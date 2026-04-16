import logging
import sys
from logging.handlers import RotatingFileHandler
from agent.paths import LOGS_DIR, ensure_dirs

ensure_dirs()

LOG_FILE = LOGS_DIR / "agent.log"

def get_logger(name: str):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    # Prevent messages from propagating to the root logger, which may have
    # handlers that use the system default encoding (cp1252 on Windows).
    logger.propagate = False

    if not logger.handlers:
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
        try:
            handler = RotatingFileHandler(
                LOG_FILE,
                maxBytes=5_000_000,
                backupCount=3,
                encoding='utf-8',
                errors='replace',   # replace unencodable chars instead of crashing
            )
        except Exception:
            # Fall back to stderr if the log file can't be opened
            # (e.g. quarantine/permission issue on first launch)
            handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
