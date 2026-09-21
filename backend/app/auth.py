"""Local accounts, role permissions, department hierarchy and revocable sessions."""

import hashlib
import hmac
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import settings


PERMISSIONS = {
    "meeting:create": "创建会议",
    "meeting:read_own": "查看本人会议",
    "meeting:read_department": "查看本部门及下级会议",
    "meeting:read_all": "查看全部会议",
    "meeting:manage_own": "处理本人会议",
    "meeting:manage_department": "处理本部门及下级会议",
    "meeting:manage_all": "处理全部会议",
    "chat:use": "使用会议问答",
    "model:read": "查看模型配置",
    "model:manage": "管理模型配置",
    "user:read": "查看用户",
    "user:manage": "管理用户及其角色",
    "role:read": "查看角色",
    "role:manage": "管理角色与权限",
    "department:read": "查看部门",
    "department:manage": "管理部门",
}
MEMBER_PERMISSIONS = {
    "meeting:create", "meeting:read_own", "meeting:manage_own", "chat:use", "model:read",
}
ADMIN_ROLE_ID = "system-admin"
MEMBER_ROLE_ID = "member"


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
                CREATE TABLE IF NOT EXISTS departments (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, parent_id TEXT,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (parent_id) REFERENCES departments(id)
                );
                CREATE TABLE IF NOT EXISTS roles (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE,
                    description TEXT NOT NULL DEFAULT '', is_system INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS role_permissions (
                    role_id TEXT NOT NULL, permission TEXT NOT NULL,
                    PRIMARY KEY (role_id, permission),
                    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS user_roles (
                    user_id TEXT NOT NULL, role_id TEXT NOT NULL,
                    PRIMARY KEY (user_id, role_id),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
                );
            """)
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(users)")}
            if "department_id" not in columns:
                connection.execute("ALTER TABLE users ADD COLUMN department_id TEXT")
            if "is_active" not in columns:
                connection.execute("ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")
            connection.execute("INSERT OR IGNORE INTO roles VALUES (?, ?, ?, 1)", (ADMIN_ROLE_ID, "系统管理员", "拥有全部权限"))
            connection.execute("INSERT OR IGNORE INTO roles VALUES (?, ?, ?, 1)", (MEMBER_ROLE_ID, "普通成员", "仅管理自己的会议"))
            connection.executemany(
                "INSERT OR IGNORE INTO role_permissions VALUES (?, ?)",
                [(ADMIN_ROLE_ID, key) for key in PERMISSIONS] + [(MEMBER_ROLE_ID, key) for key in MEMBER_PERMISSIONS],
            )

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _hash_password(password: str, salt: bytes | None = None) -> str:
        salt = salt or secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
        return f"{salt.hex()}:{digest.hex()}"

    def bootstrap_admin(self):
        username, password = settings.app.admin_username.strip(), settings.app.admin_password
        with self._connect() as connection:
            first = connection.execute("SELECT id FROM users ORDER BY rowid LIMIT 1").fetchone()
            if not first and username and password:
                user_id = secrets.token_hex(16)
                connection.execute(
                    "INSERT INTO users (id, username, password_hash, display_name) VALUES (?, ?, ?, ?)",
                    (user_id, username, self._hash_password(password), "系统管理员"),
                )
                first = {"id": user_id}
                if connection.execute("SELECT 1 FROM sqlite_master WHERE name = 'meetings'").fetchone():
                    connection.execute("UPDATE meetings SET owner_id = ? WHERE owner_id IS NULL", (user_id,))
            if not first:
                return
            if not connection.execute("SELECT 1 FROM user_roles WHERE role_id = ?", (ADMIN_ROLE_ID,)).fetchone():
                preferred = connection.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
                connection.execute("INSERT OR IGNORE INTO user_roles VALUES (?, ?)", ((preferred or first)["id"], ADMIN_ROLE_ID))
            connection.execute(
                "INSERT OR IGNORE INTO user_roles SELECT id, ? FROM users WHERE id NOT IN "
                "(SELECT user_id FROM user_roles)", (MEMBER_ROLE_ID,),
            )

    def has_users(self) -> bool:
        with self._connect() as connection:
            return connection.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None

    def _public_user(self, connection: sqlite3.Connection, row: sqlite3.Row) -> dict:
        role_ids = [item["role_id"] for item in connection.execute(
            "SELECT role_id FROM user_roles WHERE user_id = ? ORDER BY role_id", (row["id"],)
        )]
        permissions = [item["permission"] for item in connection.execute(
            "SELECT DISTINCT rp.permission FROM role_permissions rp JOIN user_roles ur ON ur.role_id = rp.role_id "
            "WHERE ur.user_id = ? ORDER BY rp.permission", (row["id"],)
        )]
        return {
            "id": row["id"], "username": row["username"], "display_name": row["display_name"],
            "department_id": row["department_id"], "is_active": bool(row["is_active"]),
            "role_ids": role_ids, "permissions": permissions,
        }

    def authenticate(self, username: str, password: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM users WHERE username = ? AND is_active = 1", (username,)).fetchone()
            if not row:
                return None
            salt_hex, expected_hex = row["password_hash"].split(":", 1)
            actual = self._hash_password(password, bytes.fromhex(salt_hex)).split(":", 1)[1]
            return self._public_user(connection, row) if hmac.compare_digest(actual, expected_hex) else None

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
                "SELECT users.*, sessions.expires_at "
                "FROM sessions JOIN users ON users.id = sessions.user_id WHERE sessions.token_hash = ? AND users.is_active = 1",
                (self._token_hash(token),),
            ).fetchone()
            if not row or datetime.fromisoformat(row["expires_at"]) <= datetime.now(timezone.utc):
                return None
            return self._public_user(connection, row)

    def delete_session(self, token: str | None):
        if token:
            with self._connect() as connection:
                connection.execute("DELETE FROM sessions WHERE token_hash = ?", (self._token_hash(token),))

    def list_users(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM users ORDER BY username").fetchall()
            return [self._public_user(connection, row) for row in rows]

    def get_user_by_id(self, user_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return self._public_user(connection, row) if row else None

    def _validate_links(self, connection, department_id: str | None, role_ids: list[str]):
        if department_id and not connection.execute("SELECT 1 FROM departments WHERE id = ?", (department_id,)).fetchone():
            raise ValueError("部门不存在")
        if not role_ids:
            raise ValueError("至少选择一个角色")
        known = {row["id"] for row in connection.execute("SELECT id FROM roles")}
        if set(role_ids) - known:
            raise ValueError("角色不存在")

    def create_user(self, username: str, display_name: str, password: str, department_id: str | None, role_ids: list[str]) -> dict:
        user_id = secrets.token_hex(16)
        with self._connect() as connection:
            self._validate_links(connection, department_id, role_ids)
            try:
                connection.execute(
                    "INSERT INTO users (id, username, password_hash, display_name, department_id) VALUES (?, ?, ?, ?, ?)",
                    (user_id, username, self._hash_password(password), display_name, department_id),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError("账号已存在") from exc
            connection.executemany("INSERT INTO user_roles VALUES (?, ?)", [(user_id, role_id) for role_id in set(role_ids)])
            row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return self._public_user(connection, row)

    def _is_last_admin(self, connection, user_id: str) -> bool:
        assigned = connection.execute("SELECT 1 FROM user_roles WHERE user_id = ? AND role_id = ?", (user_id, ADMIN_ROLE_ID)).fetchone()
        if not assigned:
            return False
        count = connection.execute(
            "SELECT COUNT(*) FROM users u JOIN user_roles ur ON ur.user_id = u.id "
            "WHERE ur.role_id = ? AND u.is_active = 1", (ADMIN_ROLE_ID,),
        ).fetchone()[0]
        return count <= 1

    def update_user(self, user_id: str, display_name: str, department_id: str | None, is_active: bool, role_ids: list[str], password: str | None = None) -> dict:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if not row:
                raise KeyError("用户不存在")
            self._validate_links(connection, department_id, role_ids)
            if self._is_last_admin(connection, user_id) and (not is_active or ADMIN_ROLE_ID not in role_ids):
                raise ValueError("不能移除或停用最后一名系统管理员")
            connection.execute(
                "UPDATE users SET display_name = ?, department_id = ?, is_active = ? WHERE id = ?",
                (display_name, department_id, int(is_active), user_id),
            )
            if password:
                connection.execute("UPDATE users SET password_hash = ? WHERE id = ?", (self._hash_password(password), user_id))
                connection.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            if not is_active:
                connection.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            connection.execute("DELETE FROM user_roles WHERE user_id = ?", (user_id,))
            connection.executemany("INSERT INTO user_roles VALUES (?, ?)", [(user_id, role_id) for role_id in set(role_ids)])
            return self._public_user(connection, connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())

    def delete_user(self, user_id: str, actor_id: str):
        with self._connect() as connection:
            if user_id == actor_id:
                raise ValueError("不能删除当前登录用户")
            if not connection.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone():
                raise KeyError("用户不存在")
            if self._is_last_admin(connection, user_id):
                raise ValueError("不能删除最后一名系统管理员")
            if connection.execute("SELECT 1 FROM sqlite_master WHERE name = 'meetings'").fetchone():
                if connection.execute("SELECT 1 FROM meetings WHERE owner_id = ? LIMIT 1", (user_id,)).fetchone():
                    raise ValueError("用户仍有关联会议，请先处理会议记录")
            connection.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            connection.execute("DELETE FROM user_roles WHERE user_id = ?", (user_id,))
            if connection.execute("SELECT 1 FROM sqlite_master WHERE name = 'notifications'").fetchone():
                connection.execute("DELETE FROM notifications WHERE user_id = ?", (user_id,))
            connection.execute("DELETE FROM users WHERE id = ?", (user_id,))

    def list_roles(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM roles ORDER BY is_system DESC, name").fetchall()
            return [self._role_from_row(connection, row) for row in rows]

    @staticmethod
    def _role_from_row(connection, row) -> dict:
        permissions = [item["permission"] for item in connection.execute(
            "SELECT permission FROM role_permissions WHERE role_id = ? ORDER BY permission", (row["id"],)
        )]
        members = connection.execute("SELECT COUNT(*) FROM user_roles WHERE role_id = ?", (row["id"],)).fetchone()[0]
        return {"id": row["id"], "name": row["name"], "description": row["description"],
                "is_system": bool(row["is_system"]), "permissions": permissions, "member_count": members}

    def save_role(self, role_id: str | None, name: str, description: str, permissions: list[str]) -> dict:
        if set(permissions) - PERMISSIONS.keys():
            raise ValueError("包含未知权限")
        with self._connect() as connection:
            if role_id:
                row = connection.execute("SELECT * FROM roles WHERE id = ?", (role_id,)).fetchone()
                if not row:
                    raise KeyError("角色不存在")
                if row["is_system"]:
                    raise ValueError("内置角色不可修改")
                try:
                    connection.execute("UPDATE roles SET name = ?, description = ? WHERE id = ?", (name, description, role_id))
                except sqlite3.IntegrityError as exc:
                    raise ValueError("角色名称已存在") from exc
                connection.execute("DELETE FROM role_permissions WHERE role_id = ?", (role_id,))
            else:
                role_id = secrets.token_hex(16)
                try:
                    connection.execute("INSERT INTO roles VALUES (?, ?, ?, 0)", (role_id, name, description))
                except sqlite3.IntegrityError as exc:
                    raise ValueError("角色名称已存在") from exc
            connection.executemany("INSERT INTO role_permissions VALUES (?, ?)", [(role_id, key) for key in set(permissions)])
            return self._role_from_row(connection, connection.execute("SELECT * FROM roles WHERE id = ?", (role_id,)).fetchone())

    def delete_role(self, role_id: str):
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM roles WHERE id = ?", (role_id,)).fetchone()
            if not row:
                raise KeyError("角色不存在")
            if row["is_system"]:
                raise ValueError("内置角色不可删除")
            if connection.execute("SELECT 1 FROM user_roles WHERE role_id = ?", (role_id,)).fetchone():
                raise ValueError("角色仍有成员，不能删除")
            connection.execute("DELETE FROM role_permissions WHERE role_id = ?", (role_id,))
            connection.execute("DELETE FROM roles WHERE id = ?", (role_id,))

    def list_departments(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM departments ORDER BY sort_order, name").fetchall()
            return [{"id": row["id"], "name": row["name"], "parent_id": row["parent_id"],
                     "sort_order": row["sort_order"], "member_count": connection.execute(
                         "SELECT COUNT(*) FROM users WHERE department_id = ?", (row["id"],)
                     ).fetchone()[0]} for row in rows]

    def descendant_department_ids(self, department_id: str) -> set[str]:
        with self._connect() as connection:
            rows = connection.execute(
                "WITH RECURSIVE descendants(id) AS (SELECT id FROM departments WHERE id = ? "
                "UNION ALL SELECT d.id FROM departments d JOIN descendants x ON d.parent_id = x.id) "
                "SELECT id FROM descendants", (department_id,),
            ).fetchall()
        return {row["id"] for row in rows}

    def save_department(self, department_id: str | None, name: str, parent_id: str | None, sort_order: int) -> dict:
        with self._connect() as connection:
            if parent_id and not connection.execute("SELECT 1 FROM departments WHERE id = ?", (parent_id,)).fetchone():
                raise ValueError("上级部门不存在")
            if department_id:
                if not connection.execute("SELECT 1 FROM departments WHERE id = ?", (department_id,)).fetchone():
                    raise KeyError("部门不存在")
                if parent_id in self.descendant_department_ids(department_id):
                    raise ValueError("不能将部门移动到自身或下级部门")
                connection.execute("UPDATE departments SET name = ?, parent_id = ?, sort_order = ? WHERE id = ?",
                                   (name, parent_id, sort_order, department_id))
            else:
                department_id = secrets.token_hex(16)
                connection.execute("INSERT INTO departments VALUES (?, ?, ?, ?)", (department_id, name, parent_id, sort_order))
            return {"id": department_id, "name": name, "parent_id": parent_id, "sort_order": sort_order,
                    "member_count": connection.execute("SELECT COUNT(*) FROM users WHERE department_id = ?", (department_id,)).fetchone()[0]}

    def delete_department(self, department_id: str):
        with self._connect() as connection:
            if not connection.execute("SELECT 1 FROM departments WHERE id = ?", (department_id,)).fetchone():
                raise KeyError("部门不存在")
            if connection.execute("SELECT 1 FROM departments WHERE parent_id = ?", (department_id,)).fetchone():
                raise ValueError("请先删除或移动下级部门")
            if connection.execute("SELECT 1 FROM users WHERE department_id = ?", (department_id,)).fetchone():
                raise ValueError("部门仍有成员，请先转移成员")
            connection.execute("DELETE FROM departments WHERE id = ?", (department_id,))


auth_store = AuthStore()
