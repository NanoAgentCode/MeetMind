"""Authentication, notifications and access-management routes."""

from collections.abc import Callable

from fastapi import APIRouter, HTTPException, Request, Response as FastAPIResponse

from .access import (
    DepartmentInput, LoginInput, RoleInput, UserCreateInput, UserUpdateInput,
    has_permission, require_permission,
)
from .auth import ADMIN_ROLE_ID, MEMBER_ROLE_ID, PERMISSIONS, AuthStore
from .config import settings
from .store import MeetingStore


def create_access_router(get_auth_store: Callable[[], AuthStore], get_store: Callable[[], MeetingStore]) -> APIRouter:
    router = APIRouter()

    @router.post("/api/auth/login")
    def login(data: LoginInput, response: FastAPIResponse):
        get_auth_store().bootstrap_admin()
        if not get_auth_store().has_users():
            raise HTTPException(503, "请先配置 ADMIN_USERNAME 和 ADMIN_PASSWORD")
        user = get_auth_store().authenticate(data.username, data.password)
        if not user:
            raise HTTPException(401, "账号或密码错误")
        token = get_auth_store().create_session(user["id"])
        response.set_cookie("meetmind_session", token, max_age=7 * 86400, httponly=True, samesite="lax", secure=settings.app.cookie_secure)
        return user

    @router.post("/api/auth/logout", status_code=204)
    def logout(request: Request, response: FastAPIResponse):
        get_auth_store().delete_session(request.cookies.get("meetmind_session"))
        response.delete_cookie("meetmind_session")

    @router.get("/api/auth/me")
    def current_user(request: Request):
        return request.state.user

    @router.get("/api/notifications")
    def list_notifications(request: Request):
        return get_store().list_notifications(request.state.user["id"])

    @router.post("/api/notifications/{notification_id}/read", status_code=204)
    def mark_notification_read(notification_id: str, request: Request):
        if not get_store().mark_notification_read(notification_id, request.state.user["id"]):
            raise HTTPException(404, "通知不存在")

    def _management_error(exc: Exception):
        if isinstance(exc, KeyError):
            raise HTTPException(404, str(exc.args[0])) from exc
        raise HTTPException(409, str(exc)) from exc

    def _protect_admin_target(actor: dict, target: dict | None):
        if target and ADMIN_ROLE_ID in target["role_ids"] and ADMIN_ROLE_ID not in actor["role_ids"]:
            raise HTTPException(403, "只有系统管理员可以管理管理员账号")

    def _check_role_assignment(actor: dict, role_ids: list[str]):
        if not has_permission(actor, "role:manage") and set(role_ids) != {MEMBER_ROLE_ID}:
            raise HTTPException(403, "分配角色需要角色管理权限")
        if ADMIN_ROLE_ID in role_ids and ADMIN_ROLE_ID not in actor["role_ids"]:
            raise HTTPException(403, "只有系统管理员可以分配管理员角色")

    @router.get("/api/permissions")
    def list_permissions(request: Request):
        require_permission(request.state.user, "role:read", "role:manage")
        return [{"key": key, "label": label} for key, label in PERMISSIONS.items()]

    @router.get("/api/users")
    def list_users():
        return get_auth_store().list_users()

    @router.post("/api/users", status_code=201)
    def create_user(data: UserCreateInput, request: Request):
        _check_role_assignment(request.state.user, data.role_ids)
        try:
            return get_auth_store().create_user(data.username, data.display_name, data.password, data.department_id, data.role_ids)
        except (ValueError, KeyError) as exc:
            _management_error(exc)

    @router.put("/api/users/{user_id}")
    def update_user(user_id: str, data: UserUpdateInput, request: Request):
        target = get_auth_store().get_user_by_id(user_id)
        _protect_admin_target(request.state.user, target)
        if target and set(data.role_ids) != set(target["role_ids"]):
            _check_role_assignment(request.state.user, data.role_ids)
            require_permission(request.state.user, "role:manage")
        try:
            return get_auth_store().update_user(user_id, data.display_name, data.department_id, data.is_active, data.role_ids, data.password)
        except (ValueError, KeyError) as exc:
            _management_error(exc)

    @router.delete("/api/users/{user_id}", status_code=204)
    def delete_user(user_id: str, request: Request):
        _protect_admin_target(request.state.user, get_auth_store().get_user_by_id(user_id))
        try:
            get_auth_store().delete_user(user_id, request.state.user["id"])
        except (ValueError, KeyError) as exc:
            _management_error(exc)

    @router.get("/api/roles")
    def list_roles():
        return get_auth_store().list_roles()

    @router.post("/api/roles", status_code=201)
    def create_role(data: RoleInput):
        try:
            return get_auth_store().save_role(None, data.name, data.description, data.permissions)
        except (ValueError, KeyError) as exc:
            _management_error(exc)

    @router.put("/api/roles/{role_id}")
    def update_role(role_id: str, data: RoleInput):
        try:
            return get_auth_store().save_role(role_id, data.name, data.description, data.permissions)
        except (ValueError, KeyError) as exc:
            _management_error(exc)

    @router.delete("/api/roles/{role_id}", status_code=204)
    def delete_role(role_id: str):
        try:
            get_auth_store().delete_role(role_id)
        except (ValueError, KeyError) as exc:
            _management_error(exc)

    @router.get("/api/departments")
    def list_departments():
        return get_auth_store().list_departments()

    @router.post("/api/departments", status_code=201)
    def create_department(data: DepartmentInput):
        try:
            return get_auth_store().save_department(None, data.name, data.parent_id, data.sort_order)
        except (ValueError, KeyError) as exc:
            _management_error(exc)

    @router.put("/api/departments/{department_id}")
    def update_department(department_id: str, data: DepartmentInput):
        try:
            return get_auth_store().save_department(department_id, data.name, data.parent_id, data.sort_order)
        except (ValueError, KeyError) as exc:
            _management_error(exc)

    @router.delete("/api/departments/{department_id}", status_code=204)
    def delete_department(department_id: str):
        try:
            get_auth_store().delete_department(department_id)
        except (ValueError, KeyError) as exc:
            _management_error(exc)

    return router
