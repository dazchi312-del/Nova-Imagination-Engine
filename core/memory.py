import json
from typing import Dict, List
from db.db import get_connection


class Memory:
    def __init__(self):
        pass

    def save(self, key: str, data: Dict):
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO memory_entries (key, value)
            VALUES (?, ?)
            """,
            (key, json.dumps(data)),
        )

        conn.commit()
        conn.close()

    def load(self, key: str) -> Dict:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT value FROM memory_entries WHERE key = ?",
            (key,),
        )

        row = cursor.fetchone()
        conn.close()

        if row:
            return json.loads(row[0])

        return {}

    def list_keys(self) -> List[str]:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT key FROM memory_entries")
        rows = cursor.fetchall()
        conn.close()

        return [row[0] for row in rows]

    def delete(self, key: str):
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM memory_entries WHERE key = ?",
            (key,),
        )

        conn.commit()
        conn.close()