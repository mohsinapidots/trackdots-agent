import platform
from agent.utils.logger import get_logger

log = get_logger("idle")

def get_idle_seconds() -> float:
    try:
        if platform.system() == "Darwin":
            import Quartz
            return Quartz.CGEventSourceSecondsSinceLastEventType(
                Quartz.kCGEventSourceStateCombinedSessionState,
                Quartz.kCGAnyInputEventType
            )

        elif platform.system() == "Windows":
            import ctypes
            class LASTINPUTINFO(ctypes.Structure):
                _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
            lii = LASTINPUTINFO()
            lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
            ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
            millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
            return millis / 1000.0

        else:
            # Linux: use xprintidle if available
            import subprocess
            result = subprocess.run(['xprintidle'], capture_output=True, text=True, timeout=2)
            return int(result.stdout.strip()) / 1000.0

    except Exception as e:
        log.debug("get_idle_seconds failed: %s", e)
        return 0.0
