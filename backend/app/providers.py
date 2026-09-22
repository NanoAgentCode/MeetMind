from typing import Any

from .models import ModelConfig, Provider


def build_managed_chat_model(model: ModelConfig, provider: Provider, api_key: str) -> Any:
    """Build a chat client from a model managed in the database."""
    if provider.protocol in {"openai", "openai_compatible"}:
        if provider.protocol == "openai" and not api_key:
            raise ValueError("该供应商尚未配置 API Key")
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model.model_id,
            api_key=api_key or "EMPTY",
            base_url=provider.base_url,
            temperature=0,
        )
    if provider.protocol == "anthropic":
        if not api_key:
            raise ValueError("该供应商尚未配置 API Key")
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model.model_id,
            api_key=api_key,
            base_url=provider.base_url,
            temperature=0,
        )
    if provider.protocol == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(model=model.model_id, base_url=provider.base_url, temperature=0)
    raise ValueError(f"不支持的供应商协议：{provider.protocol}")
