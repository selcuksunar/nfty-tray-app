#!/bin/bash
set -e

cd "$(dirname "$0")"

export MACOSX_DEPLOYMENT_TARGET=12.0

ARCH=$(uname -m)
if [ "$ARCH" = "x86_64" ]; then
    DMG_NAME="build/ntfy-tray-macos-x86_64.dmg"
elif [ "$ARCH" = "arm64" ]; then
    DMG_NAME="build/ntfy-tray-macos-arm64.dmg"
else
    DMG_NAME="build/ntfy-tray-macos-${ARCH}.dmg"
fi

mkdir -p build

echo "=== ntfy-tray macOS Builder ==="
echo "Arch: $ARCH"
echo "Output: $DMG_NAME"
echo ""

# Temizle
rm -rf dist dmg-stage "$DMG_NAME"
mkdir -p build

# Derle
echo ">>> PyInstaller ile derleniyor..."
python3 -m PyInstaller ntfy-tray.spec

# DMG oluştur
echo ">>> DMG oluşturuluyor..."
mkdir -p dmg-stage
cp -R dist/ntfy-tray.app dmg-stage/
ln -sf /Applications dmg-stage/Applications
hdiutil create -volname "ntfy-tray" -srcfolder dmg-stage -ov -format UDZO "$DMG_NAME"

# Temizle
rm -rf dmg-stage

echo ""
echo "=== Tamamlandı ==="
echo "DMG: $(pwd)/$DMG_NAME"
echo "Boyut: $(du -h "$DMG_NAME" | cut -f1)"
