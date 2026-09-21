"""Model provider and configuration routes."""

from collections.abc import Callable
from uuid import uuid4

import httpx
from fastapi import APIRouter, HTTPException

from .model_registry import ModelRegistry
from .models import ModelConfig, ModelConfigInput, Provider, ProviderInput
from .provider_catalog import fetch_provider_models


def create_model_router(get_model_registry: Callable[[], ModelRegistry], get_http_client: Callable[[], type[httpx.AsyncClient]]) -> APIRouter:
    router = APIRouter()

    @router.get("/api/model-providers", response_model=list[Provider])
    def list_model_providers():
        return get_model_registry().list_providers()

    @router.post("/api/model-providers", response_model=Provider, status_code=201)
    def create_model_provider(data: ProviderInput):
        return get_model_registry().save_provider(uuid4().hex, data)

    @router.put("/api/model-providers/{provider_id}", response_model=Provider)
    def update_model_provider(provider_id: str, data: ProviderInput):
        if not get_model_registry().get_provider(provider_id):
            raise HTTPException(404, "供应商不存在")
        return get_model_registry().save_provider(provider_id, data)

    @router.delete("/api/model-providers/{provider_id}", status_code=204)
    def delete_model_provider(provider_id: str):
        if not get_model_registry().delete_provider(provider_id):
            raise HTTPException(404, "供应商不存在")

    async def _fetch_provider_models(provider_id: str) -> list[str]:
        return await fetch_provider_models(provider_id, get_model_registry(), get_http_client())

    @router.get("/api/model-providers/{provider_id}/models")
    async def list_provider_models(provider_id: str):
        return {"models": await _fetch_provider_models(provider_id)}

    @router.post("/api/model-providers/{provider_id}/test")
    async def test_model_provider(provider_id: str):
        await _fetch_provider_models(provider_id)
        return {"status": "ok", "message": "连接成功"}

    @router.get("/api/model-configs", response_model=list[ModelConfig])
    def list_model_configs():
        return get_model_registry().list_models()

    @router.post("/api/model-configs", response_model=ModelConfig, status_code=201)
    def create_model_config(data: ModelConfigInput):
        try:
            return get_model_registry().save_model(uuid4().hex, data)
        except KeyError as exc:
            raise HTTPException(400, str(exc.args[0])) from exc

    @router.put("/api/model-configs/{model_config_id}", response_model=ModelConfig)
    def update_model_config(model_config_id: str, data: ModelConfigInput):
        if not get_model_registry().get_model(model_config_id):
            raise HTTPException(404, "模型配置不存在")
        try:
            return get_model_registry().save_model(model_config_id, data)
        except KeyError as exc:
            raise HTTPException(400, str(exc.args[0])) from exc

    @router.delete("/api/model-configs/{model_config_id}", status_code=204)
    def delete_model_config(model_config_id: str):
        if not get_model_registry().delete_model(model_config_id):
            raise HTTPException(404, "模型配置不存在")

    return router
