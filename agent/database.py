"""SQLite storage for processed calls."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional, Sequence

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    source TEXT DEFAULT 'unknown',
    caller_name TEXT,
    callback_number TEXT,
    intent_type TEXT,
    course_interest TEXT,
    urgency TEXT,
    sentiment TEXT,
    lead_score INTEGER DEFAULT 0,
    lead_score_reason TEXT,
    summary TEXT,
    suggested_reply TEXT,
    tags TEXT,
    status TEXT DEFAULT 'New',
    raw_transcript TEXT
)
"""

# Columns added after the first schema version; added automatically to older databases.
_LATER_COLUMNS = {"source": "TEXT DEFAULT 'unknown'", "status": "TEXT DEFAULT 'New'"}


@contextmanager
def get_conn(db_path: Optional[Path] = None) -> Iterator[sqlite3.Connection]:
    path = Path(db_path or config.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: Optional[Path] = None) -> None:
    """Create the table if needed and add any columns missing from an older database."""
    with get_conn(db_path) as conn:
        conn.execute(SCHEMA)
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(calls)")}
        for column, definition in _LATER_COLUMNS.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE calls ADD COLUMN {column} {definition}")


def insert_call(
    transcript: str,
    info: dict,
    source: str = "unknown",
    created_at: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> int:
    """Save one analysed call and return its new id."""
    tags = info.get("tags") or []
    tags_text = ", ".join(tags) if isinstance(tags, list) else str(tags)
    with get_conn(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO calls
               (created_at, source, caller_name, callback_number, intent_type,
                course_interest, urgency, sentiment, lead_score, lead_score_reason,
                summary, suggested_reply, tags, status, raw_transcript)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'New', ?)""",
            (
                created_at or datetime.now().isoformat(timespec="seconds"),
                source,
                info.get("caller_name"),
                info.get("callback_number"),
                info.get("intent_type"),
                info.get("course_interest"),
                info.get("urgency"),
                info.get("sentiment"),
                int(info.get("lead_score") or 0),
                info.get("lead_score_reason"),
                info.get("summary"),
                info.get("suggested_reply"),
                tags_text,
                transcript,
            ),
        )
        return int(cur.lastrowid)


def fetch_calls(
    intents: Optional[Sequence[str]] = None,
    urgencies: Optional[Sequence[str]] = None,
    statuses: Optional[Sequence[str]] = None,
    min_score: int = 0,
    search: Optional[str] = None,
    order: str = "recent",
    limit: Optional[int] = None,
    db_path: Optional[Path] = None,
) -> list[dict]:
    """Return calls matching the filters. `order` is 'recent' or 'score'."""
    clauses, params = ["lead_score >= ?"], [min_score]

    for column, values in (
        ("intent_type", intents),
        ("urgency", urgencies),
        ("status", statuses),
    ):
        if values:
            clauses.append(f"{column} IN ({','.join('?' * len(values))})")
            params.extend(values)

    if search and search.strip():
        like = f"%{search.strip()}%"
        fields = ["caller_name", "summary", "course_interest", "tags", "raw_transcript"]
        clauses.append("(" + " OR ".join(f"{f} LIKE ?" for f in fields) + ")")
        params.extend([like] * len(fields))

    order_sql = "lead_score DESC, id DESC" if order == "score" else "created_at DESC, id DESC"
    sql = f"SELECT * FROM calls WHERE {' AND '.join(clauses)} ORDER BY {order_sql}"
    if limit:
        sql += f" LIMIT {int(limit)}"

    with get_conn(db_path) as conn:
        return [dict(row) for row in conn.execute(sql, params)]


def get_call(call_id: int, db_path: Optional[Path] = None) -> Optional[dict]:
    with get_conn(db_path) as conn:
        row = conn.execute("SELECT * FROM calls WHERE id = ?", (call_id,)).fetchone()
        return dict(row) if row else None


def update_status(call_id: int, status: str, db_path: Optional[Path] = None) -> None:
    if status not in config.STATUSES:
        raise ValueError(f"Unknown status: {status}")
    with get_conn(db_path) as conn:
        conn.execute("UPDATE calls SET status = ? WHERE id = ?", (status, call_id))


def delete_call(call_id: int, db_path: Optional[Path] = None) -> None:
    with get_conn(db_path) as conn:
        conn.execute("DELETE FROM calls WHERE id = ?", (call_id,))


def delete_all(db_path: Optional[Path] = None) -> None:
    with get_conn(db_path) as conn:
        conn.execute("DELETE FROM calls")


def get_stats(db_path: Optional[Path] = None) -> dict:
    """Aggregate numbers for the dashboard."""
    calls = fetch_calls(db_path=db_path)
    total = len(calls)

    def count_by(field: str) -> dict:
        counts: dict = {}
        for call in calls:
            key = call.get(field) or "unknown"
            counts[key] = counts.get(key, 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: -kv[1]))

    return {
        "total": total,
        "high_priority": sum(1 for c in calls if (c["lead_score"] or 0) >= config.HIGH_PRIORITY_SCORE),
        "avg_score": round(sum(c["lead_score"] or 0 for c in calls) / total) if total else 0,
        "awaiting_follow_up": sum(1 for c in calls if c["status"] == "New"),
        "by_intent": count_by("intent_type"),
        "by_urgency": count_by("urgency"),
        "by_sentiment": count_by("sentiment"),
        "by_status": count_by("status"),
    }
