# -*- mode: python ; coding: utf-8 -*-
import glob
import os
import sys

# Explicitly collect all pyobjc Quartz .so extension files.
# PyInstaller's collect_all/collect_binaries misses these because pyobjc .so
# files are Python extension modules, not dynamic libraries, and need to be
# listed as binaries with their correct package destination path.
_site = os.path.join(os.path.dirname(SPEC), '.venv', 'lib', 'python3.14', 'site-packages')

quartz_binaries = []
for so in glob.glob(os.path.join(_site, 'Quartz', '**', '*.so'), recursive=True):
    rel  = os.path.relpath(so, _site)   # e.g. Quartz/CoreGraphics/_coregraphics.cpython-314-darwin.so
    dest = os.path.dirname(rel)          # e.g. Quartz/CoreGraphics
    quartz_binaries.append((so, dest))

a = Analysis(
    ['agent/main.py'],
    pathex=[],
    binaries=quartz_binaries,
    datas=[],
    hiddenimports=[
        'Quartz',
        'Quartz.CoreGraphics',
        'Quartz.CoreGraphics._callbacks',
        'Quartz.CoreGraphics._contextmanager',
        'Quartz.CoreGraphics._coregraphics',
        'Quartz.CoreGraphics._doubleindirect',
        'Quartz.CoreGraphics._inlines',
        'Quartz.CoreGraphics._metadata',
        'Quartz.CoreGraphics._sortandmap',
    ],
    hookspath=['hooks'],
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
    name='apidots-agent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch='arm64',
    codesign_identity=None,
    entitlements_file=None,
)
