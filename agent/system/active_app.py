import platform
from agent.utils.logger import get_logger

log = get_logger("active_app")

def get_active_app():
    try:
        if platform.system() == "Darwin":
            from AppKit import NSWorkspace
            app = NSWorkspace.sharedWorkspace().frontmostApplication()
            if not app:
                return None
            return {
                "name": app.localizedName(),
                "bundle_id": app.bundleIdentifier()
            }

        elif platform.system() == "Windows":
            import ctypes
            import ctypes.wintypes
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            if not hwnd:
                return None
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value

            import psutil
            pid = ctypes.wintypes.DWORD()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            try:
                proc = psutil.Process(pid.value)
                name = proc.name().replace('.exe', '')
            except Exception:
                name = title or "Unknown"
            return {"name": name, "bundle_id": name.lower()}

        else:
            # Linux fallback via xdotool
            import subprocess
            result = subprocess.run(
                ['xdotool', 'getactivewindow', 'getwindowname'],
                capture_output=True, text=True, timeout=2
            )
            name = result.stdout.strip() or "Unknown"
            return {"name": name, "bundle_id": name.lower()}

    except Exception as e:
        log.debug("get_active_app failed: %s", e)
        return None
