from __future__ import annotations

import getpass
import logging
import os
import platform
import sys
import tempfile

from ntfy_tray import ntfy
from ntfy_tray import utils
from ntfy_tray.__version__ import __title__
from ntfy_tray.database import Downloader, Settings
from ntfy_tray.tasks import (
    ClearCacheTask,
    CheckUpdateTask,
    DeleteApplicationMessagesTask,
    DeleteAllMessagesTask,
    DeleteMessageTask,
    GetApplicationsTask,
    GetApplicationMessagesTask,
    GetMessagesTask,
    ProcessMessageTask,
    ServerConnectionWatchdogTask,
)
from ntfy_tray.gui.themes import set_theme
from ntfy_tray.utils import get_icon, verify_server
from ntfy_tray.i18n import load_language
from PyQt6 import QtCore, QtGui, QtWidgets, QtMultimedia

from ..__version__ import __title__
from .models import (
    ApplicationAllMessagesItem,
    ApplicationItemDataRole,
    ApplicationModel,
    ApplicationModelItem,
    ApplicationProxyModel,
    MessagesModel,
    MessagesModelItem,
    MessageItemDataRole,
)
from .widgets import ImagePopup, MainWindow, MessageWidget, SettingsDialog, Tray


settings = Settings("ntfy-tray")
logger = logging.getLogger("ntfy-tray")


def init_logger(logger: logging.Logger):
    if (level := settings.value("logging/level", type=str)) != "Disabled":
        logger.setLevel(level)
    else:
        logging.disable()

    logdir = QtCore.QStandardPaths.standardLocations(QtCore.QStandardPaths.StandardLocation.AppDataLocation)[0]
    if not os.path.exists(logdir):
        os.mkdir(logdir)
    logging.basicConfig(
        filename=os.path.join(logdir, f"{__title__}.log"),
        format="%(levelname)s > %(name)s > %(asctime)s > %(filename)20s:%(lineno)3s - %(funcName)20s() > %(message)s",
    )


def _request_macos_notification_permission():
    """Request macOS notification permission via UNUserNotificationCenter (pyobjc)."""
    if platform.system() != "Darwin":
        return
    try:
        import objc
        UNUserNotificationCenter = objc.lookUpClass("UNUserNotificationCenter")
        center = UNUserNotificationCenter.currentNotificationCenter()
        # options: alert=4, sound=2, badge=1  →  7 = all
        center.requestAuthorizationWithOptions_completionHandler_(7, lambda granted, error: None)
    except Exception as e:
        logger.debug(f"macOS notification permission request failed: {e}")


class MainApplication(QtWidgets.QApplication):
    def init_ui(self):
        # Load language before creating any UI
        lang = settings.value("language", type=str) or "en"
        load_language(lang)

        _request_macos_notification_permission()
        self.ntfy_client = ntfy.NtfyClient(
            settings.value("Server/url", type=str),
            settings.value("Server/username", type=str),
            settings.value("Server/password", type=str)
        )

        self.downloader = Downloader()
        
        # Initialize audio with error handling for QtMultimedia
        try:
            self.audio = QtMultimedia.QMediaPlayer()
            self.audio_output = QtMultimedia.QAudioOutput()
            self.audio.setAudioOutput(self.audio_output)
            sound_path = settings.value("sound/path") or utils.get_abs_path("ntfy_tray/gui/sounds/sound-theme-freedesktop/message.oga")
            self.audio.setSource(QtCore.QUrl.fromLocalFile(sound_path))
        except Exception as e:
            logger.warning(f"Failed to initialize audio: {e}")
            self.audio = None

        self.messages_model = MessagesModel()
        self.application_model = ApplicationModel()
        self.application_proxy_model = ApplicationProxyModel(self.application_model)

        self.main_window = MainWindow(self.application_model, self.application_proxy_model, self.messages_model)
        self.main_window.show()  # The initial .show() is necessary to get the correct sizes when adding MessageWigets
        QtCore.QTimer.singleShot(0, self.main_window.hide)

        # Initialize tray first
        self.tray = Tray()
        self.tray.show()
        
        self.first_connect = True
        self._message_cache: dict = {}
        self._cache_load_tasks: list = []

        self.watchdog = ServerConnectionWatchdogTask(self.ntfy_client)
        
        # Link callbacks before starting any tasks
        self.link_callbacks()
        self.init_shortcuts()

        # Start applications refresh with a small delay to ensure GUI is ready
        QtCore.QTimer.singleShot(100, self.refresh_applications)

        # Check for updates 5 seconds after startup
        QtCore.QTimer.singleShot(5000, self.check_for_updates)

        if settings.value("watchdog/enabled", type=bool):
            self.watchdog.start()

        if settings.value("autostart/enabled", type=bool):
            utils.set_autostart(True)

    def set_theme(self):
        set_theme(self)

    def _is_message_deleted(self, msg) -> bool:
        """Check if a message was previously deleted (persistent)."""
        # Global cutoff (delete all messages)
        global_cutoff = settings.value("deleted/all_before", type=int)
        if global_cutoff and msg.date.toSecsSinceEpoch() <= global_cutoff:
            return True

        # Per-topic cutoff (delete all messages in a topic)
        topic = msg.get("appid", "")
        if topic:
            topic_cutoff = settings.value(f"deleted/topic_before/{topic}", type=int)
            if topic_cutoff and msg.date.toSecsSinceEpoch() <= topic_cutoff:
                return True

        # Individual message deletion
        deleted_ids = settings.value("deleted/ids", type=list) or []
        msg_id = str(msg.get("id", ""))
        if msg_id and msg_id in [str(x) for x in deleted_ids]:
            return True

        return False

    def _add_to_cache(self, topic: str, msg):
        """Add message to cache if not deleted."""
        if not self._is_message_deleted(msg):
            self._message_cache.setdefault(topic, []).append(msg)

    def _load_all_messages_into_cache(self):
        """Load messages for all topics once into memory cache."""
        # Abort existing cache load tasks to prevent duplicate entries
        for task in self._cache_load_tasks:
            task.abort()
            try:
                task.message.disconnect()
            except TypeError:
                pass

        self._message_cache = {}
        self._cache_load_tasks = []
        topics = settings.value("Server/topics", type=list)
        for topic in topics:
            task = GetApplicationMessagesTask(topic, self.ntfy_client)
            task.message.connect(
                lambda msg, t=topic: self._add_to_cache(t, msg)
            )
            task.start()
            self._cache_load_tasks.append(task)

    def refresh_applications(self):
        self.messages_model.clear()
        self.application_model.clear()
        self._message_cache = {}
        self.first_connect = True

        self.application_model.setItem(0, 0, ApplicationAllMessagesItem())

        self.get_applications_task = GetApplicationsTask(self.ntfy_client)
        self.get_applications_task.success.connect(self.get_applications_success_callback)
        self.get_applications_task.failed.connect(self.get_applications_failed_callback)
        self.get_applications_task.started.connect(self.main_window.disable_applications)
        self.get_applications_task.finished.connect(self.main_window.enable_applications)
        self.get_applications_task.start()

    def get_applications_failed_callback(self):
        """topics_url not configured or fetch failed — use previously saved topics."""
        saved_topics = settings.value("Server/topics", type=list)
        if saved_topics:
            from ntfy_tray.ntfy.models import NtfyApplicationModel
            for i, topic in enumerate(saved_topics):
                app = NtfyApplicationModel({"id": topic, "name": topic, "description": f"ntfy topic: {topic}"})
                self.application_model.setItem(i + 1, 0, ApplicationModelItem(app, QtGui.QIcon()))
            self.restart_listener()
        else:
            self.main_window.set_inactive()
            self.tray.set_icon_error()

    def get_applications_success_callback(
        self, subscriptions: list[dict],
    ):
        from ntfy_tray.ntfy.models import NtfyApplicationModel
        topics = []
        for i, sub in enumerate(subscriptions):
            topic = sub.get("topic")
            if not topic:
                continue
            topics.append(topic)
            app = NtfyApplicationModel({
                "id": topic,
                "name": sub.get("name", topic),
                "description": sub.get("description", f"ntfy topic: {topic}"),
            })
            icon = self._load_icon(sub.get("icon", ""))
            self.application_model.setItem(i + 1, 0, ApplicationModelItem(app, icon))

        if topics:
            settings.setValue("Server/topics", topics)
        self.restart_listener()

    def _load_icon(self, icon_path: str) -> QtGui.QIcon:
        if not icon_path:
            return QtGui.QIcon()
        if icon_path.startswith("http://") or icon_path.startswith("https://"):
            filename = self.downloader.get_filename(icon_path)
            return QtGui.QIcon(filename) if filename else QtGui.QIcon()
        return QtGui.QIcon(icon_path)

    def update_last_id(self, i):
        if not isinstance(i, int):
            return
        if i > settings.value("message/last", type=int):
            settings.setValue("message/last", i)

    def listener_opened_callback(self):
        self.main_window.set_active()
        self.tray.set_icon_ok()

        if self.first_connect:
            # Do not check for missed messages on launch
            self.first_connect = False
            return

        def get_missed_messages_callback(page: NtfyPagedMessagesModel):
            last_id = settings.value("message/last", type=int)
            ids = []

            page.messages.reverse()
            for message in page.messages:
                if not isinstance(message.id, int) or message.id > last_id:
                    if settings.value("message/check_missed/notify", type=bool):
                        self.new_message_callback(message, process=False)
                    else:
                        self.add_message_to_model(message, process=False)
                    ids.append(message.id)

            if ids:
                self.update_last_id(max(ids))

        self.get_missed_messages_task = GetMessagesTask(self.ntfy_client)
        self.get_missed_messages_task.success.connect(get_missed_messages_callback)
        self.get_missed_messages_task.start()

    def listener_closed_callback(self):
        self.main_window.set_inactive()
        self.tray.set_icon_error()

    def reconnect_callback(self):
        self.restart_listener()

    def restart_listener(self):
        if hasattr(self, "ntfy_listener"):
            self.ntfy_listener.stop()
        
        url = settings.value("Server/url", type=str)
        username = settings.value("Server/username", type=str)
        password = settings.value("Server/password", type=str)
        topics = settings.value("Server/topics", type=list)
        
        if not topics:
            self.main_window.set_inactive()
            return

        self.ntfy_listener = ntfy.NtfyListener(url, topics, username, password)
        self.ntfy_listener.new_message.connect(self.new_ntfy_message_callback)
        self.ntfy_listener.opened.connect(self.listener_opened_callback)
        self.ntfy_listener.closed.connect(self.main_window.set_inactive)
        self.ntfy_listener.reconnecting.connect(self.main_window.set_connecting)
        self.ntfy_listener.start()
        self._load_all_messages_into_cache()

    def new_ntfy_message_callback(self, data: dict):
        # Convert ntfy message to NtfyMessageModel for compatibility with GUI
        from ntfy_tray.ntfy.models import NtfyMessageModel
        topic = data.get("topic")
        msg = NtfyMessageModel({
            "id": data.get("id"),
            "appid": topic,
            "message": data.get("message", ""),
            "title": data.get("title", ""),
            "priority": data.get("priority") or 3,  # ntfy default priority = 3
            "date": data.get("time", 0),
            "icon": data.get("icon"),
            "attachment": data.get("attachment"),
            "tags": data.get("tags", []),
        })
        # Add to cache so future channel selections see the new message
        if topic:
            self._message_cache.setdefault(topic, []).append(msg)
        self.new_message_callback(msg)

    def abort_get_messages_task(self):
        """
        Abort any tasks that will result in new messages getting appended to messages_model
        """
        aborted_tasks = []
        for s in ["get_application_messages_task", "get_messages_task"]:
            if task := getattr(self, s, None):
                task.abort()
                aborted_tasks.append(task)
                try:
                    task.message.disconnect()
                except TypeError:
                    pass
        
        for task in aborted_tasks:
            task.wait()

    def application_selection_changed_callback(self, item: ApplicationModelItem | ApplicationAllMessagesItem):
        self.main_window.disable_buttons()
        self.abort_get_messages_task()
        self.messages_model.clear()

        if isinstance(item, ApplicationModelItem):
            topic = item.data(ApplicationItemDataRole.ApplicationRole).id
            if topic in self._message_cache:
                # Sort by date: oldest first, insert at row 0 so newest ends up at top
                msgs = sorted(self._message_cache[topic], key=lambda m: m.date.toSecsSinceEpoch())
                for msg in msgs:
                    self.messages_model.insert_message(0, msg)
                self.main_window.enable_buttons()
            else:
                self.get_application_messages_task = GetApplicationMessagesTask(topic, self.ntfy_client)
                self.get_application_messages_task.message.connect(
                    lambda msg: self.messages_model.insert_message(0, msg) if not self._is_message_deleted(msg) else None
                )
                self.get_application_messages_task.finished.connect(self.main_window.enable_buttons)
                self.get_application_messages_task.start()

        elif isinstance(item, ApplicationAllMessagesItem):
            if self._message_cache:
                all_msgs = []
                for msgs in self._message_cache.values():
                    all_msgs.extend(msgs)
                # Sort by date: oldest first, insert at row 0 so newest ends up at top
                all_msgs.sort(key=lambda m: m.date.toSecsSinceEpoch())
                for msg in all_msgs:
                    self.messages_model.insert_message(0, msg)
                self.main_window.enable_buttons()
            else:
                self.get_messages_task = GetMessagesTask(self.ntfy_client)
                self.get_messages_task.message.connect(
                    lambda msg: self.messages_model.insert_message(0, msg) if not self._is_message_deleted(msg) else None
                )
                self.get_messages_task.finished.connect(self.main_window.enable_buttons)
                self.get_messages_task.start()

    def add_message_to_model(self, message: NtfyMessageModel, process: bool = True):
        if self.application_model.itemFromId(message.appid):
            application_index = self.main_window.currentApplicationIndex()
            if selected_application_item := self.application_model.itemFromIndex(self.application_proxy_model.mapToSource(application_index)):

                def insert_message_helper():
                    if isinstance(selected_application_item, ApplicationModelItem):
                        # A single application is selected
                        # -> Only insert the message if the appid matches the selected appid
                        if (
                            message.appid 
                            == selected_application_item.data(ApplicationItemDataRole.ApplicationRole).id
                        ):
                            self.messages_model.insert_message(0, message)
                    elif isinstance(selected_application_item, ApplicationAllMessagesItem):
                        # "All messages' is selected
                        self.messages_model.insert_message(0, message)

                if process:
                    self.process_message_task = ProcessMessageTask(message)
                    self.process_message_task.finished.connect(insert_message_helper)
                    self.process_message_task.start()
                else:
                    insert_message_helper()
        else:
            logger.error(f"App id {message.appid} could not be found. Refreshing applications.")
            self.refresh_applications()

    def new_message_callback(self, message: NtfyMessageModel, process: bool = True):
        self.add_message_to_model(message, process=process)

        # Don't show a notification if it's below min priority or the window is active
        priority = message.priority if isinstance(message.priority, int) else 3
        if (
            priority < settings.value("tray/notifications/priority", type=int)
            or self.main_window.isActiveWindow()
        ):
            return

        # Change the tray icon to show there are unread notifications
        if (
            settings.value("tray/icon/unread", type=bool)
            and not self.main_window.isActiveWindow()
        ):
            self.tray.set_icon_unread()

        # Get the application icon
        if (
            settings.value("tray/notifications/icon/show", type=bool)
            and (application_item := self.application_model.itemFromId(message.appid))
        ):
            icon = application_item.icon()
        else:
            icon = QtWidgets.QSystemTrayIcon.MessageIcon.Information

        if settings.value("sound/enabled") and self.audio:
            self.audio.play()
            
        self.tray.showMessage(
            message.title,
            message.message,
            icon,
            msecs=settings.value("tray/notifications/duration_ms", type=int),
        )

    def delete_message_callback(self, message_item: MessagesModelItem):
        message = message_item.data(MessageItemDataRole.MessageRole)

        # Persist deletion locally
        deleted_ids = settings.value("deleted/ids", type=list) or []
        msg_id = str(message.id)
        if msg_id not in [str(x) for x in deleted_ids]:
            deleted_ids.append(msg_id)
            settings.setValue("deleted/ids", deleted_ids)

        self.delete_message_task = DeleteMessageTask(
            message.id, message.appid, self.ntfy_client
        )
        self.messages_model.removeRow(message_item.row())
        # Remove from cache
        topic = message.appid
        if topic in self._message_cache:
            self._message_cache[topic] = [
                m for m in self._message_cache[topic] if str(m.get("id")) != msg_id
            ]
        self.delete_message_task.start()

    def delete_all_messages_callback(
        self, item: ApplicationModelItem | ApplicationAllMessagesItem
    ):
        now = QtCore.QDateTime.currentDateTime().toSecsSinceEpoch()

        if isinstance(item, ApplicationModelItem):
            topic = item.data(ApplicationItemDataRole.ApplicationRole).id
            # Persist: mark all messages in this topic as deleted
            settings.setValue(f"deleted/topic_before/{topic}", now)
            self._message_cache.pop(topic, None)
            self.delete_application_messages_task = DeleteApplicationMessagesTask(
                topic,
                self.ntfy_client,
            )
            self.delete_application_messages_task.start()
        elif isinstance(item, ApplicationAllMessagesItem):
            # Persist: mark all messages globally as deleted
            settings.setValue("deleted/all_before", now)
            self._message_cache = {}
            self.clear_cache_task = ClearCacheTask()
            self.clear_cache_task.start()

            self.delete_all_messages_task = DeleteAllMessagesTask(self.ntfy_client)
            self.delete_all_messages_task.start()
        else:
            return

        self.messages_model.clear()

    def image_popup_callback(self, link: str, pos: QtCore.QPoint):
        if filename := self.downloader.get_filename(link):
            self.image_popup = ImagePopup(filename, pos, link)
            self.image_popup.show()
        else:
            logger.warning(f"Image {link} is not in the cache")

    def main_window_hidden_callback(self):
        if image_popup := getattr(self, "image_popup", None):
            image_popup.close()

    def theme_change_requested_callback(self, *args):
        # Set the theme
        self.set_theme()

        # Update the main window icons
        self.main_window.set_icons()

        # Update the message widget icons
        for r in range(self.messages_model.rowCount()):
            message_widget: MessageWidget = self.main_window.listView_messages.indexWidget(self.messages_model.index(r, 0))
            message_widget.set_icons()

    def check_for_updates(self):
        from ntfy_tray.__version__ import __version__
        self._update_task = CheckUpdateTask(__version__, platform.system().lower())
        self._update_task.update_available.connect(self._on_update_available)
        self._update_task.start()

    def _on_update_available(self, latest_version: str, download_url: str):
        from .widgets.UpdateDialog import UpdateDialog
        dialog = UpdateDialog(latest_version, download_url, self.main_window)
        dialog.exec()

    def language_changed_callback(self):
        """Update all UI elements when language changes."""
        self.tray.retranslate()
        self.main_window.retranslate()

    def settings_callback(self):
        from .widgets import SettingsDialog
        dialog = SettingsDialog()
        dialog.language_changed.connect(self.language_changed_callback)
        dialog.exec()

        # Handle audio settings if changed
        if hasattr(dialog, 'settings_changed') and dialog.settings_changed:
            if self.audio:
                try:
                    self.audio.setSource(QtCore.QUrl.fromLocalFile(settings.value("sound/path")))
                except Exception as e:
                    logger.warning(f"Failed to update audio source: {e}")

    def tray_notification_clicked_callback(self):
        if settings.value("tray/notifications/click", type=bool):
            self.main_window.bring_to_front()

    def tray_activated_callback(
        self, reason: QtWidgets.QSystemTrayIcon.ActivationReason
    ):
        if (
            reason == QtWidgets.QSystemTrayIcon.ActivationReason.Trigger
            and platform.system() != "Darwin"
        ):
            self.main_window.bring_to_front()

    def link_callbacks(self):
        # Ensure tray callbacks are properly connected
        self.tray.actionQuit.triggered.connect(self.quit)
        self.tray.actionSettings.triggered.connect(self.settings_callback)
        self.tray.actionShowWindow.triggered.connect(self.main_window.bring_to_front)
        self.tray.actionReconnect.triggered.connect(self.reconnect_callback)
        self.tray.messageClicked.connect(self.tray_notification_clicked_callback)
        self.tray.activated.connect(self.tray_activated_callback)

        # Main window callbacks
        self.main_window.refresh.connect(self.refresh_applications)
        self.main_window.delete_all.connect(self.delete_all_messages_callback)
        self.main_window.application_selection_changed.connect(self.application_selection_changed_callback)
        self.main_window.delete_message.connect(self.delete_message_callback)
        self.main_window.image_popup.connect(self.image_popup_callback)
        self.main_window.hidden.connect(self.main_window_hidden_callback)
        self.main_window.activated.connect(self.tray.revert_icon)
        
        self.styleHints().colorSchemeChanged.connect(self.theme_change_requested_callback)

        self.messages_model.rowsInserted.connect(self.main_window.display_message_widgets)

        # ntfy_listener handles signals now
        self.watchdog.closed.connect(self.listener_closed_callback)


    def init_shortcuts(self):
        self.shortcut_quit = QtGui.QShortcut(
            QtGui.QKeySequence.fromString(settings.value("shortcuts/quit", type=str)),
            self.main_window,
        )
        self.shortcut_quit.activated.connect(self.quit)

    def acquire_lock(self) -> bool:
        temp_dir = tempfile.gettempdir()
        lock_filename = os.path.join(temp_dir, __title__ + "-" + getpass.getuser() + ".lock")
        self.lock_file = QtCore.QLockFile(lock_filename)
        self.lock_file.setStaleLockTime(0)
        return self.lock_file.tryLock()

    def _stop_thread(self, thread, timeout_ms=2000):
        """Stop a QThread with a timeout, forcefully terminate if needed."""
        if thread is None or not thread.isRunning():
            return
        if not thread.wait(timeout_ms):
            logger.warning(f"Thread {thread.__class__.__name__} did not stop in time, terminating.")
            thread.terminate()
            thread.wait(1000)

    def quit(self):
        logger.debug("Quit requested.")

        self.main_window.store_state()
        self.tray.hide()
        self.lock_file.unlock()

        # Close ntfy_client session — interrupts all in-progress HTTP requests
        # (watchdog health checks, GetApplicationsTask, GetMessagesTask, etc.)
        if hasattr(self, "ntfy_client"):
            try:
                self.ntfy_client.session.close()
            except Exception:
                pass

        # Abort any running message tasks
        for attr in ("get_applications_task", "get_application_messages_task",
                     "get_messages_task", "get_missed_messages_task", "process_message_task"):
            task = getattr(self, attr, None)
            if task and task.isRunning():
                task.abort()

        # Stop watchdog — disconnect signal first to avoid triggering reconnects
        if hasattr(self, "watchdog"):
            try:
                self.watchdog.closed.disconnect()
            except TypeError:
                pass
            self.watchdog.abort()
            self._stop_thread(self.watchdog)

        # Stop listener — close connection first to unblock iter_lines()
        if hasattr(self, "ntfy_listener"):
            try:
                self.ntfy_listener.closed.disconnect()
                self.ntfy_listener.reconnecting.disconnect()
            except TypeError:
                pass
            self.ntfy_listener.stop()
            self._stop_thread(self.ntfy_listener)

        super(MainApplication, self).quit()
        sys.exit(0)


def start_gui():
    app = MainApplication(sys.argv)
    app.setApplicationName(__title__)
    app.setDesktopFileName("ntfytray.desktop")
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(QtGui.QIcon(get_icon("ntfy-small")))
    app.set_theme()

    init_logger(logger)

    # Handle .ntfy config file passed as argument (Windows / Linux)
    config_file_path = None
    for arg in sys.argv[1:]:
        if arg.endswith(".ntfy") and not arg.startswith("-"):
            config_file_path = arg
            break

    if config_file_path:
        from ntfy_tray.config_file import apply_config_file
        apply_config_file(config_file_path)

    # prevent multiple instances
    if (app.acquire_lock() or "--no-lock" in sys.argv) and verify_server():
        app.init_ui()

        # Handle .ntfy config file opened via macOS Finder (file open event)
        app.fileOpenRequest.connect(lambda path: _handle_file_open(app, path))

        sys.exit(app.exec())


def _handle_file_open(app: MainApplication, path: str):
    """Handle macOS Finder file open event for .ntfy files."""
    if not path.endswith(".ntfy"):
        return
    from ntfy_tray.config_file import apply_config_file
    from PyQt6 import QtWidgets
    if apply_config_file(path):
        QtWidgets.QMessageBox.information(
            app.main_window,
            "ntfy Tray",
            f"Configuration applied from:\n{path}\n\nRestart to connect with new settings.",
        )
