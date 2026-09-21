"""Fetch available model identifiers from a configured provider."""

import httpx
from fastapi import HTTPException

from .model_registry import ModelRegistry


async def fetch_provider_models(provider_id: str, registry: ModelRegistry, client_factory=httpx.AsyncClient) -> list[str]:
    credentials = registry.get_provider_credentials(provider_id)
    if not credentials:
        raise HTTPException(404, "供应商不存在")
    provider, api_key = credentials
    if not provider.enabled:
        raise HTTPException(409, "请先启用供应商")
    if provider.protocol in {"openai", "openai_compatible"}:
        url = f"{provider.base_url.rstrip('/')}/models"
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    elif provider.protocol == "anthropic":
        base_url = provider.base_url.rstrip("/")
        url = f"{base_url}/models" if base_url.endswith("/v1") else f"{base_url}/v1/models"
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
    else:
        url = f"{provider.base_url.rstrip('/')}/api/tags"
        headers = {}
    try:
        async with client_factory(timeout=15) as client:
            response = await client.get(url, headers=headers)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"获取模型列表失败：{exc}") from exc
    payload = response.json()
    if provider.protocol == "ollama":
        model_ids = [item.get("name") or item.get("model") for item in payload.get("models", [])]
    else:
        model_ids = [item.get("id") for item in payload.get("data", [])]
    return sorted({model_id for model_id in model_ids if isinstance(model_id, str) and model_id.strip()})
