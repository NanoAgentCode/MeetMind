import asyncio

from backend.app.provider_context import context_window_from_metadata, resolve_context_window
from backend.app.config import AppSettings


def test_ollama_uses_smaller_configured_context_limit():
    assert context_window_from_metadata("ollama", {
        "parameters": "temperature 0.7\nnum_ctx 4096",
        "model_info": {"llama.context_length": 131072},
    }) == 4096


def test_compatible_metadata_can_provide_context_window():
    assert context_window_from_metadata("openai_compatible", {"max_model_len": 32768}) == 32768
    assert context_window_from_metadata("openai_compatible", {"id": "model-only"}) is None


def test_openai_model_object_without_window_uses_fallback():
    assert context_window_from_metadata("openai", {"id": "gpt-model", "owned_by": "openai"}) is None


def test_default_fallback_context_window_is_256k():
    assert AppSettings.model_fields["chat_context_window_tokens"].default == 262144


def test_no_managed_model_uses_fallback_even_with_legacy_ollama_env(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")

    class Registry:
        def get_default_model(self, _type):
            return None

    assert asyncio.run(resolve_context_window(Registry(), None, 262144)) == 262144


def test_ollama_context_discovery_uses_show_metadata():
    from backend.app.provider_context import _cache
    from types import SimpleNamespace

    class Registry:
        def get_default_model(self, _type):
            return (SimpleNamespace(model_id="test-model"),
                    SimpleNamespace(protocol="ollama", base_url="http://localhost:11434"), "")

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"parameters": "num_ctx 2048", "model_info": {"llama.context_length": 8192}}

    class Client:
        def __init__(self, timeout):
            assert timeout == 3

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            pass

        async def post(self, _url, json):
            assert json == {"model": "test-model"}
            return Response()

    _cache.clear()
    assert asyncio.run(resolve_context_window(Registry(), None, 8192, Client)) == 2048
