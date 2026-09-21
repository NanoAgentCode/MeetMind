import sqlite3

from fastapi.testclient import TestClient

import backend.app.main as main_module
from backend.app.auth import AuthStore
from backend.app.config import settings
from backend.app.main import app
from backend.app.store import MeetingStore
from backend.tests.test_flow import MemoryObjectStorage


def setup(monkeypatch, tmp_path):
    database = tmp_path / "rbac.db"
    monkeypatch.setattr(main_module, "store", MeetingStore(MemoryObjectStorage(), database))
    monkeypatch.setattr(main_module, "auth_store", AuthStore(database))
    monkeypatch.setattr(settings.app, "admin_username", "admin")
    monkeypatch.setattr(settings.app, "admin_password", "admin-password")
    admin = TestClient(app)
    response = admin.post("/api/auth/login", json={"username": "admin", "password": "admin-password"})
    assert response.status_code == 200
    assert "role:manage" in response.json()["permissions"]
    return admin


def create_user(admin, username, department_id=None, role_ids=None):
    response = admin.post("/api/users", json={
        "username": username, "display_name": username, "password": "member-password",
        "department_id": department_id, "role_ids": role_ids or ["member"],
    })
    assert response.status_code == 201, response.text
    client = TestClient(app)
    assert client.post("/api/auth/login", json={"username": username, "password": "member-password"}).status_code == 200
    return response.json(), client


def upload(client, title):
    response = client.post("/api/meetings", data={"title": title}, files={"file": ("meeting.mp3", b"audio", "audio/mpeg")})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_member_cannot_manage_users_roles_departments_or_models(monkeypatch, tmp_path):
    admin = setup(monkeypatch, tmp_path)
    _, member = create_user(admin, "alice")
    assert member.get("/api/users").status_code == 403
    assert member.get("/api/roles").status_code == 403
    assert member.get("/api/departments").status_code == 403
    assert member.post("/api/model-providers", json={}).status_code == 403
    assert member.get("/api/model-configs").status_code == 200
    assert member.get("/api/permissions").status_code == 403


def test_department_tree_and_scoped_meeting_access(monkeypatch, tmp_path):
    admin = setup(monkeypatch, tmp_path)
    root = admin.post("/api/departments", json={"name": "研发中心"}).json()
    child = admin.post("/api/departments", json={"name": "平台组", "parent_id": root["id"]}).json()
    sibling = admin.post("/api/departments", json={"name": "销售部"}).json()
    assert admin.put(f"/api/departments/{root['id']}", json={"name": "研发中心", "parent_id": child["id"]}).status_code == 409
    assert admin.delete(f"/api/departments/{root['id']}").status_code == 409

    role = admin.post("/api/roles", json={"name": "部门观察员", "permissions": ["meeting:read_department"]}).json()
    _, viewer = create_user(admin, "viewer", root["id"], [role["id"]])
    _, engineer = create_user(admin, "engineer", child["id"])
    _, seller = create_user(admin, "seller", sibling["id"])
    visible_id = upload(engineer, "研发例会")
    hidden_id = upload(seller, "销售例会")
    assert [item["id"] for item in viewer.get("/api/meetings").json()] == [visible_id]
    assert viewer.get(f"/api/meetings/{visible_id}").status_code == 200
    assert viewer.get(f"/api/meetings/{hidden_id}").status_code == 404
    assert viewer.delete(f"/api/meetings/{visible_id}").status_code == 403
    editor_role = admin.post("/api/roles", json={"name": "部门编辑", "permissions": ["meeting:read_department", "meeting:manage_department"]}).json()
    _, editor = create_user(admin, "editor", root["id"], [editor_role["id"]])
    assert editor.delete(f"/api/meetings/{hidden_id}").status_code == 404
    assert editor.delete(f"/api/meetings/{visible_id}").status_code == 204
    assert admin.delete(f"/api/departments/{child['id']}").status_code == 409


def test_permission_changes_take_effect_without_relogin(monkeypatch, tmp_path):
    admin = setup(monkeypatch, tmp_path)
    role = admin.post("/api/roles", json={"name": "审阅者", "permissions": ["meeting:read_own"]}).json()
    user, client = create_user(admin, "reviewer", role_ids=[role["id"]])
    assert client.get("/api/roles").status_code == 403
    assert admin.put(f"/api/roles/{role['id']}", json={"name": "审阅者", "permissions": ["meeting:read_own", "role:read"]}).status_code == 200
    assert client.get("/api/roles").status_code == 200
    assert admin.put(f"/api/users/{user['id']}", json={"display_name": "reviewer", "role_ids": ["member"], "is_active": False}).status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_last_admin_and_system_role_are_protected(monkeypatch, tmp_path):
    admin = setup(monkeypatch, tmp_path)
    current = admin.get("/api/auth/me").json()
    assert admin.put(f"/api/users/{current['id']}", json={
        "display_name": "系统管理员", "role_ids": ["member"], "is_active": True,
    }).status_code == 409
    assert admin.delete(f"/api/users/{current['id']}").status_code == 409
    assert admin.delete("/api/roles/system-admin").status_code == 409
    assert admin.put("/api/roles/member", json={"name": "成员", "permissions": []}).status_code == 409


def test_password_reset_revokes_session_and_role_assignment_is_guarded(monkeypatch, tmp_path):
    admin = setup(monkeypatch, tmp_path)
    manager_role = admin.post("/api/roles", json={"name": "账号管理员", "permissions": ["user:read", "user:manage"]}).json()
    _, manager = create_user(admin, "manager", role_ids=[manager_role["id"]])
    assert manager.post("/api/users", json={
        "username": "newadmin", "display_name": "newadmin", "password": "new-password", "role_ids": ["system-admin"],
    }).status_code == 403
    ordinary = manager.post("/api/users", json={
        "username": "ordinary", "display_name": "ordinary", "password": "new-password", "role_ids": ["member"],
    })
    assert ordinary.status_code == 201
    ordinary_id = ordinary.json()["id"]
    session = TestClient(app)
    assert session.post("/api/auth/login", json={"username": "ordinary", "password": "new-password"}).status_code == 200
    reset = manager.put(f"/api/users/{ordinary_id}", json={
        "display_name": "ordinary", "role_ids": ["member"], "is_active": True, "password": "changed-password",
    })
    assert reset.status_code == 200
    assert session.get("/api/auth/me").status_code == 401
    assert session.post("/api/auth/login", json={"username": "ordinary", "password": "changed-password"}).status_code == 200
    assert manager.delete(f"/api/users/{ordinary_id}").status_code == 204


def test_role_permission_catalog_rejects_unknown_keys(monkeypatch, tmp_path):
    admin = setup(monkeypatch, tmp_path)
    response = admin.post("/api/roles", json={"name": "未知权限", "permissions": ["root:everything"]})
    assert response.status_code == 409
    assert admin.get("/api/permissions").status_code == 200


def test_existing_login_database_migrates_to_admin_role(monkeypatch, tmp_path):
    database = tmp_path / "legacy.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE users (id TEXT PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT, display_name TEXT)")
        connection.execute("INSERT INTO users VALUES (?, ?, ?, ?)",
                           ("legacy-admin", "admin", AuthStore._hash_password("admin-password"), "旧管理员"))
    monkeypatch.setattr(settings.app, "admin_username", "admin")
    monkeypatch.setattr(settings.app, "admin_password", "admin-password")
    auth_store = AuthStore(database)
    auth_store.bootstrap_admin()
    user = auth_store.authenticate("admin", "admin-password")
    assert user is not None
    assert user["role_ids"] == ["system-admin"]
    assert "department:manage" in user["permissions"]
