from __future__ import annotations

import abc
import glob
import logging
import time
import os

from functools import reduce
from PyQt6 import QtCore
from PyQt6.QtCore import pyqtSignal

from ntfy_tray.database import Cache, Settings
from ntfy_tray.utils import process_messages

from . import ntfy
from .ntfy import models as ntfy_models


settings = Settings("ntfy-tray")
logger = logging.getLogger("ntfy-tray")


class BaseTask(QtCore.QThread):
    failed = pyqtSignal()

    def __init__(self):
        super(BaseTask, self).__init__()
        self.running = False
        self._abort = False

    @abc.abstractmethod
    def task(self):
        ...

    def abort(self):
        self._abort = True

    def abort_requested(self) -> bool:
        return self._abort

    def run(self):
        self.running = True
        try:
            self.task()
        except Exception as e:
            logger.error(f"{self.__class__.__name__} failed: {e}")
            self.failed.emit()
        finally:
            self.running = False


class DeleteMessageTask(BaseTask):
    success = pyqtSignal()

    def __init__(self, message_id: str, topic: str, ntfy_client: ntfy.NtfyClient):
        super(DeleteMessageTask, self).__init__()
        self.message_id = message_id
        self.topic = topic
        self.ntfy_client = ntfy_client

    def task(self):
        if self.ntfy_client.delete_message(self.topic, self.message_id):
            self.success.emit()
        else:
            self.failed.emit()


class DeleteApplicationMessagesTask(BaseTask):
    success = pyqtSignal()

    def __init__(self, topic: str, ntfy_client: ntfy.NtfyClient):
        super(DeleteApplicationMessagesTask, self).__init__()
        self.topic = topic
        self.ntfy_client = ntfy_client

    def task(self):
        if self.ntfy_client.delete_messages(self.topic):
            self.success.emit()
        else:
            self.failed.emit()


class DeleteAllMessagesTask(BaseTask):
    success = pyqtSignal()

    def __init__(self, ntfy_client: ntfy.NtfyClient):
        super(DeleteAllMessagesTask, self).__init__()
        self.ntfy_client = ntfy_client

    def task(self):
        if self.ntfy_client.delete_messages():
            self.success.emit()
        else:
            self.failed.emit()


class GetApplicationsTask(BaseTask):
    success = pyqtSignal(list)

    def __init__(self, ntfy_client: ntfy.NtfyClient):
        super(GetApplicationsTask, self).__init__()
        self.ntfy_client = ntfy_client

    def task(self):
        result = self.ntfy_client.get_subscriptions()
        if result is not None:
            self.success.emit(result)
        else:
            self.failed.emit()


class GetApplicationMessagesTask(BaseTask):
    message = pyqtSignal(ntfy_models.NtfyMessageModel)
    error = pyqtSignal(ntfy_models.NtfyErrorModel)

    def __init__(self, topic: str, ntfy_client: ntfy.NtfyClient):
        super(GetApplicationMessagesTask, self).__init__()
        self.topic = topic
        self.ntfy_client = ntfy_client

    def task(self):
        """Fetch messages for a specific topic"""
        try:
            # Get messages from ntfy API
            messages_data = self.ntfy_client.get_messages(self.topic)
            
            if messages_data is not None:
                # Convert to NtfyMessageModel objects
                for msg_data in messages_data:
                    # Skip non-message events
                    if msg_data.get("event") == "message":
                        msg = ntfy_models.NtfyMessageModel({
                            "id": msg_data.get("id"),
                            "appid": msg_data.get("topic"),
                            "message": msg_data.get("message", ""),
                            "title": msg_data.get("title", ""),
                            "priority": msg_data.get("priority") or 3,
                            "date": msg_data.get("time", 0)
                        })
                        if not self.abort_requested():
                            self.message.emit(msg)
            else:
                logger.warning(f"No messages returned for topic {self.topic}")
        except Exception as e:
            logger.error(f"Error fetching messages for topic {self.topic}: {e}")
            self.error.emit(ntfy_models.NtfyErrorModel({"error": str(e)}))


class GetMessagesTask(BaseTask):
    message = pyqtSignal(ntfy_models.NtfyMessageModel)
    success = pyqtSignal(ntfy_models.NtfyPagedMessagesModel)
    error = pyqtSignal(ntfy_models.NtfyErrorModel)

    def __init__(self, ntfy_client: ntfy.NtfyClient):
        super(GetMessagesTask, self).__init__()
        self.ntfy_client = ntfy_client

    def task(self):
        """Fetch messages for all topics"""
        try:
            # Get all topics from settings
            topics = settings.value("Server/topics", type=list)
            
            if not topics:
                logger.info("No topics found for fetching messages")
                return
                
            # Fetch messages for each topic
            all_messages = []
            for topic in topics:
                if self.abort_requested():
                    break
                    
                messages_data = self.ntfy_client.get_messages(topic)
                
                if messages_data is not None:
                    # Convert to NtfyMessageModel objects
                    for msg_data in messages_data:
                        # Skip non-message events
                        if msg_data.get("event") == "message":
                            msg = ntfy_models.NtfyMessageModel({
                                "id": msg_data.get("id"),
                                "appid": msg_data.get("topic"),
                                "message": msg_data.get("message", ""),
                                "title": msg_data.get("title", ""),
                                "priority": msg_data.get("priority") or 3,
                                "date": msg_data.get("time", 0)
                            })
                            if not self.abort_requested():
                                self.message.emit(msg)
                                all_messages.append(msg)
            
            # Emit success with all messages
            paging_model = ntfy_models.NtfyPagingModel({
                "limit": len(all_messages),
                "next": None,
                "since": 0,
                "size": len(all_messages)
            })
            
            paged_model = ntfy_models.NtfyPagedMessagesModel({
                "messages": all_messages,
                "paging": paging_model
            })
            
            if not self.abort_requested():
                self.success.emit(paged_model)
                
        except Exception as e:
            logger.error(f"Error fetching all messages: {e}")
            self.error.emit(ntfy_models.NtfyErrorModel({"error": str(e)}))


class ProcessMessageTask(BaseTask):
    def __init__(self, message: ntfy_models.NtfyMessageModel):
        super(ProcessMessageTask, self).__init__()
        self.message = message

    def task(self):
        for _ in process_messages([self.message]):
            pass


class VerifyServerInfoTask(BaseTask):
    success = pyqtSignal()
    incorrect_credentials = pyqtSignal()
    incorrect_url = pyqtSignal()

    def __init__(self, url: str, username: str | None = None, password: str | None = None):
        super(VerifyServerInfoTask, self).__init__()
        self.url = url
        self.username = username
        self.password = password

    def task(self):
        try:
            ntfy_client = ntfy.NtfyClient(self.url, self.username, self.password)
            result = ntfy_client.get_subscriptions()

            if result is not None:
                self.success.emit()
            else:
                self.incorrect_credentials.emit()
        except Exception as e:
            logger.error(f"VerifyServerInfoTask error: {e}")
            self.incorrect_url.emit()


class ServerConnectionWatchdogTask(BaseTask):
    closed = pyqtSignal()

    def __init__(self, ntfy_client: ntfy.NtfyClient):
        super(ServerConnectionWatchdogTask, self).__init__()
        self.ntfy_client = ntfy_client

    def task(self):
        """Monitor ntfy connection status"""
        try:
            # For ntfy, we'll periodically check if we can reach the server
            while not self.abort_requested():
                try:
                    # Simple health check
                    response = self.ntfy_client.session.get(f"{self.ntfy_client.url}/v1/health", timeout=10)
                    if not response.ok:
                        logger.warning(f"ntfy health check failed: {response.status_code}")
                        if not self.abort_requested():
                            self.closed.emit()
                        break
                except Exception as e:
                    logger.warning(f"ntfy connection health check failed: {e}")
                    if not self.abort_requested():
                        self.closed.emit()
                    break
                    
                # Wait before next check
                for _ in range(30):  # 30 seconds
                    if self.abort_requested():
                        break
                    time.sleep(1)
                    
        except Exception as e:
            logger.error(f"ServerConnectionWatchdogTask error: {e}")
            if not self.abort_requested():
                self.closed.emit()


class ExportSettingsTask(BaseTask):
    success = pyqtSignal()

    def __init__(self, path: str):
        super(ExportSettingsTask, self).__init__()
        self.path = path

    def task(self):
        settings.export(self.path)
        self.success.emit()


class ImportSettingsTask(BaseTask):
    success = pyqtSignal()

    def __init__(self, path: str):
        super(ImportSettingsTask, self).__init__()
        self.path = path

    def task(self):
        settings.load(self.path)
        self.success.emit()


class CacheSizeTask(BaseTask):
    size = pyqtSignal(int)

    def task(self):        
        cache_dir = Cache().directory()
        if os.path.exists(cache_dir):
            cache_size_bytes = reduce(lambda x, f: x + os.path.getsize(f), glob.glob(os.path.join(cache_dir, "*")), 0)
            self.size.emit(cache_size_bytes)

class ClearCacheTask(BaseTask):        
    def task(self):
        cache = Cache()
        cache.clear()
        
