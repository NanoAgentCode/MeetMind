from typing import Any

from .config import Settings, settings


SUPPORTED_LLM_PROVIDERS = ("demo", "openai", "anthropic", "ollama", "vllm")


def build_chat_model(config: Settings = settings) -> Any | None:
    """Create a LangChain chat model for the configured protocol.

    Demo deliberately returns None so the workflow can use its deterministic
    fallback without credentials or a running model server.
    """
    provider = config.llm_provider.lower().strip()
    if provider == "demo":
        return None
    if provider == "openai":
        if not config.openai_api_key:
            raise ValueError("使用 OpenAI 模型前请配置 OPENAI_API_KEY")
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=config.llm_model,
            api_key=config.openai_api_key,
            base_url=config.openai_base_url,
            temperature=0,
        )
    if provider == "anthropic":
        if not config.anthropic_api_key:
            raise ValueError("使用 Claude 模型前请配置 ANTHROPIC_API_KEY")
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=config.llm_model,
            api_key=config.anthropic_api_key,
            base_url=config.anthropic_base_url,
            temperature=0,
        )
    if provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=config.llm_model,
            base_url=config.ollama_base_url,
            temperature=0,
            format="json",
        )
    if provider == "vllm":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=config.llm_model,
            api_key=config.vllm_api_key or "EMPTY",
            base_url=config.vllm_base_url,
            temperature=0,
        )
    supported = "、".join(SUPPORTED_LLM_PROVIDERS)
    raise ValueError(f"不支持的 LLM_PROVIDER：{config.llm_provider}，可选值：{supported}")
