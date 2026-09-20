from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=Path(__file__).parents[1] / ".env", extra="ignore")

    asr_backend: str = "demo"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    asr_model: str = "whisper-1"
    llm_model: str = "gpt-4o-mini"
    max_upload_mb: int = 200
    rustfs_endpoint: str = "http://localhost:9000"
    rustfs_access_key: str = "huizhi-local-access"
    rustfs_secret_key: str = "huizhi-local-secret-change-before-production"
    rustfs_bucket: str = "huizhi-meetings"
    rustfs_region: str = "us-east-1"


settings = Settings()
