import platform
from agent.utils.logger import get_logger

log = get_logger("active_app")

# Sites whose window title reveals unproductive activity inside a browser
_BROWSER_BUNDLE_IDS = {
    'com.google.chrome', 'org.mozilla.firefox', 'com.apple.safari',
    'com.microsoft.edgemac', 'com.brave.browser', 'company.thebrowser.browser',  # Arc
    'chrome', 'firefox', 'msedge', 'brave', 'opera',
}

UNPRODUCTIVE_TITLE_KEYWORDS = [
    'youtube', 'netflix', 'twitch', 'tiktok', 'instagram', 'facebook',
    'twitter', 'x.com', 'reddit', 'hulu', 'disney+', 'prime video',
    'amazon prime', 'spotify', 'soundcloud', 'steam', 'epic games',
]

PRODUCTIVE_TITLE_KEYWORDS = [
    'github', 'gitlab', 'stackoverflow', 'google docs', 'google sheets',
    'notion', 'jira', 'confluence', 'linear', 'figma',
]


def classify_window_title(app_name, bundle_id, window_title):
    """
    If the active app is a browser, use the window title to refine
    the app name to the actual site being viewed.
    Returns the string to use as primary_app.
    """
    bid = (bundle_id or '').lower()
    name = (app_name or '').lower()

    is_browser = bid in _BROWSER_BUNDLE_IDS or name in {'chrome', 'firefox', 'safari', 'edge', 'brave', 'arc'}
    if not is_browser or not window_title:
        return app_name

    title_lower = window_title.lower()

    for kw in UNPRODUCTIVE_TITLE_KEYWORDS:
        if kw in title_lower:
            return kw  # e.g. "youtube" — matches UNPRODUCTIVE_APPS in scoring.py

    for kw in PRODUCTIVE_TITLE_KEYWORDS:
        if kw in title_lower:
            return kw  # e.g. "github" — treat as productive

    return app_name  # generic browser — scoring handles it


def get_active_app():
    try:
        if platform.system() == "Darwin":
            from AppKit import NSWorkspace
            app = NSWorkspace.sharedWorkspace().frontmostApplication()
            if not app:
                return None

            app_name  = app.localizedName()
            bundle_id = app.bundleIdentifier() or ''
            window_title = None

            bid = bundle_id.lower()
            is_browser = any(b in bid for b in ('chrome', 'firefox', 'safari', 'edge', 'brave', 'browser'))

            if is_browser:
                # Primary: Quartz CGWindowListCopyWindowInfo — reads the OS-level window
                # title directly (e.g. "YouTube — Mozilla Firefox"). Works for every
                # browser including Firefox without AppleScript permissions.
                try:
                    import Quartz
                    app_pid = app.processIdentifier()
                    wlist = Quartz.CGWindowListCopyWindowInfo(
                        Quartz.kCGWindowListOptionOnScreenOnly |
                        Quartz.kCGWindowListExcludeDesktopElements,
                        Quartz.kCGNullWindowID,
                    )
                    for w in (wlist or []):
                        if (w.get('kCGWindowOwnerPID') == app_pid and
                                w.get('kCGWindowLayer') == 0 and
                                w.get('kCGWindowName')):
                            window_title = w['kCGWindowName']
                            break
                except Exception:
                    pass

                # Fallback: AppleScript for Chrome/Safari/Edge/Brave (gives clean tab
                # title without the " — Browser Name" suffix).
                if not window_title:
                    try:
                        import subprocess
                        scripts = {
                            'chrome': 'tell application "Google Chrome" to get title of active tab of front window',
                            'safari': 'tell application "Safari" to get name of front document',
                            'edge':   'tell application "Microsoft Edge" to get title of active tab of front window',
                            'brave':  'tell application "Brave Browser" to get title of active tab of front window',
                        }
                        script = None
                        for key, s in scripts.items():
                            if key in bid:
                                script = s
                                break
                        if script:
                            r = subprocess.run(['osascript', '-e', script],
                                               capture_output=True, text=True, timeout=1)
                            if r.returncode == 0:
                                window_title = r.stdout.strip()
                    except Exception:
                        pass

            primary = classify_window_title(app_name, bundle_id, window_title)
            return {
                "name":         primary,
                "bundle_id":    bundle_id,
                "window_title": window_title,
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
            window_title = buf.value

            import psutil
            pid = ctypes.wintypes.DWORD()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            try:
                proc = psutil.Process(pid.value)
                app_name  = proc.name().replace('.exe', '')
                bundle_id = app_name.lower()
            except Exception:
                app_name  = window_title or "Unknown"
                bundle_id = app_name.lower()

            primary = classify_window_title(app_name, bundle_id, window_title)
            return {
                "name":         primary,
                "bundle_id":    bundle_id,
                "window_title": window_title,
            }

        else:
            # Linux fallback via xdotool
            import subprocess
            result = subprocess.run(
                ['xdotool', 'getactivewindow', 'getwindowname'],
                capture_output=True, text=True, timeout=2
            )
            window_title = result.stdout.strip() or "Unknown"
            primary = classify_window_title(window_title, window_title.lower(), window_title)
            return {"name": primary, "bundle_id": primary.lower(), "window_title": window_title}

    except Exception as e:
        log.debug("get_active_app failed: %s", e)
        return None
