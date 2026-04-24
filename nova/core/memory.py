"""
core/memory.py
L6 Memory Layer — SQLite session logging + context retrieval
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path("nova.db")

# ─────────────────────────────────────────────
# Schema
# ─────────────────────────────────────────────

def init_db():
    """Create tables if they don't exist."""
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS turns (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT    NOT NULL,
            timestamp   TEXT    NOT NULL,
            role        TEXT    NOT NULL,
            content     TEXT    NOT NULL,
            score       REAL    DEFAULT NULL,
            flags       TEXT    DEFAULT '[]'
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id  TEXT    PRIMARY KEY,
            started_at  TEXT    NOT NULL,
            ended_at    TEXT    DEFAULT NULL,
            turn_count  INTEGER DEFAULT 0,
            avg_score   REAL    DEFAULT NULL
        )
    """)

    con.commit()
    con.close()


# ─────────────────────────────────────────────
# Session Management
# ─────────────────────────────────────────────

def new_session() -> str:
    """Create a new session ID based on timestamp."""
    session_id = datetime.now().strftime("session_%Y%m%d_%H%M%S")
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        "INSERT INTO sessions (session_id, started_at) VALUES (?, ?)",
        (session_id, datetime.now().isoformat())
    )
    con.commit()
    con.close()
    return session_id


def close_session(session_id: str):
    """Mark session as ended and compute avg score."""
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.execute("""
        SELECT COUNT(*), AVG(score)
        FROM turns
        WHERE session_id = ? AND role = 'assistant' AND score IS NOT NULL
    """, (session_id,))
    row = cur.fetchone()
    turn_count = row[0] or 0
    avg_score  = round(row[1], 3) if row[1] else None

    cur.execute("""
        UPDATE sessions
        SET ended_at = ?, turn_count = ?, avg_score = ?
        WHERE session_id = ?
    """, (datetime.now().isoformat(), turn_count, avg_score, session_id))

    con.commit()
    con.close()
    print(f"[Memory] Session closed — {turn_count} turns, avg score: {avg_score}")


# ─────────────────────────────────────────────
# Turn Logging
# ─────────────────────────────────────────────

def log_turn(session_id: str, role: str, content: str,
             score: float = None, flags: list = None):
    """Save a single turn to the database."""
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        INSERT INTO turns (session_id, timestamp, role, content, score, flags)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        session_id,
        datetime.now().isoformat(),
        role,
        content,
        score,
        json.dumps(flags or [])
    ))
    con.commit()
    con.close()


# ─────────────────────────────────────────────
# Context Retrieval
# ─────────────────────────────────────────────

def get_recent_context(n: int = 6) -> list[dict]:
    """
    Pull the last N user+assistant turn pairs across all sessions.
    Returns a list of message dicts ready to inject into history.
    """
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.execute("""
        SELECT role, content
        FROM turns
        ORDER BY id DESC
        LIMIT ?
    """, (n * 2,))

    rows = cur.fetchall()
    con.close()

    # Reverse so oldest first, format for chat history
    messages = [{"role": r, "content": c} for r, c in reversed(rows)]
    return messages

def get_session_context(session_id: str, n: int = 6) -> list[dict]:
    """
    Pull last N turn pairs from the CURRENT session only.
    Used by loop.py to maintain in-session coherence.
    """
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.execute("""
        SELECT role, content
        FROM turns
        WHERE session_id = ?
        ORDER BY id DESC
        LIMIT ?
    """, (session_id, n * 2))

    rows = cur.fetchall()
    con.close()

    messages = [{"role": r, "content": c} for r, c in reversed(rows)]
    return messages



def get_session_summary(session_id: str) -> dict:
    """Return metadata for a specific session."""
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
    row = cur.fetchone()
    con.close()
    if row:
        return {
            "session_id": row[0],
            "started_at": row[1],
            "ended_at":   row[2],
            "turn_count": row[3],
            "avg_score":  row[4],
        }
    return {}


# ─────────────────────────────────────────────
# Standalone test
# ─────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    sid = new_session()
    print(f"New session: {sid}")

    log_turn(sid, "user",      "Hello Nova, who are you?")
    log_turn(sid, "assistant", "I am Nova, your local-first AI partner.", score=0.91, flags=[])

    context = get_recent_context(n=3)
    print(f"Recent context ({len(context)} messages):")
    for m in context:
        print(f"  [{m['role']}] {m['content'][:60]}")

    close_session(sid)
