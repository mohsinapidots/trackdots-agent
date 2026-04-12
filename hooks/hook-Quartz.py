"""
PyInstaller hook for pyobjc-framework-Quartz.

collect_all('Quartz') finds the Python modules but misses the .so extension
files because pyobjc uses an unusual package layout. This hook explicitly
walks the Quartz package and adds every .so file as a binary.
"""
import os
import glob
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = collect_all('Quartz')

# Manually collect all .so extension modules that collect_all misses
try:
    import Quartz as _q
    quartz_dir = os.path.dirname(_q.__file__)
    for so in glob.glob(os.path.join(quartz_dir, '**', '*.so'), recursive=True):
        dest = os.path.dirname(os.path.relpath(so, os.path.dirname(quartz_dir)))
        binaries.append((so, dest))
except ImportError:
    pass
