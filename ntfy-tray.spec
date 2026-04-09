# -*- mode: python -*-

import os
import platform
import certifi

# Read version from single source of truth
import sys
sys.path.insert(0, os.getcwd())
from ntfy_tray.__version__ import __version__

# Auto-generate version.txt for Inno Setup
with open("version.txt", "w") as _f:
    _f.write(__version__)

# Auto-generate version.py for PyInstaller Windows EXE metadata
_ver_tuple = tuple(int(x) for x in __version__.split(".")) + (0,) * (4 - len(__version__.split(".")))
with open("version.py", "w") as _f:
    _f.write(f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={_ver_tuple},
    prodvers={_ver_tuple},
    mask=0x3F, flags=0x0, OS=0x4,
    fileType=0x1, subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(u"040904B0", [
        StringStruct(u"Comments", u"ntfy Tray"),
        StringStruct(u"CompanyName", u""),
        StringStruct(u"FileDescription", u"ntfy Tray"),
        StringStruct(u"FileVersion", u"{__version__}"),
        StringStruct(u"InternalName", u"ntfy-tray"),
        StringStruct(u"LegalCopyright", u""),
        StringStruct(u"OriginalFilename", u"ntfy-tray.exe"),
        StringStruct(u"ProductName", u"ntfy Tray"),
        StringStruct(u"ProductVersion", u"{__version__}"),
      ])
    ]),
    VarFileInfo([VarStruct(u"Translation", [0, 1200])])
  ]
)
""")

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
        ('ntfy_tray/translations', 'ntfy_tray/translations'),
        (certifi.where(), 'certifi'),
    ],
    hiddenimports=[
        'websocket', 'websocket._core', 'websocket._exceptions',
        'objc', 'Foundation', 'UserNotifications',
    ],
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
            'CFBundleName': 'NTFY Tray',
            'CFBundleDisplayName': 'NTFY Tray',
            'NSHighResolutionCapable': True,
            'LSUIElement': True,
            'CFBundleShortVersionString': __version__,
            'LSMinimumSystemVersion': '12.0',
            'NSPrincipalClass': 'NSApplication',
            'CFBundleDocumentTypes': [
                {
                    'CFBundleTypeName': 'ntfy Tray Configuration',
                    'CFBundleTypeExtensions': ['ntfy'],
                    'CFBundleTypeRole': 'Editor',
                    'LSHandlerRank': 'Owner',
                }
            ],
            'UTExportedTypeDeclarations': [
                {
                    'UTTypeIdentifier': 'com.ntfy-tray.config',
                    'UTTypeDescription': 'ntfy Tray Configuration',
                    'UTTypeConformsTo': ['public.json'],
                    'UTTypeTagSpecification': {
                        'public.filename-extension': ['ntfy'],
                    },
                }
            ],
        },
    )
