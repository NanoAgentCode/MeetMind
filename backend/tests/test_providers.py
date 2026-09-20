import pytest

from app.config import Settings
from app.providers import build_chat_model


def config(**overrides):
    values = {
        "llm_provider": "demo",
        "llm_model": "test-model",
        "_env_file": None,
    }
    values.update(overrides)
    return Settings(**values)


def test_demo_provider_uses_deterministic_fallback():
    assert build_chat_model(config()) is None


def test_openai_provider():
    model = build_chat_model(config(llm_provider="openai", openai_api_key="test-key"))
    assert model.__class__.__name__ == "ChatOpenAI"
    assert model.model_name == "test-model"


def test_anthropic_provider():
    model = build_chat_model(config(llm_provider="anthropic", anthropic_api_key="test-key"))
    assert model.__class__.__name__ == "ChatAnthropic"
    assert model.model == "test-model"


def test_ollama_provider():
    model = build_chat_model(config(llm_provider="ollama"))
    assert model.__class__.__name__ == "ChatOllama"
    assert model.model == "test-model"


def test_vllm_uses_openai_compatible_client():
    model = build_chat_model(config(llm_provider="vllm", vllm_base_url="http://vllm:8000/v1"))
    assert model.__class__.__name__ == "ChatOpenAI"
    assert str(model.openai_api_base).rstrip("/") == "http://vllm:8000/v1"


@pytest.mark.parametrize("provider,key_name", [("openai", "OPENAI_API_KEY"), ("anthropic", "ANTHROPIC_API_KEY")])
def test_cloud_provider_requires_key(provider, key_name):
    with pytest.raises(ValueError, match=key_name):
        build_chat_model(config(llm_provider=provider))


def test_rejects_unknown_provider():
    with pytest.raises(ValueError, match="不支持的 LLM_PROVIDER"):
        build_chat_model(config(llm_provider="unknown"))
