import json
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


class MeetingStore:
    def __init__(self, storage: ObjectStorage | None = None):
        self.storage = storage or RustFSStorage()

    @staticmethod
    def meeting_key(meeting_id: str) -> str:
        return f"meetings/{meeting_id}.json"

    @staticmethod
    def audio_key(meeting: Meeting) -> str:
        return f"recordings/{meeting.id}/source{Path(meeting.filename).suffix.lower()}"

    def save(self, meeting: Meeting) -> Meeting:
        payload = meeting.model_dump_json(indent=2).encode("utf-8")
        self.storage.put(self.meeting_key(meeting.id), payload, "application/json")
        return meeting

    def get(self, meeting_id: str) -> Meeting | None:
        try:
            payload = self.storage.get(self.meeting_key(meeting_id))
        except (ClientError, KeyError):
            return None
        return Meeting.model_validate(json.loads(payload.decode("utf-8")))

    def save_audio(self, meeting: Meeting, content: bytes, content_type: str) -> None:
        self.storage.put(self.audio_key(meeting), content, content_type)

    def get_audio(self, meeting: Meeting) -> bytes:
        return self.storage.get(self.audio_key(meeting))

    def save_export(self, meeting: Meeting, extension: str, content: bytes, content_type: str) -> str:
        key = f"exports/{meeting.id}/minutes.{extension}"
        self.storage.put(key, content, content_type)
        return key


store = MeetingStore()
