from __future__ import annotations

import logging

import requests

from PyQt6 import QtCore


logger = logging.getLogger("ntfy-tray")


class AttributeDict(dict):
    def __init__(self, *args, **kwargs):
        super(AttributeDict, self).__init__(*args, **kwargs)
        self.__dict__ = self


class NtfyApplicationModel(AttributeDict):
    description: str
    id: int
    image: str
    internal: bool
    name: str
    token: str


class NtfyPagingModel(AttributeDict):
    limit: int
    next: str | None = None
    since: int
    size: int


class NtfyMessageModel(AttributeDict):
    appid: int
    date: QtCore.QDateTime
    extras: dict | None = None
    id: int
    message: str
    priority: int | None = None
    title: str | None = None

    def __init__(self, d: dict, *args, **kwargs):
        date_val = d.get("date", 0)
        if isinstance(date_val, (int, float)):
            dt = QtCore.QDateTime.fromSecsSinceEpoch(int(date_val))
        elif isinstance(date_val, str):
            dt = QtCore.QDateTime.fromString(date_val, QtCore.Qt.DateFormat.ISODate).toLocalTime()
            if not dt.isValid():
                dt = QtCore.QDateTime.currentDateTime()
        else:
            dt = QtCore.QDateTime.currentDateTime()
        d["date"] = dt
        super(NtfyMessageModel, self).__init__(d, *args, **kwargs)


class NtfyPagedMessagesModel(AttributeDict):
    messages: list[NtfyMessageModel]
    paging: NtfyPagingModel


class NtfyHealthModel(AttributeDict):
    database: str
    health: str


class NtfyVersionModel(AttributeDict):
    buildDate: str
    commit: str
    version: str


class NtfyErrorModel(AttributeDict):
    error: str
    errorCode: int
    errorDescription: str

    def __init__(self, response, *args, **kwargs):
        if isinstance(response, dict):
            j = response
        else:
            try:
                j = response.json()
            except ValueError:
                j = {
                    "error": "unknown",
                    "errorCode": response.status_code,
                    "errorDescription": "",
                }

        super(NtfyErrorModel, self).__init__(j, *args, **kwargs)
