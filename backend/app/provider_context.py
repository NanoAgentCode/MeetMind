"""Best-effort context window discovery from model provider metadata."""

import re
import time
from urllib.parse import quote

import httpx

from .config import settings
from .model_registry import ModelRegistry
from .models import Meeting

_cache: dict[tuple[str, str, str], tuple[float, int]] = {}


def _positive_int(value) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 512 else None


def context_window_from_metadata(protocol: str, payload: dict) -> int | None:
    if protocol == "ollama":
        model_info = payload.get("model_info") or {}
        lengths = [_positive_int(value) for key, value in model_info.items() if key.endswith(".context_length")]
        architecture_limit = max((length for length in lengths if length), default=None)
        match = re.search(r"(?:^|\n)\s*num_ctx\s+(\d+)", payload.get("parameters") or "")
        configured_limit = _positive_int(match.group(1)) if match else None
        return min(architecture_limit, configured_limit) if architecture_limit and configured_limit else configured_limit or architecture_limit
    for key in ("context_window", "context_length", "max_model_len", "max_input_tokens"):
        result = _positive_int(payload.get(key))
        if result:
            return result
    return None


async def resolve_context_window(registry: ModelRegistry, meeting: Meeting | None,
                                 fallback: int, client_factory=httpx.AsyncClient) -> int:
    managed = (registry.get_default_model("rag") or registry.get_default_model("llm")) if meeting else registry.get_default_model("llm")
    if managed:
        model, provider, api_key = managed
        protocol, base_url, model_id = provider.protocol, provider.base_url.rstrip("/"), model.model_id
    elif settings.llm.provider == "ollama":
        protocol, base_url, model_id, api_key = "ollama", settings.ollama.base_url.rstrip("/"), settings.llm.model, ""
    else:
        return fallback
    if protocol not in {"ollama", "openai_compatible"}:
        return fallback
    cache_key = (protocol, base_url, model_id)
    cached = _cache.get(cache_key)
    if cached and cached[0] > time.monotonic():
        return cached[1]
    try:
        async with client_factory(timeout=3) as client:
            if protocol == "ollama":
                response = await client.post(f"{base_url}/api/show", json={"model": model_id})
                response.raise_for_status()
                detected = context_window_from_metadata(protocol, response.json())
            else:
                headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
                try:
                    response = await client.get(f"{base_url}/models/{quote(model_id, safe='')}", headers=headers)
                    response.raise_for_status()
                    detected = context_window_from_metadata(protocol, response.json())
                except httpx.HTTPError:
                    detected = None
                if not detected:
                    response = await client.get(f"{base_url}/models", headers=headers)
                    response.raise_for_status()
                    entry = next((item for item in response.json().get("data", []) if item.get("id") == model_id), {})
                    detected = context_window_from_metadata(protocol, entry)
    except (httpx.HTTPError, ValueError, TypeError):
        detected = None
    result = detected or fallback
    _cache[cache_key] = (time.monotonic() + 900, result)
    return result
