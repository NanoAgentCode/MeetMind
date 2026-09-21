from datetime import datetime, timezone

from fastapi.testclient import TestClient
import pytest

import backend.app.main as main_module
from backend.app.main import app
from backend.app.model_registry import ModelRegistry
from backend.app.models import Meeting, ProviderInput
from backend.app.store import MeetingStore
from backend.tests.test_flow import MemoryObjectStorage


class FakeModelResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeModelClient:
    payload = {}
    requests = []

    def __init__(self, **_kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def get(self, url, headers):
        self.requests.append((url, headers))
        return FakeModelResponse(self.payload)


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


@pytest.mark.parametrize(
    "protocol,base_url,payload,expected_url,expected_models",
    [
        (
            "openai_compatible", "https://llm.example.com/v1",
            {"data": [{"id": "qwen3"}, {"id": "deepseek-v3"}, {"id": "qwen3"}]},
            "https://llm.example.com/v1/models", ["deepseek-v3", "qwen3"],
        ),
        (
            "anthropic", "https://api.anthropic.com",
            {"data": [{"id": "claude-sonnet-4-5"}]},
            "https://api.anthropic.com/v1/models", ["claude-sonnet-4-5"],
        ),
        (
            "ollama", "http://localhost:11434",
            {"models": [{"name": "qwen3:8b"}, {"model": "nomic-embed-text"}]},
            "http://localhost:11434/api/tags", ["nomic-embed-text", "qwen3:8b"],
        ),
    ],
)
def test_lists_models_from_provider_protocol(
    monkeypatch, tmp_path, protocol, base_url, payload, expected_url, expected_models
):
    registry = ModelRegistry(tmp_path / f"{protocol}.db")
    provider = registry.save_provider(
        "provider-1",
        ProviderInput.model_validate({
            "name": "模型供应商", "protocol": protocol, "base_url": base_url,
            "api_key": "secret", "enabled": True,
        }),
    )
    monkeypatch.setattr(main_module, "model_registry", registry)
    FakeModelClient.payload = payload
    FakeModelClient.requests = []
    monkeypatch.setattr(main_module.httpx, "AsyncClient", FakeModelClient)

    response = TestClient(app).get(f"/api/model-providers/{provider.id}/models")

    assert response.status_code == 200
    assert response.json() == {"models": expected_models}
    assert FakeModelClient.requests[0][0] == expected_url
