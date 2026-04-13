# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['agent/main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'pynput.keyboard._win32',
        'pynput.mouse._win32',
        'pynput._util.win32',
        'mss',
        'mss.windows',
        'pkg_resources.py2_warn',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['AppKit', 'Quartz', 'pyobjc'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='apidots-agent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
