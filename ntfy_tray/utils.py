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


# Maps legacy icon names to the current image files
_ICON_MAP = {
    "tray":         "ntfy.png",
    "tray-macos":   "ntfy.png",
    "tray-unread":  "ntfy.png",
    "tray-unread-macos": "ntfy.png",
    "tray-error":   "ntfy-error.png",
    "tray-error-macos": "ntfy-error.png",
    "ntfy-small":   "ntfy.png",
    "ntfy-small-macos": "ntfy.png",
    "logo":         "ntfy.ico",
    "logo-macos":   "ntfy.icns",
}


def get_icon(name: str) -> str:
    filename = _ICON_MAP.get(name, f"{name}.png")
    return get_abs_path(f"ntfy_tray/gui/images/{filename}")

def tags_to_emojis(tags: list) -> str:
    """Convert ntfy tag shortcodes (e.g. ['tada', 'warning']) to emoji characters.
    Tries 'alias' (GitHub/Slack style) first, then 'en'. Skips unrecognised tags.
    """
    if not tags:
        return ""
    try:
        import emoji as _emoji_lib
        parts = []
        for tag in tags:
            shortcode = f":{tag}:"
            converted = _emoji_lib.emojize(shortcode, language="alias")
            if converted == shortcode:
                converted = _emoji_lib.emojize(shortcode, language="en")
            if converted != shortcode:
                parts.append(converted)
        return " ".join(parts)
    except ImportError:
        return ""


def update_widget_property(widget: QtWidgets.QWidget, property: str, value: str):
    widget.setProperty(property, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def _get_executable_path() -> str:
    """Return the path to the running executable (frozen or script)."""
    import sys
    if getattr(sys, 'frozen', False):
        # PyInstaller bundle
        if platform.system() == "Darwin":
            # .app bundle: go up from MacOS/ntfy-tray to .app
            app_path = Path(sys.executable).resolve()
            for parent in app_path.parents:
                if parent.suffix == ".app":
                    return str(parent)
            return sys.executable
        return sys.executable
    else:
        return f"{sys.executable} -m ntfy_tray"


def set_autostart(enabled: bool):
    """Enable or disable autostart at login for the current platform."""
    system = platform.system()
    exe = _get_executable_path()

    if system == "Darwin":
        plist_dir = Path.home() / "Library" / "LaunchAgents"
        plist_path = plist_dir / "com.ntfy-tray.app.plist"
        if enabled:
            plist_dir.mkdir(parents=True, exist_ok=True)
            if exe.endswith(".app"):
                program_args = f"    <array>\n        <string>/usr/bin/open</string>\n        <string>-a</string>\n        <string>{exe}</string>\n    </array>"
            else:
                parts = exe.split(" ")
                args_xml = "\n".join(f"        <string>{p}</string>" for p in parts)
                program_args = f"    <array>\n{args_xml}\n    </array>"
            plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ntfy-tray.app</string>
    <key>ProgramArguments</key>
{program_args}
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
"""
            plist_path.write_text(plist_content)
        else:
            plist_path.unlink(missing_ok=True)

    elif system == "Windows":
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            if enabled:
                winreg.SetValueEx(key, "ntfy-tray", 0, winreg.REG_SZ, exe)
            else:
                try:
                    winreg.DeleteValue(key, "ntfy-tray")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except OSError:
            pass

    elif system == "Linux":
        desktop_dir = Path.home() / ".config" / "autostart"
        desktop_path = desktop_dir / "ntfy-tray.desktop"
        if enabled:
            desktop_dir.mkdir(parents=True, exist_ok=True)
            desktop_content = f"""[Desktop Entry]
Type=Application
Name=ntfy Tray
Exec={exe}
Icon=ntfy-tray
Terminal=false
X-GNOME-Autostart-enabled=true
"""
            desktop_path.write_text(desktop_content)
        else:
            desktop_path.unlink(missing_ok=True)
