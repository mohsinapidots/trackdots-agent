"""
File-based credential store.
All paths come from agent.paths — single source of truth.
"""
import json
import os
from agent.paths import BASE_DIR, SESSION_FILE, DEVICE_TOKEN, CREDENTIALS_FILE, ensure_dirs


def get_device_token() -> str:
    if not DEVICE_TOKEN.exists():
        raise RuntimeError(
            "Device token not found. "
            "Please log in via the TrackDots app."
        )
    return DEVICE_TOKEN.read_text().strip()


def set_device_token(token: str):
    ensure_dirs()
    DEVICE_TOKEN.write_text(token)
    DEVICE_TOKEN.chmod(0o600)


def delete_device_token():
    if DEVICE_TOKEN.exists():
        DEVICE_TOKEN.unlink()


def set_user_session(access: str, refresh: str):
    ensure_dirs()
    SESSION_FILE.write_text(
        json.dumps({'access': access, 'refresh': refresh}, indent=2)
    )
    SESSION_FILE.chmod(0o600)


def get_user_session() -> dict:
    if not SESSION_FILE.exists():
        return {'access': None, 'refresh': None}
    try:
        return json.loads(SESSION_FILE.read_text())
    except Exception:
        return {'access': None, 'refresh': None}


def clear_user_session():
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()


def save_credentials(username: str, password: str):
    ensure_dirs()
    CREDENTIALS_FILE.write_text(
        json.dumps({'username': username, 'password': password}, indent=2)
    )
    CREDENTIALS_FILE.chmod(0o600)


def get_credentials() -> dict:
    if not CREDENTIALS_FILE.exists():
        return {}
    try:
        return json.loads(CREDENTIALS_FILE.read_text())
    except Exception:
        return {}


def clear_credentials():
    if CREDENTIALS_FILE.exists():
        CREDENTIALS_FILE.unlink()
