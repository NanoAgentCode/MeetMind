import json
import sqlite3
from pathlib import Path
from typing import Protocol

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from .config import settings
from .models import Meeting


class ObjectStorage(Protocol):
    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None: ...
    def get(self, key: str) -> bytes: ...
    def list_keys(self, prefix: str) -> list[str]: ...
    def delete(self, key: str) -> None: ...


class RustFSStorage:
    """RustFS adapter using its S3-compatible API and path-style addressing."""

    def __init__(self):
        self.bucket = settings.rustfs.bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.rustfs.endpoint,
            aws_access_key_id=settings.rustfs.access_key,
            aws_secret_access_key=settings.rustfs.secret_key,
            region_name=settings.rustfs.region,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )
        self._ready = False

    def _ensure_bucket(self) -> None:
        if self._ready:
            return
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code not in {"404", "NoSuchBucket", "NotFound"}:
                raise
            self.client.create_bucket(Bucket=self.bucket)
        self._ready = True

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        self._ensure_bucket()
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

    def get(self, key: str) -> bytes:
        self._ensure_bucket()
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read()

    def list_keys(self, prefix: str) -> list[str]:
        self._ensure_bucket()
        keys: list[str] = []
        continuation_token: str | None = None
        while True:
            request = {"Bucket": self.bucket, "Prefix": prefix}
            if continuation_token:
                request["ContinuationToken"] = continuation_token
            response = self.client.list_objects_v2(**request)
            keys.extend(item["Key"] for item in response.get("Contents", []))
            if not response.get("IsTruncated"):
                return keys
            continuation_token = response.get("NextContinuationToken")

    def delete(self, key: str) -> None:
        self._ensure_bucket()
        self.client.delete_object(Bucket=self.bucket, Key=key)


class MeetingStore:
    def __init__(self, storage: ObjectStorage | None = None, database_path: Path | str | None = None):
        self.storage = storage or RustFSStorage()
        self.database_path = Path(database_path or settings.database.path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_database()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_database(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS meetings (
                    id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    transcript TEXT NOT NULL DEFAULT '',
                    minutes_json TEXT
                )
                """
            )
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(meetings)")}
            if "owner_id" not in columns:
                connection.execute("ALTER TABLE meetings ADD COLUMN owner_id TEXT")
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS notifications (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, meeting_id TEXT,
                    title TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL,
                    read_at TEXT
                );
            """)

    @staticmethod
    def audio_key(meeting: Meeting) -> str:
        return f"recordings/{meeting.id}/source{Path(meeting.filename).suffix.lower()}"

    def save(self, meeting: Meeting) -> Meeting:
        minutes_json = meeting.minutes.model_dump_json() if meeting.minutes else None
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO meetings (id, filename, title, created_at, status, transcript, minutes_json, owner_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    filename = excluded.filename,
                    title = excluded.title,
                    created_at = excluded.created_at,
                    status = excluded.status,
                    transcript = excluded.transcript,
                    minutes_json = excluded.minutes_json,
                    owner_id = excluded.owner_id
                """,
                (
                    meeting.id,
                    meeting.filename,
                    meeting.title,
                    meeting.created_at.isoformat(),
                    meeting.status,
                    meeting.transcript,
                    minutes_json,
                    meeting.owner_id,
                ),
            )
        return meeting

    def get(self, meeting_id: str) -> Meeting | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
        if row is None:
            return None
        return self._meeting_from_row(row)

    def list(self, owner_id: str | None = None) -> list[Meeting]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM meetings WHERE owner_id = ? ORDER BY created_at DESC" if owner_id else "SELECT * FROM meetings ORDER BY created_at DESC",
                (owner_id,) if owner_id else (),
            ).fetchall()
        return [self._meeting_from_row(row) for row in rows]

    @staticmethod
    def _meeting_from_row(row: sqlite3.Row) -> Meeting:
        return Meeting.model_validate(
            {
                "id": row["id"],
                "filename": row["filename"],
                "title": row["title"],
                "created_at": row["created_at"],
                "status": row["status"],
                "transcript": row["transcript"],
                "minutes": json.loads(row["minutes_json"]) if row["minutes_json"] else None,
                "owner_id": row["owner_id"],
            }
        )

    def delete(self, meeting: Meeting) -> None:
        related_keys = [
            *self.storage.list_keys(f"recordings/{meeting.id}/"),
            *self.storage.list_keys(f"exports/{meeting.id}/"),
        ]
        for key in dict.fromkeys(related_keys):
            self.storage.delete(key)
        with self._connect() as connection:
            connection.execute("DELETE FROM meetings WHERE id = ?", (meeting.id,))
            connection.execute("DELETE FROM notifications WHERE meeting_id = ?", (meeting.id,))

    def pending_transcriptions(self) -> list[Meeting]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM meetings WHERE status IN ('queued', 'transcribing')").fetchall()
        return [self._meeting_from_row(row) for row in rows]

    def notify(self, user_id: str, meeting_id: str, title: str, body: str) -> None:
        from datetime import datetime, timezone
        from uuid import uuid4
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO notifications VALUES (?, ?, ?, ?, ?, ?, NULL)",
                (uuid4().hex, user_id, meeting_id, title, body, datetime.now(timezone.utc).isoformat()),
            )

    def list_notifications(self, user_id: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT 100", (user_id,)
            ).fetchall()
        return [dict(row) for row in rows]

    def mark_notification_read(self, notification_id: str, user_id: str) -> bool:
        from datetime import datetime, timezone
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE notifications SET read_at = ? WHERE id = ? AND user_id = ?",
                (datetime.now(timezone.utc).isoformat(), notification_id, user_id),
            )
        return cursor.rowcount > 0

    def save_audio(self, meeting: Meeting, content: bytes, content_type: str) -> None:
        self.storage.put(self.audio_key(meeting), content, content_type)

    def get_audio(self, meeting: Meeting) -> bytes:
        return self.storage.get(self.audio_key(meeting))

    def save_export(self, meeting: Meeting, extension: str, content: bytes, content_type: str) -> str:
        key = f"exports/{meeting.id}/minutes.{extension}"
        self.storage.put(key, content, content_type)
        return key


store = MeetingStore()
