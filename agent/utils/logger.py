import logging
import sys
from logging.handlers import RotatingFileHandler
from agent.paths import LOGS_DIR, ensure_dirs

ensure_dirs()

LOG_FILE = LOGS_DIR / "agent.log"


class _SafeRotatingFileHandler(RotatingFileHandler):
    """RotatingFileHandler that skips rotation when the log file is locked.

    On Windows, renaming an open file raises PermissionError (WinError 32).
    This happens when a user has agent.log open in Notepad or another editor
    while the handler tries to rotate. Skipping the rotation is safer than
    filling stderr with 'Logging error' tracebacks on every log line.
    """
    def doRollover(self):
        try:
            super().doRollover()
        except PermissionError:
            pass  # file locked by another process — keep writing to current log


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
            handler = _SafeRotatingFileHandler(
                LOG_FILE,
                maxBytes=5_000_000,
                backupCount=3,
                encoding='utf-8',
                errors='replace',
            )
        except Exception:
            handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
