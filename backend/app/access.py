"""Request models and permission rules for access management."""

from fastapi import HTTPException
from pydantic import BaseModel, Field

from .auth import MEMBER_ROLE_ID


class LoginInput(BaseModel):
    username: str
    password: str


class UserCreateInput(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    display_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=256)
    department_id: str | None = None
    role_ids: list[str] = Field(default_factory=lambda: [MEMBER_ROLE_ID])


class UserUpdateInput(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)
    department_id: str | None = None
    is_active: bool = True
    role_ids: list[str] = Field(min_length=1)
    password: str | None = Field(default=None, min_length=8, max_length=256)


class RoleInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=300)
    permissions: list[str] = Field(default_factory=list)


class DepartmentInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    parent_id: str | None = None
    sort_order: int = 0


def has_permission(user: dict, permission: str) -> bool:
    return permission in user.get("permissions", [])


def require_permission(user: dict, *permissions: str):
    if not any(has_permission(user, permission) for permission in permissions):
        raise HTTPException(403, "权限不足")


def required_route_permissions(path: str, method: str) -> tuple[str, ...]:
    if path.startswith("/api/users"):
        return ("user:read", "user:manage") if method == "GET" else ("user:manage",)
    if path.startswith("/api/roles"):
        return ("role:read", "role:manage", "user:manage") if method == "GET" else ("role:manage",)
    if path.startswith("/api/departments"):
        return ("department:read", "department:manage", "user:manage") if method == "GET" else ("department:manage",)
    if path.startswith(("/api/model-providers", "/api/model-configs")):
        return ("model:read", "model:manage") if method == "GET" else ("model:manage",)
    if path == "/api/chat" or path.endswith("/questions"):
        return ("chat:use",)
    if path == "/api/meetings" and method == "POST":
        return ("meeting:create",)
    if path.startswith("/api/meetings"):
        if method == "GET":
            return ("meeting:read_own", "meeting:read_department", "meeting:read_all",
                    "meeting:manage_own", "meeting:manage_department", "meeting:manage_all")
        return ("meeting:manage_own", "meeting:manage_department", "meeting:manage_all")
    return ()
