# ntfy Tray

A tray notification application for receiving messages from a [ntfy server](https://ntfy.sh).

Supports **Windows 10/11**, **macOS 12+** (Intel & Apple Silicon), and **Linux**.


## Download

Pre-built binaries are available on the [Releases](https://github.com/selcuksunar/nfty-tray-app/releases) page:

| Platform | File |
|----------|------|
| Windows (installer) | `ntfy-tray-installer.exe` |
| Windows (portable) | `ntfy-tray-windows-portable.zip` |
| macOS (Apple Silicon) | `ntfy-tray-macos-arm64.dmg` |


## Features

- Receive ntfy messages in the native notification area
- Reconnect after wake from sleep or losing network connection
- Receive missed messages after losing network connection
- Disable notification banners for low priority messages
- Manually delete received messages (persistent across restarts)
- Message history with search and filtering
- Multi-language support (English, Turkish)
- Autostart at login
- Customizable fonts, notification sounds, and themes
- Self-signed certificate support


## Getting Started

### Run from source

```shell
git clone https://github.com/selcuksunar/nfty-tray-app.git
cd nfty-tray-app
pip install -r requirements.txt
python -m ntfy_tray
```

### Requirements

- Python >= 3.8
- PyQt6 >= 6.7.1
- requests
- websocket-client >= 1.0.0


## Build

### macOS

Use the included build script to create a DMG:

```shell
chmod +x build-macos.sh
./build-macos.sh
```

Or manually:

```shell
pip install pyinstaller Pillow
export MACOSX_DEPLOYMENT_TARGET=12.0
pyinstaller ntfy-tray.spec
```

### Windows

```shell
pip install pyinstaller Pillow
pyinstaller ntfy-tray.spec
```

The compiled application will be in the `dist/` directory.


## License and Acknowledgements

This project is licensed under the **GNU General Public License v3.0**.

Originally developed by [seird](https://github.com/seird/gotify-tray). This fork adapts the application for [ntfy](https://ntfy.sh) with additional features including i18n support, persistent message deletion, autostart, and macOS packaging.
