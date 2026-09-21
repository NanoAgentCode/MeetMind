from datetime import datetime, timezone

from fastapi.testclient import TestClient

import backend.app.main as main_module
from backend.app.main import app
from backend.app.model_registry import ModelRegistry
from backend.app.models import Meeting
from backend.app.store import MeetingStore
from backend.tests.test_flow import MemoryObjectStorage


def test_model_provider_and_config_crud(monkeypatch, tmp_path):
    registry = ModelRegistry(tmp_path / "models.db")
    monkeypatch.setattr(main_module, "model_registry", registry)
    client = TestClient(app)

    provider_response = client.post(
        "/api/model-providers",
        json={
            "name": "企业 OpenAI",
            "protocol": "openai_compatible",
            "base_url": "https://llm.example.com/v1",
            "api_key": "company-secret-key",
            "enabled": True,
        },
    )
    assert provider_response.status_code == 201
    provider = provider_response.json()
    assert "api_key" not in provider
    assert provider["api_key_configured"] is True

    model_response = client.post(
        "/api/model-configs",
        json={
            "provider_id": provider["id"],
            "name": "会议问答",
            "model_id": "qwen3-32b",
            "model_type": "rag",
            "enabled": True,
            "is_default": True,
        },
    )
    assert model_response.status_code == 201
    assert model_response.json()["is_default"] is True
    assert len(client.get("/api/model-configs").json()) == 1

    assert client.delete(f"/api/model-providers/{provider['id']}").status_code == 204
    assert client.get("/api/model-configs").json() == []


def test_meeting_question_uses_meeting_context(monkeypatch, tmp_path):
    meeting_store = MeetingStore(MemoryObjectStorage(), tmp_path / "meetings.db")
    registry = ModelRegistry(tmp_path / "models.db")
    monkeypatch.setattr(main_module, "store", meeting_store)
    monkeypatch.setattr(main_module, "model_registry", registry)
    meeting_store.save(
        Meeting(
            id="meeting-1",
            filename="weekly.mp3",
            title="产品周会",
            created_at=datetime.now(timezone.utc),
            status="transcribed",
            transcript="决定周五发布，张明负责上线。",
        )
    )

    async def fake_answer(meeting, question, passed_registry):
        assert meeting.transcript == "决定周五发布，张明负责上线。"
        assert question == "谁负责上线？"
        assert passed_registry is registry
        return "张明负责上线。"

    monkeypatch.setattr(main_module, "answer_meeting_question", fake_answer)
    response = TestClient(app).post(
        "/api/meetings/meeting-1/questions", json={"question": "谁负责上线？"}
    )

    assert response.status_code == 200
    assert response.json() == {"answer": "张明负责上线。"}
