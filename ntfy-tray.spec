# -*- mode: python -*-

import os
import platform

block_cipher = None

is_mac = platform.system() == "Darwin"
is_win = platform.system() == "Windows"

logo = "ntfy_tray/gui/images/ntfy.icns" if is_mac else "ntfy_tray/gui/images/ntfy.ico"

a = Analysis(
    ['ntfy_tray/__main__.py'],
    pathex=[os.getcwd()],
    binaries=[],
    datas=[
        ('ntfy_tray/gui/images', 'ntfy_tray/gui/images'),
        ('ntfy_tray/gui/themes', 'ntfy_tray/gui/themes'),
        ('ntfy_tray/gui/sounds', 'ntfy_tray/gui/sounds'),
    ],
    hiddenimports=['websocket', 'websocket._core', 'websocket._exceptions', 'objc', 'Foundation'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe_kwargs = {}
if is_win:
    exe_kwargs['version'] = 'version.py'

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ntfy-tray',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=logo,
    **exe_kwargs,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name='ntfy-tray',
)

if is_mac:
    app = BUNDLE(
        coll,
        name='ntfy-tray.app',
        icon=logo,
        bundle_identifier='com.ntfy-tray.app',
        info_plist={
            'NSHighResolutionCapable': True,
            'LSUIElement': True,
            'CFBundleShortVersionString': '1.0.0',
            'LSMinimumSystemVersion': '12.0',
        },
    )
