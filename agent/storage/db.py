import sqlite3 as sqlite
from agent.utils.logger import get_logger
from agent.storage.crypto import get_or_create_key
from agent.paths import DB_PATH, ensure_dirs

log = get_logger("db")


def get_conn():
    ensure_dirs()
    conn = sqlite.connect(str(DB_PATH))
    conn.row_factory = sqlite.Row
    cur = conn.cursor()

    key = get_or_create_key()

    cur.execute(f"PRAGMA key = '{key}';")
    cur.execute("PRAGMA cipher_compatibility = 4;")
    cur.execute("PRAGMA foreign_keys = ON;")

    cur.execute("PRAGMA cipher_version;")

    return conn

def init_db():
    # Auto-recover corrupt or encrypted DB
    if DB_PATH.exists():
        try:
            import sqlite3 as _test
            conn = _test.connect(str(DB_PATH))
            conn.execute("SELECT name FROM sqlite_master LIMIT 1")
            conn.close()
        except Exception:
            log.warning("Corrupt or incompatible database detected — recreating")
            DB_PATH.unlink()

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS activity_blocks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        block_uuid TEXT UNIQUE NOT NULL,
        start_ts REAL NOT NULL,
        end_ts REAL NOT NULL,
        idle INTEGER NOT NULL,
        keys INTEGER NOT NULL,
        mouse_clicks INTEGER NOT NULL,
        mouse_distance INTEGER NOT NULL,
        screenshot_path TEXT,
        primary_app TEXT,
        window_title TEXT,
        sync_status TEXT NOT NULL DEFAULT 'pending',
        created_at REAL NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS agent_state (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        paused INTEGER NOT NULL,
        pause_reason TEXT,
        updated_at REAL
    )
    """)

    cur.execute("""
    INSERT OR IGNORE INTO agent_state (id, paused, pause_reason, updated_at)
        VALUES (1, 0, NULL, strftime('%s','now'))
    """)

    # Schema migrations — add columns that may be missing in existing databases
    try:
        existing_cols = {row[1] for row in cur.execute("PRAGMA table_info(activity_blocks)")}
        if 'window_title' not in existing_cols:
            cur.execute("ALTER TABLE activity_blocks ADD COLUMN window_title TEXT")
            log.info("Migrated DB: added window_title column")
    except Exception as e:
        log.warning("Schema migration check failed: %s", e)

    conn.commit()
    conn.close()
    log.info("Database initialized")

def save_block(block: dict):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO activity_blocks (
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
        created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        block["block_uuid"],
        block["start"],
        block["end"],
        int(block["idle"]),
        block["keys"],
        block["mouse_clicks"],
        block["mouse_distance"],
        block.get("screenshot_path"),
        block["primary_app"],
        block.get("window_title"),
        block["created_at"]
    ))

    conn.commit()
    conn.close()

def get_pending_blocks(limit=10):
    conn = get_conn()
    cur = conn.cursor()

    # Ensure window_title column exists (safe migration for pre-existing DBs)
    try:
        existing_cols = {row[1] for row in cur.execute("PRAGMA table_info(activity_blocks)")}
        if 'window_title' not in existing_cols:
            cur.execute("ALTER TABLE activity_blocks ADD COLUMN window_title TEXT")
            conn.commit()
            log.info("Migrated DB: added window_title column (lazy)")
    except Exception:
        pass

    cur.execute(
        """
        SELECT
        id,
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
        created_at
        FROM activity_blocks
        WHERE sync_status = 'pending'
        ORDER BY start_ts
        LIMIT ?
        """,
        (limit,)
    )

    rows = cur.fetchall()
    conn.close()
    return rows


def mark_block_synced(block_uuid):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE activity_blocks
        SET sync_status = 'sent'
        WHERE block_uuid = ?
        """,
        (block_uuid,)
    )

    conn.commit()
    conn.close()

def count_pending_blocks():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM activity_blocks WHERE sync_status='pending'"
    )
    count = cur.fetchone()[0]
    conn.close()
    return count

def get_agent_state():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT paused, pause_reason FROM agent_state WHERE id = 1")
    paused, reason = cur.fetchone()
    conn.close()
    return bool(paused), reason


def set_agent_state(paused: bool, reason: str | None = None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE agent_state
        SET paused = ?, pause_reason = ?, updated_at = strftime('%s','now')
        WHERE id = 1
        """,
        (1 if paused else 0, reason),
    )
    conn.commit()
    conn.close()
