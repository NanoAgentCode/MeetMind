from io import BytesIO

from docx import Document
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.main import app
from backend.app.store import MeetingStore
import backend.app.main as main_module


class MemoryObjectStorage:
    def __init__(self):
        self.objects = {}

    def put(self, key, data, content_type="application/octet-stream"):
        self.objects[key] = (data, content_type)

    def get(self, key):
        if key not in self.objects:
            raise KeyError(key)
        return self.objects[key][0]

    def list_keys(self, prefix):
        return sorted(key for key in self.objects if key.startswith(prefix))

    def delete(self, key):
        self.objects.pop(key, None)


def test_complete_meeting_flow(monkeypatch, tmp_path):
    object_storage = MemoryObjectStorage()
    test_store = MeetingStore(object_storage, tmp_path / "meetings.db")
    monkeypatch.setattr(main_module, "store", test_store)
    monkeypatch.setattr(settings.asr, "backend", "demo")
    client = TestClient(app)

    uploaded = client.post(
        "/api/meetings",
        data={"title": "产品周会"},
        files={"file": ("weekly.mp3", b"fake-audio", "audio/mpeg")},
    )
    assert uploaded.status_code == 201
    meeting_id = uploaded.json()["id"]
    assert uploaded.json()["status"] == "uploaded"
    assert any(key.startswith("recordings/") for key in object_storage.objects)

    transcribed = client.post(f"/api/meetings/{meeting_id}/transcribe")
    assert transcribed.status_code == 200
    assert transcribed.json()["status"] == "transcribed"
    assert "第一阶段" in transcribed.json()["transcript"]

    generated = client.post(f"/api/meetings/{meeting_id}/minutes/generate")
    assert generated.status_code == 200
    assert generated.json()["status"] == "generated"
    minutes = generated.json()["minutes"]
    minutes["summary"] = "这是人工确认后的会议摘要。"

    edited = client.put(f"/api/meetings/{meeting_id}/minutes", json=minutes)
    assert edited.status_code == 200
    assert edited.json()["status"] == "edited"

    markdown = client.get(f"/api/meetings/{meeting_id}/export?format=md")
    assert markdown.status_code == 200
    assert "这是人工确认后的会议摘要" in markdown.text

    word = client.get(f"/api/meetings/{meeting_id}/export?format=docx")
    assert word.status_code == 200
    document = Document(BytesIO(word.content))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert "这是人工确认后的会议摘要" in text
    assert any(key.endswith("minutes.docx") for key in object_storage.objects)


def test_rejects_unsupported_file(monkeypatch, tmp_path):
    monkeypatch.setattr(main_module, "store", MeetingStore(MemoryObjectStorage(), tmp_path / "meetings.db"))
    response = TestClient(app).post(
        "/api/meetings",
        data={"title": "非法文件"},
        files={"file": ("note.txt", b"text", "text/plain")},
    )
    assert response.status_code == 400


def test_lists_meetings_newest_first(monkeypatch, tmp_path):
    object_storage = MemoryObjectStorage()
    monkeypatch.setattr(main_module, "store", MeetingStore(object_storage, tmp_path / "meetings.db"))
    client = TestClient(app)

    first = client.post(
        "/api/meetings",
        data={"title": "第一场会议"},
        files={"file": ("first.mp3", b"first", "audio/mpeg")},
    )
    second = client.post(
        "/api/meetings",
        data={"title": "第二场会议"},
        files={"file": ("second.mp3", b"second", "audio/mpeg")},
    )

    response = client.get("/api/meetings")

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [second.json()["id"], first.json()["id"]]


def test_deletes_meeting_and_related_objects(monkeypatch, tmp_path):
    object_storage = MemoryObjectStorage()
    monkeypatch.setattr(main_module, "store", MeetingStore(object_storage, tmp_path / "meetings.db"))
    client = TestClient(app)
    created = client.post(
        "/api/meetings",
        data={"title": "待删除会议"},
        files={"file": ("delete.mp3", b"audio", "audio/mpeg")},
    ).json()
    object_storage.put(f"exports/{created['id']}/minutes.md", b"minutes")

    response = client.delete(f"/api/meetings/{created['id']}")

    assert response.status_code == 204
    assert not any(created["id"] in key for key in object_storage.objects)
    assert client.get(f"/api/meetings/{created['id']}").status_code == 404


def test_delete_missing_meeting_returns_not_found(monkeypatch, tmp_path):
    monkeypatch.setattr(main_module, "store", MeetingStore(MemoryObjectStorage(), tmp_path / "meetings.db"))

    response = TestClient(app).delete("/api/meetings/missing")

    assert response.status_code == 404
