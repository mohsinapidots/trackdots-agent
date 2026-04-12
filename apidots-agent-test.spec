# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['agent/main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['Quartz', 'Quartz.CoreGraphics', 'Quartz.CoreGraphics._callbacks', 'Quartz.CoreGraphics._contextmanager', 'Quartz.CoreGraphics._coregraphics', 'Quartz.CoreGraphics._doubleindirect', 'Quartz.CoreGraphics._inlines', 'Quartz.CoreGraphics._metadata', 'Quartz.CoreGraphics._sortandmap'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='apidots-agent-test',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
