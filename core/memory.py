from typing import Dict
import uuid
import json
import ast
from db.db import get_connection


class Memory:
    def __init__(self):
        self.store: Dict[str, Dict] = {}

    def save(self, task_id: str, data: Dict):
        self.store[task_id] = data

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO creative_sessions (session_id, base_prompt)
            VALUES (?, ?)
            """,
            (task_id, json.dumps(data)),
        )

        conn.commit()
        conn.close()

    def _parse_payload(self, payload):
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return ast.literal_eval(payload)

    def load(self, task_id: str) -> Dict:
        # First check in-memory
        if task_id in self.store:
            return self.store[task_id]

        # Fallback to database
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT base_prompt FROM creative_sessions WHERE session_id = ?",
            (task_id,),
        )

        row = cursor.fetchone()
        conn.close()

        if row:
            return json.loads(row[0])

        return {}

    def list_sessions(self):
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT session_id, base_prompt FROM creative_sessions ORDER BY timestamp DESC"
        )

        rows = cursor.fetchall()
        conn.close()

        return [{"session_id": row[0], **self._parse_payload(row[1])} for row in rows]

    def get_last_session(self):
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT session_id, base_prompt FROM creative_sessions ORDER BY timestamp DESC LIMIT 1"
        )

        row = cursor.fetchone()
        conn.close()

        if row:
            return {"session_id": row[0], **self._parse_payload(row[1])}

        return {}
