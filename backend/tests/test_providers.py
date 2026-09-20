import pytest

from backend.app.config import (
    ASRSettings,
    AnthropicSettings,
    AppSettings,
    LLMSettings,
    OllamaSettings,
    OpenAISettings,
    RustFSSettings,
    Settings,
    VLLMSettings,
)
from backend.app.providers import build_chat_model


def config(**overrides):
    return Settings(
        app=AppSettings(_env_file=None),
        asr=ASRSettings(_env_file=None),
        llm=LLMSettings(
            provider=overrides.get("llm_provider", "demo"),
            model=overrides.get("llm_model", "test-model"),
            _env_file=None,
        ),
        openai=OpenAISettings(api_key=overrides.get("openai_api_key", ""), _env_file=None),
        anthropic=AnthropicSettings(api_key=overrides.get("anthropic_api_key", ""), _env_file=None),
        ollama=OllamaSettings(_env_file=None),
        vllm=VLLMSettings(
            base_url=overrides.get("vllm_base_url", "http://localhost:8000/v1"),
            _env_file=None,
        ),
        rustfs=RustFSSettings(_env_file=None),
    )


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
