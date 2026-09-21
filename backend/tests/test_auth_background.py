import asyncio

from fastapi.testclient import TestClient

import backend.app.main as main_module
from backend.app.auth import AuthStore
from backend.app.config import settings
from backend.app.main import app
from backend.app.store import MeetingStore
from backend.tests.test_flow import MemoryObjectStorage


def setup_app(monkeypatch, tmp_path):
    database = tmp_path / "app.db"
    meeting_store = MeetingStore(MemoryObjectStorage(), database)
    auth_store = AuthStore(database)
    monkeypatch.setattr(main_module, "store", meeting_store)
    monkeypatch.setattr(main_module, "auth_store", auth_store)
    monkeypatch.setattr(settings.app, "admin_username", "admin")
    monkeypatch.setattr(settings.app, "admin_password", "strong-test-password")
    return meeting_store, auth_store


def login(client):
    response = client.post("/api/auth/login", json={"username": "admin", "password": "strong-test-password"})
    assert response.status_code == 200
    return response.json()


def test_login_session_and_logout(monkeypatch, tmp_path):
    setup_app(monkeypatch, tmp_path)
    client = TestClient(app)
    assert client.get("/api/meetings").status_code == 401
    assert client.post("/api/auth/login", json={"username": "admin", "password": "wrong"}).status_code == 401
    user = login(client)
    assert client.get("/api/auth/me").json()["id"] == user["id"]
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/meetings").status_code == 401


def test_large_audio_queues_and_notifies_owner(monkeypatch, tmp_path):
    meeting_store, _ = setup_app(monkeypatch, tmp_path)
    monkeypatch.setattr(settings.app, "background_audio_mb", 0)
    queued = []
    monkeypatch.setattr(main_module, "schedule_transcription", queued.append)
    client = TestClient(app)
    owner = login(client)

    response = client.post("/api/meetings", data={"title": "长会议"}, files={"file": ("long.mp3", b"audio", "audio/mpeg")})
    assert response.status_code == 201
    meeting_id = response.json()["id"]
    assert response.json()["status"] == "queued"
    assert queued == [meeting_id]
    assert client.post(f"/api/meetings/{meeting_id}/transcribe").status_code == 409

    async def fake_transcriber(_path):
        return "会议转写完成"

    monkeypatch.setattr(main_module, "transcribe_audio", fake_transcriber)
    asyncio.run(main_module.run_transcription(meeting_id))
    assert meeting_store.get(meeting_id).status == "transcribed"
    notifications = client.get("/api/notifications").json()
    assert len(notifications) == 1
    assert notifications[0]["user_id"] == owner["id"]
    assert notifications[0]["title"] == "转写完成"
    assert client.post(f"/api/notifications/{notifications[0]['id']}/read").status_code == 204
    assert client.get("/api/notifications").json()[0]["read_at"] is not None


def test_failed_background_transcription_notifies_owner(monkeypatch, tmp_path):
    setup_app(monkeypatch, tmp_path)
    monkeypatch.setattr(settings.app, "background_audio_mb", 0)
    monkeypatch.setattr(main_module, "schedule_transcription", lambda _id: None)
    client = TestClient(app)
    login(client)
    meeting_id = client.post("/api/meetings", data={"title": "失败会议"}, files={"file": ("bad.mp3", b"audio", "audio/mpeg")}).json()["id"]

    async def failing_transcriber(_path):
        raise ValueError("ASR unavailable")

    monkeypatch.setattr(main_module, "transcribe_audio", failing_transcriber)
    asyncio.run(main_module.run_transcription(meeting_id))
    assert client.get(f"/api/meetings/{meeting_id}").json()["status"] == "transcription_failed"
    assert client.get("/api/notifications").json()[0]["title"] == "转写失败"


def test_pending_tasks_are_persisted_for_restart(monkeypatch, tmp_path):
    meeting_store, _ = setup_app(monkeypatch, tmp_path)
    monkeypatch.setattr(settings.app, "background_audio_mb", 0)
    monkeypatch.setattr(main_module, "schedule_transcription", lambda _id: None)
    client = TestClient(app)
    login(client)
    meeting_id = client.post("/api/meetings", data={"title": "待恢复"}, files={"file": ("restart.mp3", b"audio", "audio/mpeg")}).json()["id"]
    reopened_store = MeetingStore(meeting_store.storage, meeting_store.database_path)
    assert [item.id for item in reopened_store.pending_transcriptions()] == [meeting_id]


def test_meeting_is_private_to_owner(monkeypatch, tmp_path):
    _meeting_store, auth_store = setup_app(monkeypatch, tmp_path)
    client = TestClient(app)
    login(client)
    meeting_id = client.post("/api/meetings", data={"title": "私有会议"}, files={"file": ("private.mp3", b"audio", "audio/mpeg")}).json()["id"]
    auth_store.create_user("other", "另一用户", "other-password", None, ["member"])
    other = TestClient(app)
    assert other.post("/api/auth/login", json={"username": "other", "password": "other-password"}).status_code == 200
    assert other.get("/api/meetings").json() == []
    assert other.get(f"/api/meetings/{meeting_id}").status_code == 404
    assert other.get("/api/notifications").json() == []
