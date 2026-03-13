#!/bin/sh

if [ $# -eq 0 ]
  then
    echo "Call the script with the desired fpm output type [deb, pacman, ...]"
	exit
fi

rm -rf build/linux

pyinstaller ntfy-tray.spec

mkdir -p build/linux/opt
mkdir -p build/linux/usr/share/applications
mkdir -p build/linux/usr/share/icons

cp -r dist/ntfy-tray build/linux/opt/ntfy-tray
cp ntfy_tray/gui/images/logo.ico build/linux/usr/share/icons/ntfy-tray.ico
cp gotifytray.desktop build/linux/usr/share/applications

find build/linux/opt/ntfy-tray -type f -exec chmod 644 -- {} +
find build/linux/opt/ntfy-tray -type d -exec chmod 755 -- {} +
find build/linux/usr/share -type f -exec chmod 644 -- {} +
chmod +x build/linux/opt/ntfy-tray/ntfy-tray

fpm --verbose \
    -C build/linux \
    -s dir \
    -t $1 \
    -p dist/ \
    -n ntfy-tray \
    --url https://github.com/seird/ntfy-tray \
    -m k.dries@protonmail.com \
    --description "Gotify Tray. A tray notification application for receiving messages from a Gotify server." \
    --category internet \
    --version "$(cat version.txt)" \
    --license GPLv3
