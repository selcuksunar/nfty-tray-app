import logging
import platform
import os

from ntfy_tray.__version__ import __version__
from ntfy_tray.database import Cache, Settings
from ntfy_tray.ntfy import models as ntfy_models
from ntfy_tray.gui.models import MessagesModelItem
from . import MessageWidget
from ntfy_tray.utils import get_image, get_icon, verify_server, open_file, set_autostart
from ntfy_tray.i18n import tr, load_language, available_languages, current_language
from ntfy_tray.tasks import (
    ExportSettingsTask,
    ImportSettingsTask,
    CacheSizeTask,
    ClearCacheTask,
)
from typing import Any
from PyQt6 import QtCore, QtGui, QtWidgets

from ..designs.widget_settings import Ui_Dialog


logger = logging.getLogger("ntfy-tray")
settings = Settings("ntfy-tray")


class SettingsDialog(QtWidgets.QDialog, Ui_Dialog):
    quit_requested = QtCore.pyqtSignal()
    style_changed = QtCore.pyqtSignal()
    language_changed = QtCore.pyqtSignal()

    def __init__(self):
        super(SettingsDialog, self).__init__()
        self.setupUi(self)
        self.setWindowTitle(tr("settings.title"))

        self.settings_changed = False
        self.changes_applied = False
        self.server_changed = False

        self.initUI()

        self.link_callbacks()

    def initUI(self):
        self.buttonBox.button(QtWidgets.QDialogButtonBox.StandardButton.Apply).setEnabled(False)

        # Language
        langs = available_languages()
        self._lang_codes = list(langs.keys())
        self.combo_language.addItems(list(langs.values()))
        cur_lang = settings.value("language", type=str) or "en"
        if cur_lang in self._lang_codes:
            self.combo_language.setCurrentIndex(self._lang_codes.index(cur_lang))

        # Notifications
        self.spin_priority.setValue(settings.value("tray/notifications/priority", type=int))

        self.spin_duration.setValue(settings.value("tray/notifications/duration_ms", type=int))
        if platform.system() == "Windows":
            # The notification duration setting is ignored by windows
            self.label_notification_duration.hide()
            self.spin_duration.hide()
            self.label_notification_duration_ms.hide()

        self.cb_notify.setChecked(settings.value("message/check_missed/notify", type=bool))

        self.cb_notification_click.setChecked(settings.value("tray/notifications/click", type=bool))

        self.cb_tray_icon_unread.setChecked(settings.value("tray/icon/unread", type=bool))

        self.groupBox_sound.setChecked(settings.value("sound/enabled", type=bool))
        if sound_path := settings.value("sound/path"):
            self.line_sound.setText(sound_path)
        self.line_sound.setToolTip(tr("settings.dialog.sound_choose"))

        # Interface
        self.combo_style.addItem("Default")
        self.combo_style.addItems(QtWidgets.QStyleFactory.keys())
        style_override = settings.value("StyleOverride", type=str) or "Default"
        self.combo_style.setCurrentText(style_override)

        self.cb_priority_colors.setChecked(settings.value("MessageWidget/priority_color", type=bool))
        self.cb_image_urls.setChecked(settings.value("MessageWidget/image_urls", type=bool))
        self.cb_locale.setChecked(settings.value("locale", type=bool))
        self.cb_sort_applications.setChecked(settings.value("ApplicationModel/sort", type=bool))
        self.cb_autostart.setChecked(settings.value("autostart/enabled", type=bool))

        # Logging
        self.combo_logging.addItems(
            [
                logging.getLevelName(logging.ERROR),
                logging.getLevelName(logging.WARNING),
                logging.getLevelName(logging.INFO),
                logging.getLevelName(logging.DEBUG),
                "Disabled",
            ]
        )
        self.combo_logging.setCurrentText(settings.value("logging/level", type=str))

        # Fonts
        self.add_message_widget()

        # Topics JSON URL
        self.line_topics_url.setText(settings.value("Server/topics_url", type=str))

        # Advanced
        self.groupbox_image_popup.setChecked(settings.value("ImagePopup/enabled", type=bool))
        self.spin_popup_w.setValue(settings.value("ImagePopup/w", type=int))
        self.spin_popup_h.setValue(settings.value("ImagePopup/h", type=int))
        self.label_cache.setText("0 MB")
        self.compute_cache_size()
        self.groupbox_watchdog.setChecked(settings.value("watchdog/enabled", type=bool))
        self.spin_watchdog_interval.setValue(settings.value("watchdog/interval/s", type=int))

        self.label_app_version.setText(__version__)
        self.label_qt_version.setText(QtCore.QT_VERSION_STR)
        self.label_app_icon.setPixmap(QtGui.QIcon(get_image("ntfy.png")).pixmap(22,22))
        self.label_qt_icon.setPixmap(QtGui.QIcon(get_image("qt.png")).pixmap(22,22))

    def add_message_widget(self):
        self.message_widget = MessageWidget(
            self,
            MessagesModelItem(
                ntfy_models.NtfyMessageModel(
                    {
                        "date": "2021-01-01T11:11:00.928224+01:00",
                        "message": "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Proin luctus.",
                        "title": "Title",
                        "priority": 4,
                    }
                )
            ),
        )
        self.layout_fonts_message.addWidget(self.message_widget)

    def compute_cache_size(self):
        self.cache_size_task = CacheSizeTask()
        self.cache_size_task.size.connect(lambda size: self.label_cache.setText(f"{round(size/1e6, 1)} MB"))
        self.cache_size_task.start()

    def set_value(self, key: str, value: Any, widget: QtWidgets.QWidget):
        """Set a Settings value, only if the widget's value_changed attribute has been set
        """
        if hasattr(widget, "value_changed"):
            settings.setValue(key, value)

    def connect_signal(self, signal: QtCore.pyqtBoundSignal, widget: QtWidgets.QWidget):
        """Connect to a signal and set the value_changed attribute for a widget on trigger
        """
        signal.connect(lambda *args: self.setting_changed_callback(widget))

    def change_server_info_callback(self):
        self.server_changed = verify_server(force_new=True, enable_import=False)

    def setting_changed_callback(self, widget: QtWidgets.QWidget):
        self.settings_changed = True
        self.buttonBox.button(QtWidgets.QDialogButtonBox.StandardButton.Apply).setEnabled(True)
        setattr(widget, "value_changed", True)

    def change_font_callback(self, name: str):
        label: QtWidgets.QLabel = getattr(self.message_widget, "label_" + name)

        font, accepted = QtWidgets.QFontDialog.getFont(
            label.font(), self, tr("settings.fonts.select").format(name=name)
        )

        if accepted:
            self.setting_changed_callback(label)
            label.setFont(font)

    def export_callback(self):
        fname = QtWidgets.QFileDialog.getSaveFileName(
            self, tr("settings.dialog.export_settings"), settings.value("export/path", type=str), "*",
        )[0]
        if fname and os.path.exists(os.path.dirname(fname)):
            self.export_settings_task = ExportSettingsTask(fname)
            self.export_settings_task.start()
            settings.setValue("export/path", fname)

    def import_success_callback(self):
        response = QtWidgets.QMessageBox.information(
            self, tr("settings.dialog.restart"), tr("settings.dialog.restart")
        )
        if response == QtWidgets.QMessageBox.StandardButton.Ok:
            self.quit_requested.emit()

    def import_callback(self):
        fname = QtWidgets.QFileDialog.getOpenFileName(
            self, tr("settings.dialog.import_settings"), settings.value("export/path", type=str), "*",
        )[0]
        if fname and os.path.exists(fname):
            self.import_settings_task = ImportSettingsTask(fname)
            self.import_settings_task.success.connect(self.import_success_callback)
            self.import_settings_task.start()

    def reset_fonts_callback(self):
        response = QtWidgets.QMessageBox.warning(
            self,
            tr("settings.dialog.reset_fonts.title"),
            tr("settings.dialog.reset_fonts.text"),
            QtWidgets.QMessageBox.StandardButton.Ok
            | QtWidgets.QMessageBox.StandardButton.Cancel,
            defaultButton=QtWidgets.QMessageBox.StandardButton.Cancel,
        )
        if response == QtWidgets.QMessageBox.StandardButton.Ok:
            settings.remove("MessageWidget/font")
            self.message_widget.deleteLater()
            self.add_message_widget()

    def reset_callback(self):
        response = QtWidgets.QMessageBox.warning(
            self,
            tr("settings.dialog.reset_settings.title"),
            tr("settings.dialog.reset_settings.text"),
            QtWidgets.QMessageBox.StandardButton.Ok
            | QtWidgets.QMessageBox.StandardButton.Cancel,
            defaultButton=QtWidgets.QMessageBox.StandardButton.Cancel,
        )
        if response == QtWidgets.QMessageBox.StandardButton.Ok:
            settings.clear()
            self.quit_requested.emit()

    def clear_cache_callback(self):
        self.clear_cache_task = ClearCacheTask()
        self.clear_cache_task.start()
        self.label_cache.setText("0 MB")

    def select_sound_callback(self):
        fname = QtWidgets.QFileDialog.getOpenFileName(
            self, tr("settings.dialog.sound_choose"), os.path.expanduser("~"),
            tr("settings.dialog.sound_filter")
        )[0]
        if fname and os.path.exists(fname):
            self.line_sound.setText(fname)

    def link_callbacks(self):
        self.buttonBox.button(QtWidgets.QDialogButtonBox.StandardButton.Apply).clicked.connect(self.apply_settings)

        # Language
        self.connect_signal(self.combo_language.currentIndexChanged, self.combo_language)

        # Notifications
        self.connect_signal(self.spin_priority.valueChanged, self.spin_priority)
        self.connect_signal(self.spin_duration.valueChanged, self.spin_duration)
        self.connect_signal(self.cb_notify.stateChanged, self.cb_notify)
        self.connect_signal(self.cb_notification_click.stateChanged, self.cb_notification_click)
        self.connect_signal(self.cb_tray_icon_unread.stateChanged, self.cb_tray_icon_unread)
        self.connect_signal(self.groupBox_sound.toggled, self.groupBox_sound)
        self.connect_signal(self.line_sound.textChanged, self.line_sound)
        self.pb_sound.clicked.connect(self.select_sound_callback)

        # Interface
        self.connect_signal(self.cb_priority_colors.stateChanged, self.cb_priority_colors)
        self.connect_signal(self.cb_image_urls.stateChanged, self.cb_image_urls)
        self.connect_signal(self.cb_locale.stateChanged, self.cb_locale)
        self.connect_signal(self.cb_sort_applications.stateChanged, self.cb_sort_applications)
        self.connect_signal(self.combo_style.currentTextChanged, self.combo_style)
        self.connect_signal(self.cb_autostart.stateChanged, self.cb_autostart)

        # Server info
        self.pb_change_server_info.clicked.connect(self.change_server_info_callback)
        self.connect_signal(self.line_topics_url.textChanged, self.line_topics_url)

        # Logging
        self.connect_signal(self.combo_logging.currentTextChanged, self.combo_logging)
        self.pb_open_log.clicked.connect(lambda: open_file(logger.root.handlers[0].baseFilename))

        # Fonts
        self.pb_reset_fonts.clicked.connect(self.reset_fonts_callback)

        self.pb_font_message_title.clicked.connect(lambda: self.change_font_callback("title"))
        self.pb_font_message_date.clicked.connect(lambda: self.change_font_callback("date"))
        self.pb_font_message_content.clicked.connect(lambda: self.change_font_callback("message"))

        # Advanced
        self.pb_export.clicked.connect(self.export_callback)
        self.pb_import.clicked.connect(self.import_callback)
        self.pb_reset.clicked.connect(self.reset_callback)
        self.connect_signal(self.groupbox_image_popup.toggled, self.groupbox_image_popup)
        self.connect_signal(self.spin_popup_w.valueChanged, self.spin_popup_w)
        self.connect_signal(self.spin_popup_h.valueChanged, self.spin_popup_h)
        self.pb_clear_cache.clicked.connect(self.clear_cache_callback)
        self.pb_open_cache_dir.clicked.connect(lambda: open_file(Cache().directory()))
        self.connect_signal(self.groupbox_watchdog.toggled, self.groupbox_watchdog)
        self.connect_signal(self.spin_watchdog_interval.valueChanged, self.spin_watchdog_interval)

    def apply_settings(self):
        # Language
        if hasattr(self.combo_language, "value_changed"):
            idx = self.combo_language.currentIndex()
            if 0 <= idx < len(self._lang_codes):
                new_lang = self._lang_codes[idx]
                settings.setValue("language", new_lang)
                load_language(new_lang)
                self.retranslateUi(self)
                self.setWindowTitle(tr("settings.title"))
                self.language_changed.emit()

        # Priority
        self.set_value("tray/notifications/priority", self.spin_priority.value(), self.spin_priority)
        self.set_value("tray/notifications/duration_ms", self.spin_duration.value(), self.spin_duration)
        self.set_value("message/check_missed/notify", self.cb_notify.isChecked(), self.cb_notify)
        self.set_value("tray/notifications/click", self.cb_notification_click.isChecked(), self.cb_notification_click)
        self.set_value("tray/icon/unread", self.cb_tray_icon_unread.isChecked(), self.cb_tray_icon_unread)
        self.set_value("sound/enabled", self.groupBox_sound.isChecked(), self.groupBox_sound)
        self.set_value("sound/path", self.line_sound.text(), self.line_sound)

        # Interface
        self.set_value("MessageWidget/priority_color", self.cb_priority_colors.isChecked(), self.cb_priority_colors)
        self.set_value("MessageWidget/image_urls", self.cb_image_urls.isChecked(), self.cb_image_urls)
        self.set_value("locale", self.cb_locale.isChecked(), self.cb_locale)
        self.set_value("ApplicationModel/sort", self.cb_sort_applications.isChecked(), self.cb_sort_applications)
        selected_style = self.combo_style.currentText().replace("Default", "")
        if selected_style != settings.value("StyleOverride", type=str):
            self.set_value("StyleOverride", selected_style, self.combo_style)
            self.style_changed.emit()
        if hasattr(self.cb_autostart, "value_changed"):
            autostart_enabled = self.cb_autostart.isChecked()
            self.set_value("autostart/enabled", autostart_enabled, self.cb_autostart)
            set_autostart(autostart_enabled)

        # Logging
        selected_level = self.combo_logging.currentText()
        self.set_value("logging/level", selected_level, self.combo_logging)
        if selected_level == "Disabled":
            logging.disable(logging.CRITICAL)
        else:
            logging.disable(logging.NOTSET)
            logger.setLevel(selected_level)

        # Fonts
        self.set_value("MessageWidget/font/title", self.message_widget.label_title.font().toString(), self.message_widget.label_title)
        self.set_value("MessageWidget/font/date", self.message_widget.label_date.font().toString(), self.message_widget.label_date)
        self.set_value("MessageWidget/font/message", self.message_widget.label_message.font().toString(), self.message_widget.label_message)

        # Topics JSON URL
        self.set_value("Server/topics_url", self.line_topics_url.text().strip(), self.line_topics_url)

        # Advanced
        self.set_value("ImagePopup/enabled", self.groupbox_image_popup.isChecked(), self.groupbox_image_popup)
        self.set_value("ImagePopup/w", self.spin_popup_w.value(), self.spin_popup_w)
        self.set_value("ImagePopup/h", self.spin_popup_h.value(), self.spin_popup_h)
        self.set_value("watchdog/enabled", self.groupbox_watchdog.isChecked(), self.groupbox_watchdog)
        self.set_value("watchdog/interval/s", self.spin_watchdog_interval.value(), self.spin_watchdog_interval)

        self.settings_changed = False
        self.buttonBox.button(QtWidgets.QDialogButtonBox.StandardButton.Apply).setEnabled(False)

        self.changes_applied = True
