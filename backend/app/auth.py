"""Minimal local accounts and revocable cookie sessions.

User IDs are stable so future role and department tables can reference them.
"""

import hashlib
import hmac
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import settings


class AuthStore:
    def __init__(self, database_path: Path | str | None = None):
        self.database_path = Path(database_path or settings.database.path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL, display_name TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );
            """)

    def _connect(self):
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _hash_password(password: str, salt: bytes | None = None) -> str:
        salt = salt or secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
        return f"{salt.hex()}:{digest.hex()}"

    def bootstrap_admin(self):
        username, password = settings.app.admin_username.strip(), settings.app.admin_password
        if not username or not password:
            return
        with self._connect() as connection:
            if connection.execute("SELECT 1 FROM users LIMIT 1").fetchone():
                return
            user_id = secrets.token_hex(16)
            connection.execute(
                "INSERT INTO users VALUES (?, ?, ?, ?)",
                (user_id, username, self._hash_password(password), "系统管理员"),
            )
            if connection.execute("SELECT 1 FROM sqlite_master WHERE name = 'meetings'").fetchone():
                connection.execute("UPDATE meetings SET owner_id = ? WHERE owner_id IS NULL", (user_id,))

    def authenticate(self, username: str, password: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if not row:
            return None
        salt_hex, expected_hex = row["password_hash"].split(":", 1)
        actual = self._hash_password(password, bytes.fromhex(salt_hex)).split(":", 1)[1]
        if not hmac.compare_digest(actual, expected_hex):
            return None
        return {"id": row["id"], "username": row["username"], "display_name": row["display_name"]}

    def create_session(self, user_id: str) -> str:
        token = secrets.token_urlsafe(32)
        expires = datetime.now(timezone.utc) + timedelta(days=7)
        with self._connect() as connection:
            connection.execute("INSERT INTO sessions VALUES (?, ?, ?)", (self._token_hash(token), user_id, expires.isoformat()))
        return token

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def get_user(self, token: str | None) -> dict | None:
        if not token:
            return None
        with self._connect() as connection:
            row = connection.execute(
                "SELECT users.id, users.username, users.display_name, sessions.expires_at "
                "FROM sessions JOIN users ON users.id = sessions.user_id WHERE sessions.token_hash = ?",
                (self._token_hash(token),),
            ).fetchone()
        if not row or datetime.fromisoformat(row["expires_at"]) <= datetime.now(timezone.utc):
            return None
        return {"id": row["id"], "username": row["username"], "display_name": row["display_name"]}

    def delete_session(self, token: str | None):
        if token:
            with self._connect() as connection:
                connection.execute("DELETE FROM sessions WHERE token_hash = ?", (self._token_hash(token),))


auth_store = AuthStore()
