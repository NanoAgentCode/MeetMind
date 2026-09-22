from datetime import datetime, timezone

import pytest

from backend.app.models import ModelConfig, Provider
from backend.app.providers import build_managed_chat_model


def managed(protocol: str, api_key: str = "test-key"):
    now = datetime.now(timezone.utc)
    model = ModelConfig(id="model", provider_id="provider", name="测试模型", model_id="test-model",
                        model_type="llm", enabled=True, is_default=True, created_at=now)
    provider = Provider(id="provider", name="测试供应商", protocol=protocol,
                        base_url="http://localhost:8000/v1", enabled=True, created_at=now)
    return model, provider, api_key


@pytest.mark.parametrize("protocol,client_name", [
    ("openai", "ChatOpenAI"), ("openai_compatible", "ChatOpenAI"),
    ("anthropic", "ChatAnthropic"), ("ollama", "ChatOllama"),
])
def test_managed_model_uses_saved_provider(protocol, client_name):
    client = build_managed_chat_model(*managed(protocol))
    assert client.__class__.__name__ == client_name


@pytest.mark.parametrize("protocol", ["openai", "anthropic"])
def test_managed_cloud_provider_requires_key(protocol):
    with pytest.raises(ValueError, match="API Key"):
        build_managed_chat_model(*managed(protocol, ""))
