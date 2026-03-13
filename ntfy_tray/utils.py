from __future__ import annotations

import os
import platform
import re
import subprocess

from pathlib import Path
from typing import Iterator
from PyQt6 import QtWidgets

from ntfy_tray.ntfy import models as ntfy_models
from ntfy_tray.database import Downloader


def verify_server(force_new: bool = False, enable_import: bool = True) -> bool:
    from ntfy_tray.gui import ServerInfoDialog
    from ntfy_tray.database import Settings

    settings = Settings("ntfy-tray")

    url = settings.value("Server/url", type=str)
    username = settings.value("Server/username", type=str)
    password = settings.value("Server/password", type=str)

    if not url or force_new:
        dialog = ServerInfoDialog(url, username, enable_import)
        if dialog.exec():
            settings.setValue("Server/url", dialog.line_url.text())
            settings.setValue("Server/username", dialog.line_token.text())
            settings.setValue("Server/password", dialog.line_password.text())
            return True
        else:
            return False
    else:
        return True


def process_messages(messages: list[ntfy_models.NtfyMessageModel]) -> Iterator[ntfy_models.NtfyMessageModel]:
    downloader = Downloader()
    for message in messages:
        if image_url := extract_image(message.message):
            downloader.get_filename(image_url)
        yield message


def convert_links(text):
    _link = re.compile(
        r'(?:(https://|http://)|(www\.))(\S+\b/?)([!"#$%&\'()*+,\-./:;<=>?@[\\\]^_`{|}~]*)(\s|$)',
        re.I,
    )

    def replace(match):
        groups = match.groups()
        protocol = groups[0] or ""  # may be None
        www_lead = groups[1] or ""  # may be None
        return '<a href="http://{1}{2}" rel="nofollow">{0}{1}{2}</a>{3}{4}'.format(
            protocol, www_lead, *groups[2:]
        )

    return _link.sub(replace, text)


def extract_image(s: str) -> str | None:
    """If `s` contains only an image URL, this function returns that URL.
        This function also extracts a URL in the `![](<url>)` markdown image format.
    """
    s = s.strip()

    # Return True if 's' is a url and has an image extension
    RE = r'(?:(https://|http://)|(www\.))(\S+\b/?)([!"#$%&\'()*+,\-./:;<=>?@[\\\]^_`{|}~]*).(jpg|jpeg|png|bmp|gif)(\s|$)'
    if re.compile(RE, re.I).fullmatch(s) is not None:
        return s

    # Return True if 's' has the markdown image format
    RE = r'!\[[^\]]*\]\((.*?)\s*("(?:.*[^"])")?\s*\)'
    if re.compile(RE, re.I).fullmatch(s) is not None:
        return re.compile(RE, re.I).findall(s)[0][0]

    return None


def get_abs_path(s) -> str:
    h = Path(__file__).parent.parent
    p = Path(s)
    return os.path.join(h, p).replace("\\", "/")


def open_file(filename: str):
    if platform.system() == "Linux":
        subprocess.call(["xdg-open", filename])
    elif platform.system() == "Windows":
        os.startfile(filename)
    elif platform.system() == "Darwin":
        subprocess.call(["open", filename])


def get_image(name: str) -> str:
    return get_abs_path(f"ntfy_tray/gui/images/{name}")


def get_icon(name: str) -> str:
    if platform.system() == "Darwin":
        name += "-macos"

    return get_abs_path(f"ntfy_tray/gui/images/{name}.png")

def update_widget_property(widget: QtWidgets.QWidget, property: str, value: str):
    widget.setProperty(property, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()
