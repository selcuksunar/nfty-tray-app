# ntfy Tray

A tray notification application for receiving messages from a [ntfy server](https://ntfy.sh).


## Getting started


- Clone this repository and run from source:
    ```shell
    $ git clone https://github.com/selcuksunar/ntfy-tray-app.git
    $ cd ntfy-tray-app
    $ pip install -r requirements.txt
    $ python -m ntfy_tray
    ```


## Features

- Receive ntfy messages in the native notification area.
- Reconnect after wake from sleep or losing network connection.
- Disable notification banners for low priority messages.
- Manually delete received messages.
- Go through a history of all previously received messages.
- Receive missed messages after losing network connection.


## Images


### Main window

Default                                         |  Dark                                                      
:-------------------------------------------------:|:---------------------------------------------------------:
![main window default](https://raw.githubusercontent.com/seird/ntfy-tray/develop/images/main_default.png)            |  ![main window dark](https://raw.githubusercontent.com/seird/ntfy-tray/develop/images/main_dark.png)


### Notification banners

Windows 10                                         |  KDE                                                      |  MacOS 12
:-------------------------------------------------:|:---------------------------------------------------------:|:---------------------------------------------------------:
![notification](https://raw.githubusercontent.com/seird/ntfy-tray/develop/images/notification.png)            |  ![kde_notification](https://raw.githubusercontent.com/seird/ntfy-tray/develop/images/kde_notification.png)      |  ![macos_notification](https://raw.githubusercontent.com/seird/ntfy-tray/develop/images/macos_notification.png)
![notification](https://raw.githubusercontent.com/seird/ntfy-tray/develop/images/notification_centre.png)     |  ![kde_notification](https://raw.githubusercontent.com/seird/ntfy-tray/develop/images/kde_notification_centre.png) |  


## Build instructions (macOS)

To build the macOS `.app` bundle:
```shell
pip install pyinstaller Pillow
pyinstaller ntfy-tray.spec
```
The compiled application will be located in the `dist/` directory.

See [BUILDING](BUILDING.md) for general build instructions from the original repository.


## Requirements

- python >=3.8 (Supports older versions for macOS compatibility)


## License and Acknowledgements

This project is licensed under the **GNU General Public License v3.0**. 

The core application was originally developed by [seird](https://github.com/seird/ntfy-tray). This repository maintains modifications specifically aimed at providing better support and packaging for macOS environments.
