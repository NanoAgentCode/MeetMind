from typing import Any

from .config import Settings, settings
from .models import ModelConfig, Provider


SUPPORTED_LLM_PROVIDERS = ("demo", "openai", "anthropic", "ollama", "vllm")


def build_chat_model(config: Settings = settings) -> Any | None:
    """Create a LangChain chat model for the configured protocol.

    Demo deliberately returns None so the workflow can use its deterministic
    fallback without credentials or a running model server.
    """
    provider = config.llm.provider.lower().strip()
    if provider == "demo":
        return None
    if provider == "openai":
        if not config.openai.api_key:
            raise ValueError("使用 OpenAI 模型前请配置 OPENAI_API_KEY")
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=config.llm.model,
            api_key=config.openai.api_key,
            base_url=config.openai.base_url,
            temperature=0,
        )
    if provider == "anthropic":
        if not config.anthropic.api_key:
            raise ValueError("使用 Claude 模型前请配置 ANTHROPIC_API_KEY")
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=config.llm.model,
            api_key=config.anthropic.api_key,
            base_url=config.anthropic.base_url,
            temperature=0,
        )
    if provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=config.llm.model,
            base_url=config.ollama.base_url,
            temperature=0,
            format="json",
        )
    if provider == "vllm":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=config.llm.model,
            api_key=config.vllm.api_key or "EMPTY",
            base_url=config.vllm.base_url,
            temperature=0,
        )
    supported = "、".join(SUPPORTED_LLM_PROVIDERS)
    raise ValueError(f"不支持的 LLM_PROVIDER：{config.llm.provider}，可选值：{supported}")


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
