import os
import time
import requests
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[2] / '.env', override=False)
from agent.storage.db import get_pending_blocks, mark_block_synced
from agent.utils.logger import get_logger
from agent.sync.state import SyncState
from agent.sync.backoff import compute_backoff
from agent.security.keychain import get_device_token, get_user_session

log = get_logger("sync")

# --------------------------------------------------
# CONFIG
# --------------------------------------------------

API_BASE = os.getenv("APIDOTS_API_BASE", "http://127.0.0.1:8000")

INGEST_URL            = f"{API_BASE}/api/ingest/activity/"
SCREENSHOT_UPLOAD_URL = f"{API_BASE}/api/screenshots/upload/"
ASSIGN_USER_URL       = f"{API_BASE}/api/devices/assign-user/"
DEVICE_LOG_URL        = f"{API_BASE}/api/device/log/"

BATCH_SIZE = int(os.getenv("APIDOTS_BATCH_SIZE", "5"))
TIMEOUT = int(os.getenv("APIDOTS_TIMEOUT", "5"))

DEV_MODE = os.getenv("APIDOTS_DEV", "false") == "true"

sync_state = SyncState()



def iso(ts):
    if ts is None:
        return None
    if isinstance(ts, str):
        return ts
    return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()


def upload_screenshot(block_uuid, screenshot_path):
    if not screenshot_path:
        log.error("Screenshot path is EMPTY → upload skipped")
        return

    path = Path(screenshot_path)

    if not path.exists():
        raise RuntimeError(f"Screenshot missing on disk: {screenshot_path}")

    session = get_user_session()
    device_token = get_device_token()

    headers = {
        "Authorization": f"Bearer {session['access']}",
        "Accept-Encoding": "identity",
        "X-DEVICE-TOKEN": device_token,
    }

    url = f"{SCREENSHOT_UPLOAD_URL}{block_uuid}/"

    # Read bytes into memory first so the file handle is fully closed before
    # we call unlink() — on Windows the handle stays locked until GC otherwise.
    file_bytes = path.read_bytes()

    r = requests.post(
        url,
        headers=headers,
        files={"file": (path.name, file_bytes, "image/webp")},
        data={"block_uuid": block_uuid},
        timeout=15,
    )

    if r.status_code != 201:
        raise RuntimeError(
            f"Screenshot upload failed ({r.status_code}): {r.text}"
        )

    # Delete local file after successful upload
    import sys, time as _time
    for attempt in range(3):
        try:
            path.unlink(missing_ok=True)
            log.info("Deleted synced screenshot: %s", path.name)
            break
        except PermissionError:
            if sys.platform == "win32" and attempt < 2:
                _time.sleep(0.2)  # give Windows a moment to release any OS handles
            else:
                log.warning("Could not delete screenshot %s (PermissionError)", path.name)
                break
        except Exception as e:
            log.warning("Could not delete screenshot %s: %s", path.name, e)
            break


def report_sync_error(error_message: str, block_uuid: str = None, response_body: str = None):
    """Fire-and-forget: post a sync_error event to Device Logs on the server."""
    try:
        device_token = get_device_token()
        msg = f"Sync error: {error_message}"
        if block_uuid:
            msg += f" (block {block_uuid[:8]})"
        if response_body:
            # Include first 300 chars of server response so staff can diagnose 500s
            msg += f" | server: {response_body[:300]}"
        requests.post(
            DEVICE_LOG_URL,
            json={"event": "sync_error", "message": msg, "level": "error"},
            headers={"X-DEVICE-TOKEN": device_token},
            timeout=5,
        )
    except Exception:
        pass  # never interrupt the main loop over a logging call


def sync_device_user():
    """
    Re-associates the device with the currently logged-in user.
    Called every sync cycle so that when a different user logs in
    via the Electron app the device record is updated automatically
    within one sync interval rather than requiring re-registration.
    """
    try:
        device_token = get_device_token()
        session      = get_user_session()
        access       = session.get("access") if session else None
        if not access:
            log.debug("sync_device_user: no user session, skipping")
            return

        r = requests.post(
            ASSIGN_USER_URL,
            json={},
            headers={
                "Authorization": f"Bearer {access}",
                "X-DEVICE-TOKEN": device_token,
            },
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            data = r.json()
            if data.get("status") == "updated":
                log.info(
                    "Device re-assigned: %s → %s",
                    data.get("old_user"), data.get("new_user"),
                )
        else:
            log.warning("sync_device_user: unexpected response %s: %s", r.status_code, r.text)
    except Exception as e:
        log.debug("sync_device_user failed (non-fatal): %s", e)


def sync():
    if not sync_state.can_attempt():
        return

    blocks = get_pending_blocks(limit=BATCH_SIZE)
    if not blocks:
        return

    sync_state.record_attempt()

    for block in blocks:
        (
            _id,
            block_uuid,
            start_ts,
            end_ts,
            idle,
            keys,
            mouse_clicks,
            mouse_distance,
            screenshot_path,
            primary_app,
            window_title,
            sync_status,
            created_at,
        ) = block

        payload = {
            "block_uuid":    block_uuid,
            "start":         iso(start_ts),
            "end":           iso(end_ts),
            "idle":          bool(idle),
            "keys":          keys,
            "mouse_clicks":  mouse_clicks,
            "mouse_distance": mouse_distance,
            "primary_app":   primary_app,
            "window_title":  window_title,
            "created_at":    iso(created_at),
        }


        try:
            log.info(
                "Syncing block %s | app=%s | idle=%s | keys=%s | clicks=%s",
                block_uuid[:8], primary_app or "—", bool(idle), keys, mouse_clicks,
            )

            r = requests.post(
                INGEST_URL,
                json=payload,
                headers={"X-DEVICE-TOKEN": get_device_token()},
                timeout=TIMEOUT,
            )

            if r.status_code not in (200, 201):
                log.error("INGEST FAILED (%s): %s", r.status_code, r.text)
                r.raise_for_status()

            resp_json = r.json()
            if resp_json.get("status") == "skipped":
                log.info("Block %s skipped by server (overlap) — marking synced", block_uuid)
            else:
                upload_screenshot(block_uuid, screenshot_path)

            mark_block_synced(block_uuid)
            sync_state.record_success()

        # In agent/sync/client.py, find the except block inside sync()
        # and replace it with this:
        except Exception as e:
            # If device token rejected, clear it so agent re-registers on next cycle
            if hasattr(e, 'response') and e.response is not None:
                if e.response.status_code == 403:
                    log.warning("Device token rejected (403) — clearing for re-registration")
                    try:
                        from agent.security.keychain import delete_device_token
                        delete_device_token()
                    except Exception:
                        pass
            backoff = compute_backoff(sync_state.consecutive_failures + 1)
            sync_state.record_failure(backoff)
            log.warning("Sync error: %s", e)
            resp_body = None
            if hasattr(e, 'response') and e.response is not None:
                try:
                    resp_body = e.response.text
                except Exception:
                    pass
            report_sync_error(str(e), block_uuid, resp_body)
            break
