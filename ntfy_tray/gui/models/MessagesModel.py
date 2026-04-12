import enum

from typing import cast
from PyQt6 import QtCore, QtGui
from ntfy_tray.ntfy import models as ntfy_models


class MessageItemDataRole(enum.IntEnum):
    MessageRole = QtCore.Qt.ItemDataRole.UserRole + 1


class MessagesModelItem(QtGui.QStandardItem):
    def __init__(self, message: ntfy_models.NtfyMessageModel, *args, **kwargs):
        super(MessagesModelItem, self).__init__()
        self.setData(message, MessageItemDataRole.MessageRole)


class MessagesModel(QtGui.QStandardItemModel):
    def insert_message(self, row: int, message: ntfy_models.NtfyMessageModel):
        message_item = MessagesModelItem(message)
        self.insertRow(row, message_item)

    def append_message(self, message: ntfy_models.NtfyMessageModel):
        message_item = MessagesModelItem(message)
        self.appendRow(message_item)

    def setItem(self, row: int, column: int, item: MessagesModelItem) -> None:
        super(MessagesModel, self).setItem(row, column, item)

    def itemFromIndex(self, index: QtCore.QModelIndex) -> MessagesModelItem:
        return cast(MessagesModelItem, super(MessagesModel, self).itemFromIndex(index))
