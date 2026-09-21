import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .config import settings
from .models import ModelConfig, ModelConfigInput, Provider, ProviderInput


def _mask_secret(secret: str) -> str:
    if not secret:
        return ""
    if len(secret) <= 8:
        return "••••••••"
    return f"{secret[:3]}••••{secret[-4:]}"


class ModelRegistry:
    def __init__(self, database_path: Path | str | None = None):
        self.database_path = Path(database_path or settings.database.path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_database()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize_database(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS model_providers (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    protocol TEXT NOT NULL,
                    base_url TEXT NOT NULL,
                    api_key TEXT NOT NULL DEFAULT '',
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS model_configs (
                    id TEXT PRIMARY KEY,
                    provider_id TEXT NOT NULL REFERENCES model_providers(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    model_type TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    is_default INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS model_configs_one_default
                    ON model_configs(model_type) WHERE is_default = 1;
                """
            )

    def list_providers(self) -> list[Provider]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM model_providers ORDER BY created_at DESC").fetchall()
        return [self._provider_from_row(row) for row in rows]

    def get_provider(self, provider_id: str) -> Provider | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM model_providers WHERE id = ?", (provider_id,)).fetchone()
        return self._provider_from_row(row) if row else None

    def get_provider_credentials(self, provider_id: str) -> tuple[Provider, str] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM model_providers WHERE id = ?", (provider_id,)).fetchone()
        return (self._provider_from_row(row), row["api_key"]) if row else None

    def save_provider(self, provider_id: str, data: ProviderInput) -> Provider:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT api_key, created_at FROM model_providers WHERE id = ?", (provider_id,)
            ).fetchone()
            api_key = data.api_key or (existing["api_key"] if existing else "")
            created_at = existing["created_at"] if existing else now
            connection.execute(
                """
                INSERT INTO model_providers (id, name, protocol, base_url, api_key, enabled, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name, protocol = excluded.protocol, base_url = excluded.base_url,
                    api_key = excluded.api_key, enabled = excluded.enabled
                """,
                (provider_id, data.name, data.protocol, data.base_url.rstrip("/"), api_key, data.enabled, created_at),
            )
        return self.get_provider(provider_id)  # type: ignore[return-value]

    def delete_provider(self, provider_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM model_providers WHERE id = ?", (provider_id,))
        return cursor.rowcount > 0

    def list_models(self) -> list[ModelConfig]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM model_configs ORDER BY created_at DESC").fetchall()
        return [self._model_from_row(row) for row in rows]

    def get_model(self, model_config_id: str) -> ModelConfig | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM model_configs WHERE id = ?", (model_config_id,)).fetchone()
        return self._model_from_row(row) if row else None

    def get_default_model(self, model_type: str) -> tuple[ModelConfig, Provider, str] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT m.*, p.id AS p_id, p.name AS p_name, p.protocol, p.base_url, p.api_key,
                       p.enabled AS p_enabled, p.created_at AS p_created_at
                FROM model_configs m JOIN model_providers p ON p.id = m.provider_id
                WHERE m.model_type = ? AND m.is_default = 1 AND m.enabled = 1 AND p.enabled = 1
                """,
                (model_type,),
            ).fetchone()
        if not row:
            return None
        model = self._model_from_row(row)
        provider = Provider(
            id=row["p_id"], name=row["p_name"], protocol=row["protocol"], base_url=row["base_url"],
            enabled=bool(row["p_enabled"]), api_key_configured=bool(row["api_key"]),
            api_key_masked=_mask_secret(row["api_key"]), created_at=row["p_created_at"],
        )
        return model, provider, row["api_key"]

    def save_model(self, model_config_id: str, data: ModelConfigInput) -> ModelConfig:
        if not self.get_provider(data.provider_id):
            raise KeyError("供应商不存在")
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT created_at FROM model_configs WHERE id = ?", (model_config_id,)
            ).fetchone()
            created_at = existing["created_at"] if existing else now
            if data.is_default:
                connection.execute("UPDATE model_configs SET is_default = 0 WHERE model_type = ?", (data.model_type,))
            connection.execute(
                """
                INSERT INTO model_configs (id, provider_id, name, model_id, model_type, enabled, is_default, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    provider_id = excluded.provider_id, name = excluded.name, model_id = excluded.model_id,
                    model_type = excluded.model_type, enabled = excluded.enabled, is_default = excluded.is_default
                """,
                (model_config_id, data.provider_id, data.name, data.model_id, data.model_type,
                 data.enabled, data.is_default, created_at),
            )
        return self.get_model(model_config_id)  # type: ignore[return-value]

    def delete_model(self, model_config_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM model_configs WHERE id = ?", (model_config_id,))
        return cursor.rowcount > 0

    @staticmethod
    def _provider_from_row(row: sqlite3.Row) -> Provider:
        return Provider(
            id=row["id"], name=row["name"], protocol=row["protocol"], base_url=row["base_url"],
            enabled=bool(row["enabled"]), api_key_configured=bool(row["api_key"]),
            api_key_masked=_mask_secret(row["api_key"]), created_at=row["created_at"],
        )

    @staticmethod
    def _model_from_row(row: sqlite3.Row) -> ModelConfig:
        return ModelConfig(
            id=row["id"], provider_id=row["provider_id"], name=row["name"], model_id=row["model_id"],
            model_type=row["model_type"], enabled=bool(row["enabled"]), is_default=bool(row["is_default"]),
            created_at=row["created_at"],
        )


model_registry = ModelRegistry()
