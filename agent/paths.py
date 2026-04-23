"""
Single source of truth for all TrackDots filesystem paths.

All agent modules import from here instead of defining their own paths.
The base dir can be overridden with the TRACKDOTS_DIR environment variable.
"""
import os
from pathlib import Path

BASE_DIR = Path(os.environ.get('TRACKDOTS_DIR', str(Path.home() / '.TrackDots')))

# --- subdirectories ---
LOGS_DIR        = BASE_DIR / 'logs'
SCREENSHOTS_DIR = BASE_DIR / 'screenshots'
DATA_DIR        = BASE_DIR / 'data'

# --- files ---
SESSION_FILE    = BASE_DIR / 'session.json'
CREDENTIALS_FILE = BASE_DIR / 'credentials.json'
STATE_FILE      = BASE_DIR / 'state.json'
DEVICE_TOKEN    = BASE_DIR / 'device_token'
AGENT_PID       = BASE_DIR / 'agent.pid'
SHUTDOWN_FLAG   = BASE_DIR / 'shutdown_flag'
AGENT_LOG       = LOGS_DIR / 'agent.log'
DB_PATH         = DATA_DIR / 'activity.db'
CRYPTO_KEY      = DATA_DIR / '.key'
PERM_STATUS     = BASE_DIR / 'perm_input_status.json'
PERM_WARNING    = BASE_DIR / 'permissions_warning.json'
CURRENT_TASK    = BASE_DIR / 'current_task.txt'


def ensure_dirs():
    """Create all required directories on first use."""
    for d in (BASE_DIR, LOGS_DIR, SCREENSHOTS_DIR, DATA_DIR):
        d.mkdir(parents=True, exist_ok=True)


def migrate_old_dirs():
    """
    One-time migration from old split layout (.trackdots + .mac_tracker)
    into the new unified .TrackDots layout.
    Only copies files that don't already exist at the new location.
    """
    old_trackdots = Path.home() / '.trackdots'
    old_mac       = Path.home() / '.mac_tracker'

    if not BASE_DIR.exists():
        ensure_dirs()

    # Copy session & device token (critical — user stays logged in)
    for fname in ('session.json', 'device_token', 'state.json'):
        src = old_trackdots / fname
        dst = BASE_DIR / fname
        if src.exists() and not dst.exists():
            import shutil
            shutil.copy2(src, dst)

    # Copy database
    src = old_mac / 'activity.db'
    if src.exists() and not DB_PATH.exists():
        import shutil
        shutil.copy2(src, DATA_DIR / 'activity.db')

    # Copy crypto key
    src = old_mac / '.key'
    if src.exists() and not CRYPTO_KEY.exists():
        import shutil
        shutil.copy2(src, CRYPTO_KEY)
