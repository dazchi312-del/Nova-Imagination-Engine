"""
core/scheduler_db.py
Shared SQLite queue layer for Nova's scheduler.
All reads/writes go through this module.
"""

import sqlite3
import json
import time
from pathlib import Path

DB_PATH = Path('nova.db')


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    return conn


def init_scheduler_schema() -> None:
    """Create scheduler tables if they don't exist. Safe to call repeatedly."""
    conn = get_conn()
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL,
                tool        TEXT    NOT NULL,
                args        TEXT    NOT NULL,
                interval_s  INTEGER DEFAULT NULL,
                next_run    REAL    NOT NULL,
                status      TEXT    NOT NULL DEFAULT 'pending',
                created_at  REAL    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS results (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id     INTEGER NOT NULL,
                output      TEXT    NOT NULL,
                ran_at      REAL    NOT NULL,
                FOREIGN KEY (task_id) REFERENCES tasks(id)
            );

            CREATE TABLE IF NOT EXISTS events (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                source      TEXT    NOT NULL,
                event       TEXT    NOT NULL,
                detail      TEXT,
                ts          REAL    NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_tasks_next_run
                ON tasks(next_run) WHERE status = 'pending';

            CREATE INDEX IF NOT EXISTS idx_results_task_id
                ON results(task_id);
        """)
    conn.close()


# ── Task queue helpers ────────────────────────────────────────────────────────

def enqueue_task(
    name: str,
    tool: str,
    args: dict,
    interval_s: int | None = None,
    delay_s: float = 0.0
) -> int:
    """
    Add a task to the queue. Returns the new task id.
    interval_s=None  -> one-shot
    interval_s=30    -> repeat every 30 seconds
    delay_s          -> don't run until now + delay_s
    """
    conn = get_conn()
    now = time.time()
    with conn:
        cur = conn.execute(
            """INSERT INTO tasks (name, tool, args, interval_s, next_run, status, created_at)
               VALUES (?, ?, ?, ?, ?, 'pending', ?)""",
            (name, tool, json.dumps(args), interval_s, now + delay_s, now)
        )
        task_id = cur.lastrowid
    conn.close()
    log_event('nova', 'task_enqueued', f'{name} (id={task_id})')
    return task_id


def get_due_tasks(now: float | None = None) -> list[sqlite3.Row]:
    """Return all pending tasks whose next_run <= now."""
    if now is None:
        now = time.time()
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM tasks WHERE status = 'pending' AND next_run <= ?",
        (now,)
    ).fetchall()
    conn.close()
    return rows


def mark_running(task_id: int) -> None:
    conn = get_conn()
    with conn:
        conn.execute(
            "UPDATE tasks SET status = 'running' WHERE id = ?",
            (task_id,)
        )
    conn.close()


def mark_done(task_id: int) -> None:
    conn = get_conn()
    with conn:
        conn.execute(
            "UPDATE tasks SET status = 'done' WHERE id = ?",
            (task_id,)
        )
    conn.close()


def mark_failed(task_id: int) -> None:
    conn = get_conn()
    with conn:
        conn.execute(
            "UPDATE tasks SET status = 'failed' WHERE id = ?",
            (task_id,)
        )
    conn.close()


def reschedule(task_id: int, next_run: float) -> None:
    """Reset a recurring task back to pending with a new next_run time."""
    conn = get_conn()
    with conn:
        conn.execute(
            "UPDATE tasks SET status = 'pending', next_run = ? WHERE id = ?",
            (next_run, task_id)
        )
    conn.close()


def write_result(task_id: int, output: str) -> None:
    conn = get_conn()
    with conn:
        conn.execute(
            "INSERT INTO results (task_id, output, ran_at) VALUES (?, ?, ?)",
            (task_id, output, time.time())
        )
    conn.close()


def get_latest_result(task_name: str) -> str | None:
    """
    Fetch the most recent result output for a named task.
    Used by loop.py to surface scheduler data to Nova.
    """
    conn = get_conn()
    row = conn.execute(
        """SELECT r.output FROM results r
           JOIN tasks t ON r.task_id = t.id
           WHERE t.name = ?
           ORDER BY r.ran_at DESC
           LIMIT 1""",
        (task_name,)
    ).fetchone()
    conn.close()
    return row['output'] if row else None


def get_recent_events(limit: int = 20) -> list[sqlite3.Row]:
    """Return the most recent scheduler events, newest first."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM events ORDER BY ts DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return rows


# ── Event log ─────────────────────────────────────────────────────────────────

def log_event(source: str, event: str, detail: str | None = None) -> None:
    conn = get_conn()
    with conn:
        conn.execute(
            "INSERT INTO events (source, event, detail, ts) VALUES (?, ?, ?, ?)",
            (source, event, detail, time.time())
        )
    conn.close()


# ── Introspection helpers ─────────────────────────────────────────────────────

def get_all_tasks(status: str | None = None) -> list[sqlite3.Row]:
    conn = get_conn()
    if status:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE status = ? ORDER BY next_run",
            (status,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM tasks ORDER BY next_run"
        ).fetchall()
    conn.close()
    return rows


def print_task_summary() -> None:
    """Quick diagnostic — print all tasks and recent events to stdout."""
    tasks = get_all_tasks()
    print(f"\n── Tasks ({len(tasks)}) ──────────────────────────────")
    for t in tasks:
        print(f"  [{t['status']:8}] id={t['id']} {t['name']:25} tool={t['tool']}")

    events = get_recent_events(10)
    print(f"\n── Recent Events ────────────────────────────────")
    for e in events:
        import datetime
        ts = datetime.datetime.fromtimestamp(e['ts']).strftime('%H:%M:%S')
        print(f"  {ts}  {e['source']:10} {e['event']:20} {e['detail'] or ''}")
    print()


# ── Self-test ─────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print('Initialising scheduler schema...')
    init_scheduler_schema()

    print('Enqueueing test tasks...')
    t1 = enqueue_task(
        name='system_poll',
        tool='get_system_stats',
        args={},
        interval_s=30
    )
    t2 = enqueue_task(
        name='process_snapshot',
        tool='list_processes',
        args={'sort_by': 'cpu', 'limit': 10},
        interval_s=60
    )
    t3 = enqueue_task(
        name='oneshot_test',
        tool='get_system_stats',
        args={},
        interval_s=None
    )

    print_task_summary()

    print('Simulating task lifecycle...')
    due = get_due_tasks()
    for task in due:
        mark_running(task['id'])
        write_result(task['id'], f'[test output for {task["name"]}]')
        log_event('scheduler', 'task_done', task['name'])
        if task['interval_s']:
            reschedule(task['id'], time.time() + task['interval_s'])
        else:
            mark_done(task['id'])

    print_task_summary()
    print('scheduler_db.py self-test complete.')
