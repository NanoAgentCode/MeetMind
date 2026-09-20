from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ENV_FILE = Path(__file__).parents[1] / ".env"


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")
    max_upload_mb: int = 200


class ASRSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_prefix="ASR_", extra="ignore")
    backend: str = "demo"
    model: str = "whisper-1"


class LLMSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_prefix="LLM_", extra="ignore")
    provider: str = "demo"
    model: str = "gpt-4o-mini"


class OpenAISettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_prefix="OPENAI_", extra="ignore")
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"


class AnthropicSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_prefix="ANTHROPIC_", extra="ignore")
    api_key: str = ""
    base_url: str = "https://api.anthropic.com"


class OllamaSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_prefix="OLLAMA_", extra="ignore")
    base_url: str = "http://localhost:11434"


class VLLMSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_prefix="VLLM_", extra="ignore")
    base_url: str = "http://localhost:8000/v1"
    api_key: str = "EMPTY"


class RustFSSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_prefix="RUSTFS_", extra="ignore")
    endpoint: str = "http://localhost:9000"
    access_key: str = "huizhi-local-access"
    secret_key: str = "huizhi-local-secret-change-before-production"
    bucket: str = "huizhi-meetings"
    region: str = "us-east-1"


class Settings(BaseModel):
    app: AppSettings = Field(default_factory=AppSettings)
    asr: ASRSettings = Field(default_factory=ASRSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    openai: OpenAISettings = Field(default_factory=OpenAISettings)
    anthropic: AnthropicSettings = Field(default_factory=AnthropicSettings)
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)
    vllm: VLLMSettings = Field(default_factory=VLLMSettings)
    rustfs: RustFSSettings = Field(default_factory=RustFSSettings)


settings = Settings()
