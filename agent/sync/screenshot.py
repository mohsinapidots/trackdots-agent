import requests
from pathlib import Path

from agent.security.keychain import get_device_token, get_user_session
from agent.utils.logger import get_logger

log = get_logger("sync")

API_BASE = "http://127.0.0.1:8000"


def upload_screenshot(block_uuid: str, screenshot_path: str):
    if not screenshot_path:
        log.warning("No screenshot path for block %s", block_uuid)
        return

    path = Path(screenshot_path)

    log.warning("SYNC LOOKING FOR: %s", path)

    if not path.exists():
        log.error("Screenshot file missing: %s", path)
        return

    session = get_user_session()
    device_token = get_device_token()

    headers = {
        "Authorization": f"Bearer {session['access']}",
        "X-DEVICE-TOKEN": device_token,
    }

    with open(path, "rb") as f:
        r = requests.post(
            f"{API_BASE}/api/screenshots/upload/{block_uuid}/",
            headers=headers,
            files={"file": f},
            data={"block_uuid": block_uuid},
            timeout=15,
        )

    if r.status_code != 201:
        raise RuntimeError(
            f"Screenshot upload failed ({r.status_code}): {r.text}"
        )

    log.info("Screenshot uploaded for block %s", block_uuid)
