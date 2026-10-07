"""One call-site per command dispatch: a structured log line (A4) plus a
durable sqlite audit row (C2). Handlers call record() once they know the
outcome; nothing else should write to the audit db directly.
"""

import logging
import sqlite3
import time
from pathlib import Path

logger = logging.getLogger("hub.activity")

_DB_PATH = Path("./audit.sqlite3")
_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    user_id INTEGER NOT NULL,
    command TEXT NOT NULL,
    target TEXT,
    result TEXT NOT NULL
)
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.execute(_SCHEMA)
    return conn


def record(user_id: int, command: str, target: str | None, result: str) -> None:
    logger.info("user_id=%s command=%s target=%s result=%s", user_id, command, target, result)
    with _connect() as conn:
        conn.execute(
            "INSERT INTO audit_log (ts, user_id, command, target, result) VALUES (?, ?, ?, ?, ?)",
            (time.time(), user_id, command, target, result),
        )
