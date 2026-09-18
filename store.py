"""
Persistence for Erasmus Guide.

The original skill could only "track progress" by asking the student to
re-state what they had done. Writing scores to a database is what turns that
into something the system actually knows between sessions.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).with_name("progress.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS essays (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at   TEXT    NOT NULL,
    topic        TEXT    NOT NULL DEFAULT '',
    word_count   INTEGER NOT NULL,
    total        INTEGER NOT NULL,
    criteria     TEXT    NOT NULL,   -- JSON: key -> {score, comment}
    priority     TEXT    NOT NULL DEFAULT '',
    essay_text   TEXT    NOT NULL
);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def save_essay(topic: str, essay: str, score) -> int:
    conn = connect()
    try:
        cur = conn.execute(
            """INSERT INTO essays
               (created_at, topic, word_count, total, criteria, priority, essay_text)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                datetime.now().isoformat(timespec="seconds"),
                topic,
                len(essay.split()),
                score.total,
                json.dumps(score.criteria, ensure_ascii=False),
                score.priority,
                essay,
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def history(limit: int = 50) -> list:
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT * FROM essays ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        item = dict(r)
        item["criteria"] = json.loads(item["criteria"])
        out.append(item)
    return out


def weakest_criteria(limit: int = 5) -> list:
    """Average score per criterion over recent essays, worst first.

    This is the analysis the skill version could not do: it needs the record,
    not the student's recollection.
    """
    rows = history(limit)
    if not rows:
        return []
    totals: dict = {}
    for row in rows:
        for key, val in row["criteria"].items():
            totals.setdefault(key, []).append(float(val.get("score", 0)))
    return sorted(
        ((k, sum(v) / len(v)) for k, v in totals.items()), key=lambda x: x[1]
    )


def delete_essay(essay_id: int) -> None:
    conn = connect()
    try:
        conn.execute("DELETE FROM essays WHERE id = ?", (essay_id,))
        conn.commit()
    finally:
        conn.close()
