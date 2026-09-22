from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ENV_FILE = Path(__file__).parents[1] / ".env"


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")
    host: str = Field(default="127.0.0.1", validation_alias="APP_HOST")
    port: int = Field(default=8000, validation_alias="APP_PORT")
    max_upload_mb: int = Field(default=200, validation_alias="MAX_UPLOAD_MB")
    background_audio_mb: int = Field(default=20, validation_alias="BACKGROUND_AUDIO_MB")
    admin_username: str = Field(default="", validation_alias="ADMIN_USERNAME")
    admin_password: str = Field(default="", validation_alias="ADMIN_PASSWORD")
    cookie_secure: bool = Field(default=False, validation_alias="COOKIE_SECURE")
    chat_context_window_tokens: int = Field(default=262144, ge=512, validation_alias="CHAT_CONTEXT_WINDOW_TOKENS")


class RustFSSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_prefix="RUSTFS_", extra="ignore")
    endpoint: str = "http://localhost:9000"
    access_key: str = "huizhi-local-access"
    secret_key: str = "huizhi-local-secret-change-before-production"
    bucket: str = "huizhi-meetings"
    region: str = "us-east-1"


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_prefix="DATABASE_", extra="ignore")
    path: Path = Path(__file__).parents[1] / "data" / "meetmind.db"


class Settings(BaseModel):
    app: AppSettings = Field(default_factory=AppSettings)
    rustfs: RustFSSettings = Field(default_factory=RustFSSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)


settings = Settings()
