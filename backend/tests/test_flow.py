from io import BytesIO

from docx import Document
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.store import MeetingStore
import app.main as main_module


class MemoryObjectStorage:
    def __init__(self):
        self.objects = {}

    def put(self, key, data, content_type="application/octet-stream"):
        self.objects[key] = (data, content_type)

    def get(self, key):
        if key not in self.objects:
            raise KeyError(key)
        return self.objects[key][0]


def test_complete_meeting_flow(monkeypatch):
    object_storage = MemoryObjectStorage()
    test_store = MeetingStore(object_storage)
    monkeypatch.setattr(main_module, "store", test_store)
    monkeypatch.setattr(settings, "asr_backend", "demo")
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


def test_rejects_unsupported_file(monkeypatch):
    monkeypatch.setattr(main_module, "store", MeetingStore(MemoryObjectStorage()))
    response = TestClient(app).post(
        "/api/meetings",
        data={"title": "非法文件"},
        files={"file": ("note.txt", b"text", "text/plain")},
    )
    assert response.status_code == 400
