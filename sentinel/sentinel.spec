# PyInstaller spec for Sentinel.
# Build with:  pyinstaller sentinel.spec
# Produces:    dist/Sentinel/Sentinel.exe  (onedir; more reliable for PySide6 than onefile)

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('config/default_config.json', 'config'),
    ],
    hiddenimports=[
        'win10toast',
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

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Sentinel',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # no console window -- this is a GUI app
    icon=None,               # point this at resources/sentinel.ico if you add one
    uac_admin=False,          # request elevation only when a specific action needs it,
                                # not for the whole process at launch
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name='Sentinel',
)
