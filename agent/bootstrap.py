import json
import os
import platform
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / '.env', override=False)
from agent.security.keychain import (
    get_device_token,
    set_device_token,
)
from agent.paths import SESSION_FILE

API_BASE     = os.getenv("APIDOTS_API_BASE", "http://127.0.0.1:8000")
REGISTER_URL = f"{API_BASE}/api/devices/register/"

def get_electron_session():
    """Read JWT written by Electron app after login."""
    if not SESSION_FILE.exists():
        return None
    try:
        data = json.loads(SESSION_FILE.read_text(encoding='utf-8'))
        return data.get("access")
    except Exception:
        return None

def ensure_device_registered():
    # Already registered — return existing token
    try:
        return get_device_token()
    except RuntimeError:
        pass

    # Get JWT — try file written by Electron, then keychain fallback
    access_token = get_electron_session()

    # Also try keychain as fallback (in case agent logged in separately)
    if not access_token:
        try:
            from agent.security.keychain import get_user_session
            session = get_user_session()
            access_token = session.get("access")
        except Exception:
            pass

    if not access_token:
        raise RuntimeError(
            "No user session found. Please log in via the ApiDots Tracker app first.\n"
            f"Expected session file at: {SESSION_FILE}"
        )

    headers = {"Authorization": f"Bearer {access_token}"}
    payload = {
        "hostname":    platform.node(),
        "os":          platform.system(),
        "app_version": "1.0.0",
    }

    r = requests.post(REGISTER_URL, json=payload, headers=headers, timeout=10)
    r.raise_for_status()

    data  = r.json()
    token = data.get("device_token") or data.get("api_token")
    set_device_token(token)
    return token