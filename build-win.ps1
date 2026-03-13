echo "Creating executable"


try {C:/Python39/Scripts/pyinstaller ntfy-tray.spec}
catch {pyinstaller ntfy-tray.spec}

echo "Creating installer"
iscc ntfy-tray.iss
