"""
macOS permission helpers for the agent process.

The agent binary runs as a separate process from the Electron app, so it
needs its own Input Monitoring (kIOHIDRequestTypeListenEvent) grant in
System Preferences. This module requests that permission on first run and
writes a status file that Electron can read to guide the user if denied.
"""
import json
import platform
import time
from agent.paths import PERM_STATUS, ensure_dirs


def _write_status(status: str):
    try:
        ensure_dirs()
        PERM_STATUS.write_text(json.dumps({"status": status, "ts": time.time()}))
    except Exception:
        pass


def ensure_input_monitoring() -> bool:
    """
    Check and request Input Monitoring permission for this process on macOS.

    Returns True if granted (or non-macOS).
    Writes ~/.trackdots/perm_input_status.json with 'granted'/'denied'/'requested'
    so the Electron app can detect the state and guide the user.

    Status values:
      granted     - permission is active, pynput will work
      requested   - system dialog was shown, waiting for user decision
      denied      - user previously denied; must re-enable manually in Settings
    """
    if platform.system() != "Darwin":
        return True

    try:
        import ctypes

        IOKit = ctypes.CDLL("/System/Library/Frameworks/IOKit.framework/IOKit")
        IOKit.IOHIDCheckAccess.restype = ctypes.c_uint32
        IOKit.IOHIDCheckAccess.argtypes = [ctypes.c_uint32]
        IOKit.IOHIDRequestAccess.restype = ctypes.c_bool
        IOKit.IOHIDRequestAccess.argtypes = [ctypes.c_uint32]

        # kIOHIDRequestTypeListenEvent = 1  (Input Monitoring)
        kListen = ctypes.c_uint32(1)

        status = IOKit.IOHIDCheckAccess(kListen)
        # 0 = granted, 1 = denied, 2 = not_determined

        if status == 0:
            _write_status("granted")
            return True

        if status == 2:
            # Not determined yet — show the system consent dialog.
            # This can only be shown once; after that the user must go to Settings.
            granted = bool(IOKit.IOHIDRequestAccess(kListen))
            _write_status("granted" if granted else "denied")
            return granted

        # status == 1: explicitly denied
        _write_status("denied")
        return False

    except Exception:
        # Don't block agent startup if we can't load IOKit
        return True
