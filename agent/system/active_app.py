import platform
import subprocess
import ctypes
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

# AppleScript to get the active tab/window title for each browser.
# Firefox does not expose tabs via its own AppleScript dictionary, so we use
# System Events (Accessibility API) which works for any app and requires no
# extra Python packages — osascript is always available on macOS.
_BROWSER_SCRIPTS = {
    'chrome':   'tell application "Google Chrome" to get title of active tab of front window',
    'safari':   'tell application "Safari" to get name of front document',
    'edge':     'tell application "Microsoft Edge" to get title of active tab of front window',
    'brave':    'tell application "Brave Browser" to get title of active tab of front window',
    'firefox':  'tell application "System Events" to tell process "Firefox" to get title of front window',
    'arc':      'tell application "Arc" to get title of active tab of front window',
}


def _get_browser_title(bid):
    """Run the appropriate AppleScript for the frontmost browser and return its window title."""
    script = None
    for key, s in _BROWSER_SCRIPTS.items():
        if key in bid:
            script = s
            break
    if not script:
        return None
    try:
        r = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True, text=True, timeout=2,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass
    return None


def classify_window_title(app_name, bundle_id, window_title):
    """
    If the active app is a browser, use the window title to refine
    the app name to the actual site being viewed.
    Returns the string to use as primary_app.
    """
    bid  = (bundle_id or '').lower()
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




def _get_frontmost_window():
    """
    Returns (owner_name, pid, title) of the true frontmost window using
    CGWindowListCopyWindowInfo. The list is ordered front-to-back so the
    first layer-0 window with a non-empty name is the active window.

    More reliable than NSWorkspace.frontmostApplication() for browsers like
    Firefox that don't always update the NSWorkspace frontmost app correctly.
    """
    try:
        CF = ctypes.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
        CG = ctypes.CDLL('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')

        kCFStringEncodingUTF8  = 0x08000100
        kCFNumberSInt32Type    = 3

        CG.CGWindowListCopyWindowInfo.restype  = ctypes.c_void_p
        CG.CGWindowListCopyWindowInfo.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
        CF.CFArrayGetCount.restype             = ctypes.c_long
        CF.CFArrayGetCount.argtypes            = [ctypes.c_void_p]
        CF.CFArrayGetValueAtIndex.restype      = ctypes.c_void_p
        CF.CFArrayGetValueAtIndex.argtypes     = [ctypes.c_void_p, ctypes.c_long]
        CF.CFDictionaryGetValue.restype        = ctypes.c_void_p
        CF.CFDictionaryGetValue.argtypes       = [ctypes.c_void_p, ctypes.c_void_p]
        CF.CFNumberGetValue.restype            = ctypes.c_bool
        CF.CFNumberGetValue.argtypes           = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
        CF.CFStringGetCString.restype          = ctypes.c_bool
        CF.CFStringGetCString.argtypes         = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32]
        CF.CFStringCreateWithCString.restype   = ctypes.c_void_p
        CF.CFStringCreateWithCString.argtypes  = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
        CF.CFRelease.restype                   = None
        CF.CFRelease.argtypes                  = [ctypes.c_void_p]

        def _cfstr(s):
            return CF.CFStringCreateWithCString(None, s.encode('utf-8'), kCFStringEncodingUTF8)

        def _str(ref):
            if not ref:
                return None
            buf = ctypes.create_string_buffer(1024)
            return buf.value.decode('utf-8', errors='replace') if CF.CFStringGetCString(ref, buf, 1024, kCFStringEncodingUTF8) else None

        key_pid   = _cfstr('kCGWindowOwnerPID')
        key_layer = _cfstr('kCGWindowLayer')
        key_name  = _cfstr('kCGWindowName')
        key_owner = _cfstr('kCGWindowOwnerName')

        arr = CG.CGWindowListCopyWindowInfo(1 | 16, 0)  # OnScreen | ExcludeDesktop
        if not arr:
            return None, None, None

        # Pass 1: identify the frontmost owner from the first layer-0 window
        frontmost_owner = None
        frontmost_pid   = 0
        count = CF.CFArrayGetCount(arr)
        for i in range(count):
            w = CF.CFArrayGetValueAtIndex(arr, i)
            if not w:
                continue
            layer_ref = CF.CFDictionaryGetValue(w, key_layer)
            layer_val = ctypes.c_int32(0)
            if layer_ref:
                CF.CFNumberGetValue(layer_ref, kCFNumberSInt32Type, ctypes.byref(layer_val))
            if layer_val.value != 0:
                continue
            owner = _str(CF.CFDictionaryGetValue(w, key_owner))
            if owner:
                pid_ref = CF.CFDictionaryGetValue(w, key_pid)
                pid_val = ctypes.c_int32(0)
                if pid_ref:
                    CF.CFNumberGetValue(pid_ref, kCFNumberSInt32Type, ctypes.byref(pid_val))
                frontmost_owner = owner
                frontmost_pid   = pid_val.value
                break

        # Pass 2: find the first window belonging to that owner that has a title.
        # Firefox's first layer-0 window is often a chrome/toolbar window with no
        # kCGWindowName — the content window (with the page title) comes later.
        result = frontmost_owner, frontmost_pid, None
        if frontmost_owner:
            for i in range(count):
                w = CF.CFArrayGetValueAtIndex(arr, i)
                if not w:
                    continue
                owner = _str(CF.CFDictionaryGetValue(w, key_owner))
                if not owner or owner != frontmost_owner:
                    continue
                title = _str(CF.CFDictionaryGetValue(w, key_name))
                if title:
                    result = frontmost_owner, frontmost_pid, title
                    break

        CF.CFRelease(arr)
        CF.CFRelease(key_pid)
        CF.CFRelease(key_layer)
        CF.CFRelease(key_name)
        CF.CFRelease(key_owner)
        return result
    except Exception:
        return None, None, None


def get_active_app():
    try:
        if platform.system() == "Darwin":
            from AppKit import NSWorkspace, NSRunningApplication

            # Use window list order for frontmost app — more reliable than
            # NSWorkspace.frontmostApplication() which Firefox doesn't update correctly.
            owner_name, owner_pid, window_title = _get_frontmost_window()

            if owner_name:
                # Find the NSRunningApplication for this owner to get bundle_id.
                # Match by PID first; if not found (Firefox child process has a
                # different PID than the main app), fall back to matching by name.
                running = NSWorkspace.sharedWorkspace().runningApplications()
                bundle_id = ''
                app_name  = owner_name
                for a in running:
                    if a.processIdentifier() == owner_pid:
                        bundle_id = a.bundleIdentifier() or ''
                        app_name  = a.localizedName() or owner_name
                        break
                if not bundle_id:
                    # PID not found — match by localizedName (covers Firefox child procs)
                    for a in running:
                        if (a.localizedName() or '').lower() == owner_name.lower():
                            bundle_id = a.bundleIdentifier() or ''
                            app_name  = a.localizedName() or owner_name
                            break
            else:
                # Fallback to NSWorkspace
                app = NSWorkspace.sharedWorkspace().frontmostApplication()
                if not app:
                    return None
                app_name     = app.localizedName()
                bundle_id    = app.bundleIdentifier() or ''
                window_title = None
                owner_pid    = app.processIdentifier()

            bid = bundle_id.lower()
            is_browser = any(b in bid for b in ('chrome', 'firefox', 'safari', 'edge', 'brave', 'browser'))

            if is_browser and not window_title:
                # Window title already comes from _get_frontmost_window for most cases.
                # Fallback: AppleScript for Chrome/Safari/Edge/Brave
                window_title = _get_browser_title(bid)

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
