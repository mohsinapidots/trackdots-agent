import os
import secrets
from agent.paths import CRYPTO_KEY, ensure_dirs

def get_or_create_key() -> str:
    ensure_dirs()
    if CRYPTO_KEY.exists():
        return CRYPTO_KEY.read_text()
    key = secrets.token_hex(32)
    CRYPTO_KEY.write_text(key)
    os.chmod(CRYPTO_KEY, 0o600)
    return key
