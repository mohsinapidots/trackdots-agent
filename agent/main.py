import time
import os
import sys
import json
import signal
from pathlib import Path

# ── Bootstrap dirs & crash log FIRST ─────────────────────────────────────────
# Use raw stdlib only — no agent imports — so this runs even if imports fail.
# This ensures ~/.TrackDots/logs/ and data/ always exist, giving us a place
# to write crash output before anything else.
_BASE = Path(os.environ.get('TRACKDOTS_DIR', str(Path.home() / '.TrackDots')))
for _d in (_BASE, _BASE / 'logs', _BASE / 'screenshots', _BASE / 'data'):
    try:
        _d.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

# Redirect stderr to the log file immediately so any import crash is captured
try:
    _crash_log = open(_BASE / 'logs' / 'agent.log', 'a', buffering=1, encoding='utf-8', errors='replace')
    sys.stderr = _crash_log
except Exception:
    pass
# ─────────────────────────────────────────────────────────────────────────────

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
from agent.bootstrap import ensure_device_registered
from agent.storage.db import init_db, save_block, get_agent_state
from agent.activity.keyboard import KeyboardTracker
from agent.activity.mouse import MouseTracker
from agent.activity.block import ActivityBlock
from agent.utils.logger import get_logger
from agent.sync.client import sync, sync_device_user
from agent.permissions import ensure_input_monitoring
from agent.paths import STATE_FILE, BASE_DIR, PERM_WARNING, migrate_old_dirs, ensure_dirs

# --------------------------------------------------
# CONFIG (env overridable)
# --------------------------------------------------
BLOCK_DURATION   = int(os.getenv("APIDOTS_BLOCK_DURATION", "600"))  # seconds
TICK             = int(os.getenv("APIDOTS_TICK", "10"))              # seconds
SYNC_INTERVAL    = int(os.getenv("APIDOTS_SYNC_INTERVAL", "180"))   # seconds
CLEANUP_INTERVAL = 86400                                             # daily

log = get_logger("agent")


def _cleanup_old_files():
    """Delete screenshots and log backups older than 7 days."""
    cutoff = time.time() - 7 * 86400
    from agent.paths import SCREENSHOTS_DIR, LOGS_DIR
    screenshot_dir = SCREENSHOTS_DIR
    if screenshot_dir.exists():
        for f in screenshot_dir.iterdir():
            if f.is_file() and f.stat().st_mtime < cutoff:
                try:
                    f.unlink()
                    log.info("Cleanup: removed old screenshot %s", f.name)
                except Exception as e:
                    log.warning("Cleanup: could not remove %s: %s", f.name, e)

    log_dir = LOGS_DIR
    if log_dir.exists():
        for f in log_dir.iterdir():
            if f.is_file() and f.name != "agent.log" and f.stat().st_mtime < cutoff:
                try:
                    f.unlink()
                    log.info("Cleanup: removed old log %s", f.name)
                except Exception as e:
                    log.warning("Cleanup: could not remove %s: %s", f.name, e)


def get_electron_state():
    """Read pause/tracking state written by Electron app."""
    try:
        if STATE_FILE.exists():
            data = json.loads(STATE_FILE.read_text())
            return data.get("state")
    except Exception:
        pass
    return None


def is_paused():
    """
    Check pause state from BOTH sources:
    - ~/.apidots/state.json  (written by Electron UI)
    - DB agent state         (written by backend ingest response)
    Either one being paused = paused.
    """
    electron_state = get_electron_state()
    if electron_state in ("paused", "idle"):
        return True
    db_paused, _ = get_agent_state()
    return bool(db_paused)


def register_with_retry():
    """
    Attempt device registration, retrying every 30s until success.
    Clears stale token first if it exists, so a deleted device
    always triggers a fresh registration.
    """
    while True:
        try:
            token = ensure_device_registered()
            log.info("Device registered successfully")
            return token
        except Exception as e:
            log.error("Device registration failed: %s — retrying in 30s", e)
            # If 401/403, clear the stale token so next attempt re-registers fresh
            if hasattr(e, 'response') and e.response is not None:
                if e.response.status_code in (401, 403):
                    log.warning("Clearing stale device token for re-registration")
                    try:
                        from agent.security.keychain import delete_device_token
                        delete_device_token()
                    except Exception:
                        pass
            time.sleep(30)


def main():
    # Migrate from old dirs (.trackdots / .mac_tracker) on first run
    migrate_old_dirs()
    ensure_dirs()

    init_db()

    # On macOS: request Input Monitoring permission for this process.
    # pynput silently returns 0 events if this is not granted.
    ensure_input_monitoring()

    # Register device — retries automatically if token is missing or rejected
    register_with_retry()

    log.info(
        "Agent starting (BLOCK_DURATION=%ss, TICK=%ss)",
        BLOCK_DURATION,
        TICK,
    )

    # Write actual Python PID so Electron's killAgent() targets this process
    # directly, not the PyInstaller bootloader that spawned us.
    from agent.paths import AGENT_PID
    try:
        AGENT_PID.write_text(str(os.getpid()))
    except Exception:
        pass

    # SIGTERM (sent by Electron on quit/logout) bypasses try/finally by default.
    # Convert it to SystemExit so the finally flush block runs cleanly.
    def _handle_sigterm(signum, frame):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, _handle_sigterm)

    kb    = KeyboardTracker()
    mouse = MouseTracker()
    kb.start()
    mouse.start()

    block        = ActivityBlock(start_ts=time.time())
    block_start  = time.time()
    last_sync    = time.time()
    last_cleanup = time.time()
    was_paused   = False

    from agent.paths import SHUTDOWN_FLAG
    # Clear any stale flag from a previous run
    try:
        SHUTDOWN_FLAG.unlink(missing_ok=True)
    except Exception:
        pass

    try:
     while True:
      try:
        time.sleep(TICK)
        now = time.time()

        # Check for shutdown flag written by Electron on quit/logout.
        # More reliable than SIGTERM which only hits the PyInstaller bootloader.
        if SHUTDOWN_FLAG.exists():
            log.info("Shutdown flag detected — flushing and exiting")
            raise SystemExit(0)

        paused = is_paused()

        # --------------------------------------------------
        # PAUSE / RESUME HANDLING
        # --------------------------------------------------
        if paused:
            if not was_paused:
                log.info("Pause detected (from Electron or backend), finalizing block")
                if block:
                    data = block.finalize()
                    save_block(data)
                    log.info("Block finalized on pause")
                block       = None
                block_start = None
                was_paused  = True
            kb.reset()
            mouse.reset()
            continue

        if was_paused and not paused:
            log.info("Resume detected, starting new block")
            block       = ActivityBlock(start_ts=now)
            block_start = now
            was_paused  = False

        # --------------------------------------------------
        # ACTIVITY AGGREGATION
        # --------------------------------------------------
        if block:
            block.add_activity(
                keys=kb.reset(),
                mouse=mouse.reset(),
            )
        else:
            kb.reset()
            mouse.reset()

        # --------------------------------------------------
        # BLOCK FINALIZATION
        # --------------------------------------------------
        DEV_MODE = os.getenv("APIDOTS_DEV", "false") == "true"
        if block and now - block_start >= BLOCK_DURATION:
            data = block.finalize()
            save_block(data)
            log.info("Activity block finalized")

            if DEV_MODE:
                log.info("DEV MODE → instant sync")
                sync()
                
            block       = ActivityBlock(start_ts=now)
            block_start = now

            # ── Permission detection ─────────────────────────────────────
            # Only the real tracking agent (non-System-Settings primary app)
            # should manage the warning file.  The secondary agent always
            # reports System Settings with zero input — ignore it here so
            # the two agents don't race each other on this file.
            primary_app = data.get("primary_app") or ""
            is_secondary_agent = primary_app.lower() == "system settings"

            if not is_secondary_agent:
                pf = PERM_WARNING
                if data.get("keys", 0) == 0 and data.get("mouse_clicks", 0) == 0:
                    try:
                        cur_count = json.loads(pf.read_text()).get("count", 0) if pf.exists() else 0
                    except Exception:
                        cur_count = 0
                    pf.write_text(json.dumps({"type": "input_monitoring", "count": cur_count + 1, "ts": str(now)}))
                    log.warning("Zero input detected — possible missing Input Monitoring permission (%d blocks)", cur_count + 1)
                else:
                    if pf.exists():
                        pf.unlink()
            # ─────────────────────────────────────────────────────────────

        # --------------------------------------------------
        # BACKGROUND SYNC
        # --------------------------------------------------
        if now - last_sync >= SYNC_INTERVAL:
            log.info("Running sync")
            sync_device_user()
            sync()
            last_sync = now

            # After sync, check if token was cleared by a 403 and re-register
            try:
                from agent.security.keychain import get_device_token
                get_device_token()
            except RuntimeError:
                log.warning("Device token missing after sync — re-registering")
                register_with_retry()

        # --------------------------------------------------
        # DAILY CLEANUP
        # --------------------------------------------------
        if now - last_cleanup >= CLEANUP_INTERVAL:
            log.info("Running cleanup")
            _cleanup_old_files()
            last_cleanup = now

      except Exception as e:
        log.error("Main loop error (will retry): %s", e, exc_info=True)

    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        # Finalize and sync the current in-progress block before exit so that
        # logout / quit / SIGTERM don't silently lose the last few minutes.
        try:
            if block is not None:
                data = block.finalize()
                save_block(data)
                log.info("Shutdown: block finalized (%s keys, %s clicks)",
                         data.get("keys", 0), data.get("mouse_clicks", 0))
            sync()
            log.info("Shutdown: final sync completed")
        except Exception as e:
            log.error("Shutdown flush failed: %s", e)
        try:
            from agent.paths import AGENT_PID, SHUTDOWN_FLAG
            AGENT_PID.unlink(missing_ok=True)
            SHUTDOWN_FLAG.unlink(missing_ok=True)
        except Exception:
            pass


if __name__ == "__main__":
    main()