"""Persistent, user-owned chat conversations."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


class ChatStore:
    def __init__(self, path: Path):
        self.path = path
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS chat_conversations (
                id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, meeting_id TEXT,
                title TEXT NOT NULL, messages_json TEXT NOT NULL, updated_at TEXT NOT NULL
            )""")

    def _connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def list(self, owner_id: str):
        with self._connect() as db:
            rows = db.execute("SELECT * FROM chat_conversations WHERE owner_id = ? ORDER BY updated_at DESC", (owner_id,)).fetchall()
        return [self._decode(row) for row in rows]

    def get(self, conversation_id: str, owner_id: str):
        with self._connect() as db:
            row = db.execute("SELECT * FROM chat_conversations WHERE id = ? AND owner_id = ?", (conversation_id, owner_id)).fetchone()
        return self._decode(row) if row else None

    def save(self, owner_id: str, meeting_id: str | None, question: str, messages: list[dict], conversation_id: str | None = None):
        now = datetime.now(timezone.utc).isoformat()
        if conversation_id:
            with self._connect() as db:
                db.execute("UPDATE chat_conversations SET messages_json = ?, updated_at = ? WHERE id = ? AND owner_id = ?",
                           (json.dumps(messages, ensure_ascii=False), now, conversation_id, owner_id))
            return conversation_id
        conversation_id = uuid4().hex
        with self._connect() as db:
            db.execute("INSERT INTO chat_conversations VALUES (?, ?, ?, ?, ?, ?)",
                       (conversation_id, owner_id, meeting_id, question[:60], json.dumps(messages, ensure_ascii=False), now))
        return conversation_id

    @staticmethod
    def _decode(row):
        return {"id": row["id"], "meeting_id": row["meeting_id"], "title": row["title"],
                "messages": json.loads(row["messages_json"]), "updated_at": row["updated_at"]}
