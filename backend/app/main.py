import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

import httpx
from fastapi import FastAPI, File, Form, HTTPException, Request, Response as FastAPIResponse, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from .config import settings
from .auth import ADMIN_ROLE_ID, MEMBER_ROLE_ID, PERMISSIONS, auth_store
from .exporter import docx_bytes, markdown
from .model_registry import model_registry
from .models import ChatRequest, ChatResponse, Meeting, MeetingAnswer, MeetingQuestion, Minutes, ModelConfig, ModelConfigInput, Provider, ProviderInput
from pydantic import BaseModel, Field
from .services import answer_chat, answer_meeting_question, create_minutes, transcribe_audio
from .store import store

_running_transcriptions: set[str] = set()
_transcription_slots = asyncio.Semaphore(1)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    auth_store.bootstrap_admin()
    for pending in store.pending_transcriptions():
        schedule_transcription(pending.id)
    yield


app = FastAPI(title="会智录 API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_SUFFIXES = {".mp3", ".wav", ".m4a", ".webm", ".mp4", ".mpeg", ".ogg"}


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


@app.middleware("http")
async def require_login(request: Request, call_next):
    if request.method == "OPTIONS" or not request.url.path.startswith("/api/") or request.url.path in {"/api/health", "/api/auth/login"}:
        return await call_next(request)
    user = auth_store.get_user(request.cookies.get("meetmind_session"))
    if not user:
        return Response(status_code=401, content='{"detail":"请先登录"}', media_type="application/json")
    request.state.user = user
    required = required_route_permissions(request.url.path, request.method)
    if required and not any(has_permission(user, permission) for permission in required):
        return Response(status_code=403, content='{"detail":"权限不足"}', media_type="application/json")
    return await call_next(request)


@app.post("/api/auth/login")
def login(data: LoginInput, response: FastAPIResponse):
    auth_store.bootstrap_admin()
    if not auth_store.has_users():
        raise HTTPException(503, "请先配置 ADMIN_USERNAME 和 ADMIN_PASSWORD")
    user = auth_store.authenticate(data.username, data.password)
    if not user:
        raise HTTPException(401, "账号或密码错误")
    token = auth_store.create_session(user["id"])
    response.set_cookie("meetmind_session", token, max_age=7 * 86400, httponly=True, samesite="lax", secure=settings.app.cookie_secure)
    return user


@app.post("/api/auth/logout", status_code=204)
def logout(request: Request, response: FastAPIResponse):
    auth_store.delete_session(request.cookies.get("meetmind_session"))
    response.delete_cookie("meetmind_session")


@app.get("/api/auth/me")
def current_user(request: Request):
    return request.state.user


@app.get("/api/notifications")
def list_notifications(request: Request):
    return store.list_notifications(request.state.user["id"])


@app.post("/api/notifications/{notification_id}/read", status_code=204)
def mark_notification_read(notification_id: str, request: Request):
    if not store.mark_notification_read(notification_id, request.state.user["id"]):
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


@app.get("/api/permissions")
def list_permissions(request: Request):
    require_permission(request.state.user, "role:read", "role:manage")
    return [{"key": key, "label": label} for key, label in PERMISSIONS.items()]


@app.get("/api/users")
def list_users():
    return auth_store.list_users()


@app.post("/api/users", status_code=201)
def create_user(data: UserCreateInput, request: Request):
    _check_role_assignment(request.state.user, data.role_ids)
    try:
        return auth_store.create_user(data.username, data.display_name, data.password, data.department_id, data.role_ids)
    except (ValueError, KeyError) as exc:
        _management_error(exc)


@app.put("/api/users/{user_id}")
def update_user(user_id: str, data: UserUpdateInput, request: Request):
    target = auth_store.get_user_by_id(user_id)
    _protect_admin_target(request.state.user, target)
    if target and set(data.role_ids) != set(target["role_ids"]):
        _check_role_assignment(request.state.user, data.role_ids)
        require_permission(request.state.user, "role:manage")
    try:
        return auth_store.update_user(user_id, data.display_name, data.department_id, data.is_active, data.role_ids, data.password)
    except (ValueError, KeyError) as exc:
        _management_error(exc)


@app.delete("/api/users/{user_id}", status_code=204)
def delete_user(user_id: str, request: Request):
    _protect_admin_target(request.state.user, auth_store.get_user_by_id(user_id))
    try:
        auth_store.delete_user(user_id, request.state.user["id"])
    except (ValueError, KeyError) as exc:
        _management_error(exc)


@app.get("/api/roles")
def list_roles():
    return auth_store.list_roles()


@app.post("/api/roles", status_code=201)
def create_role(data: RoleInput):
    try:
        return auth_store.save_role(None, data.name, data.description, data.permissions)
    except (ValueError, KeyError) as exc:
        _management_error(exc)


@app.put("/api/roles/{role_id}")
def update_role(role_id: str, data: RoleInput):
    try:
        return auth_store.save_role(role_id, data.name, data.description, data.permissions)
    except (ValueError, KeyError) as exc:
        _management_error(exc)


@app.delete("/api/roles/{role_id}", status_code=204)
def delete_role(role_id: str):
    try:
        auth_store.delete_role(role_id)
    except (ValueError, KeyError) as exc:
        _management_error(exc)


@app.get("/api/departments")
def list_departments():
    return auth_store.list_departments()


@app.post("/api/departments", status_code=201)
def create_department(data: DepartmentInput):
    try:
        return auth_store.save_department(None, data.name, data.parent_id, data.sort_order)
    except (ValueError, KeyError) as exc:
        _management_error(exc)


@app.put("/api/departments/{department_id}")
def update_department(department_id: str, data: DepartmentInput):
    try:
        return auth_store.save_department(department_id, data.name, data.parent_id, data.sort_order)
    except (ValueError, KeyError) as exc:
        _management_error(exc)


@app.delete("/api/departments/{department_id}", status_code=204)
def delete_department(department_id: str):
    try:
        auth_store.delete_department(department_id)
    except (ValueError, KeyError) as exc:
        _management_error(exc)


def can_access_meeting(user: dict, meeting: Meeting, manage: bool = False) -> bool:
    if has_permission(user, "meeting:manage_all") or (not manage and has_permission(user, "meeting:read_all")):
        return True
    own_permission = "meeting:manage_own" if manage else "meeting:read_own"
    department_permission = "meeting:manage_department" if manage else "meeting:read_department"
    if meeting.owner_id == user["id"] and (has_permission(user, own_permission) or
                                             (not manage and has_permission(user, "meeting:manage_own"))):
        return True
    department_id = user.get("department_id")
    if department_id and (has_permission(user, department_permission) or
                          (not manage and has_permission(user, "meeting:manage_department"))):
        owner = auth_store.get_user_by_id(meeting.owner_id) if meeting.owner_id else None
        if owner and owner["department_id"] in auth_store.descendant_department_ids(department_id):
            return True
    return False


def require_meeting(meeting_id: str, user: dict, manage: bool = False) -> Meeting:
    meeting = store.get(meeting_id)
    if not meeting or not can_access_meeting(user, meeting, manage):
        raise HTTPException(404, "会议不存在")
    return meeting


async def run_transcription(meeting_id: str):
    meeting = store.get(meeting_id)
    if not meeting or meeting.status not in {"queued", "transcribing"}:
        _running_transcriptions.discard(meeting_id)
        return
    meeting.status = "transcribing"
    store.save(meeting)
    temporary_path: Path | None = None
    try:
        audio = await asyncio.to_thread(store.get_audio, meeting)
        with NamedTemporaryFile(suffix=Path(meeting.filename).suffix, delete=False) as temporary:
            temporary.write(audio)
            temporary_path = Path(temporary.name)
        transcript = await transcribe_audio(temporary_path)
        current = store.get(meeting_id)
        if current and current.status == "transcribing":
            current.transcript = transcript
            current.status = "transcribed"
            store.save(current)
            if current.owner_id:
                store.notify(current.owner_id, current.id, "转写完成", f"{current.title} 已完成语音转写")
    except Exception:
        current = store.get(meeting_id)
        if current and current.status == "transcribing":
            current.status = "transcription_failed"
            store.save(current)
            if current.owner_id:
                store.notify(current.owner_id, current.id, "转写失败", f"{current.title} 转写失败，请打开会议重试")
    finally:
        if temporary_path:
            temporary_path.unlink(missing_ok=True)
        _running_transcriptions.discard(meeting_id)


async def _queued_transcription(meeting_id: str):
    async with _transcription_slots:
        await run_transcription(meeting_id)


def schedule_transcription(meeting_id: str):
    if meeting_id not in _running_transcriptions:
        _running_transcriptions.add(meeting_id)
        asyncio.create_task(_queued_transcription(meeting_id))


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "asr_backend": settings.asr.backend,
        "llm_provider": settings.llm.provider,
        "llm_model": settings.llm.model,
    }


@app.get("/api/model-providers", response_model=list[Provider])
def list_model_providers():
    return model_registry.list_providers()


@app.post("/api/model-providers", response_model=Provider, status_code=201)
def create_model_provider(data: ProviderInput):
    return model_registry.save_provider(uuid4().hex, data)


@app.put("/api/model-providers/{provider_id}", response_model=Provider)
def update_model_provider(provider_id: str, data: ProviderInput):
    if not model_registry.get_provider(provider_id):
        raise HTTPException(404, "供应商不存在")
    return model_registry.save_provider(provider_id, data)


@app.delete("/api/model-providers/{provider_id}", status_code=204)
def delete_model_provider(provider_id: str):
    if not model_registry.delete_provider(provider_id):
        raise HTTPException(404, "供应商不存在")


async def _fetch_provider_models(provider_id: str) -> list[str]:
    credentials = model_registry.get_provider_credentials(provider_id)
    if not credentials:
        raise HTTPException(404, "供应商不存在")
    provider, api_key = credentials
    if not provider.enabled:
        raise HTTPException(409, "请先启用供应商")
    if provider.protocol in {"openai", "openai_compatible"}:
        url = f"{provider.base_url.rstrip('/')}/models"
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    elif provider.protocol == "anthropic":
        base_url = provider.base_url.rstrip("/")
        url = f"{base_url}/models" if base_url.endswith("/v1") else f"{base_url}/v1/models"
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
    else:
        url = f"{provider.base_url.rstrip('/')}/api/tags"
        headers = {}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(url, headers=headers)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"获取模型列表失败：{exc}") from exc
    payload = response.json()
    if provider.protocol == "ollama":
        items = payload.get("models", [])
        model_ids = [item.get("name") or item.get("model") for item in items]
    else:
        model_ids = [item.get("id") for item in payload.get("data", [])]
    return sorted({model_id for model_id in model_ids if isinstance(model_id, str) and model_id.strip()})


@app.get("/api/model-providers/{provider_id}/models")
async def list_provider_models(provider_id: str):
    return {"models": await _fetch_provider_models(provider_id)}


@app.post("/api/model-providers/{provider_id}/test")
async def test_model_provider(provider_id: str):
    await _fetch_provider_models(provider_id)
    return {"status": "ok", "message": "连接成功"}


@app.get("/api/model-configs", response_model=list[ModelConfig])
def list_model_configs():
    return model_registry.list_models()


@app.post("/api/model-configs", response_model=ModelConfig, status_code=201)
def create_model_config(data: ModelConfigInput):
    try:
        return model_registry.save_model(uuid4().hex, data)
    except KeyError as exc:
        raise HTTPException(400, str(exc.args[0])) from exc


@app.put("/api/model-configs/{model_config_id}", response_model=ModelConfig)
def update_model_config(model_config_id: str, data: ModelConfigInput):
    if not model_registry.get_model(model_config_id):
        raise HTTPException(404, "模型配置不存在")
    try:
        return model_registry.save_model(model_config_id, data)
    except KeyError as exc:
        raise HTTPException(400, str(exc.args[0])) from exc


@app.delete("/api/model-configs/{model_config_id}", status_code=204)
def delete_model_config(model_config_id: str):
    if not model_registry.delete_model(model_config_id):
        raise HTTPException(404, "模型配置不存在")


@app.post("/api/meetings", response_model=Meeting, status_code=201)
async def upload_meeting(request: Request, file: UploadFile = File(...), title: str = Form(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(400, "仅支持 MP3、WAV、M4A、WEBM、MP4、MPEG 或 OGG 文件")
    content = await file.read(settings.app.max_upload_mb * 1024 * 1024 + 1)
    if len(content) > settings.app.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"文件不能超过 {settings.app.max_upload_mb} MB")
    if not content:
        raise HTTPException(400, "录音文件不能为空")
    meeting_id = uuid4().hex
    meeting = Meeting(
        id=meeting_id,
        filename=file.filename or f"recording{suffix}",
        title=title.strip() or "未命名会议",
        created_at=datetime.now(timezone.utc),
        status="uploaded",
        owner_id=request.state.user["id"],
    )
    try:
        store.save_audio(meeting, content, file.content_type or "application/octet-stream")
    except Exception as exc:
        raise HTTPException(503, f"RustFS 存储不可用：{exc}") from exc
    if len(content) > settings.app.background_audio_mb * 1024 * 1024:
        meeting.status = "queued"
    saved = store.save(meeting)
    if meeting.status == "queued":
        schedule_transcription(meeting.id)
    return saved


@app.get("/api/meetings", response_model=list[Meeting])
def list_meetings(request: Request):
    return [meeting for meeting in store.list() if can_access_meeting(request.state.user, meeting)]


@app.get("/api/meetings/{meeting_id}", response_model=Meeting)
def get_meeting(meeting_id: str, request: Request):
    return require_meeting(meeting_id, request.state.user)


@app.delete("/api/meetings/{meeting_id}", status_code=204)
def delete_meeting(meeting_id: str, request: Request):
    meeting = require_meeting(meeting_id, request.state.user, manage=True)
    store.delete(meeting)


@app.post("/api/meetings/{meeting_id}/transcribe", response_model=Meeting)
async def transcribe(meeting_id: str, request: Request):
    meeting = require_meeting(meeting_id, request.state.user, manage=True)
    if meeting.status not in {"uploaded", "transcription_failed"}:
        raise HTTPException(409, "当前会议无法开始转写")
    temporary_path: Path | None = None
    try:
        audio = store.get_audio(meeting)
        with NamedTemporaryFile(suffix=Path(meeting.filename).suffix, delete=False) as temporary:
            temporary.write(audio)
            temporary_path = Path(temporary.name)
        meeting.transcript = await transcribe_audio(temporary_path)
    except (ValueError, httpx.HTTPError) as exc:
        raise HTTPException(502, f"转写服务失败：{exc}") from exc
    finally:
        if temporary_path:
            temporary_path.unlink(missing_ok=True)
    meeting.status = "transcribed"
    return store.save(meeting)


@app.post("/api/meetings/{meeting_id}/questions", response_model=MeetingAnswer)
async def ask_meeting(meeting_id: str, data: MeetingQuestion, request: Request):
    meeting = require_meeting(meeting_id, request.state.user)
    try:
        return MeetingAnswer(answer=await answer_meeting_question(meeting, data.question, model_registry))
    except (ValueError, httpx.HTTPError) as exc:
        raise HTTPException(502, f"会议问答失败：{exc}") from exc


@app.post("/api/chat", response_model=ChatResponse)
async def chat(data: ChatRequest, request: Request):
    meeting = require_meeting(data.meeting_id, request.state.user) if data.meeting_id else None
    try:
        answer = await answer_chat(data.question, data.history, meeting, model_registry)
        return ChatResponse(answer=answer, meeting_id=data.meeting_id)
    except (ValueError, httpx.HTTPError) as exc:
        raise HTTPException(502, f"对话失败：{exc}") from exc


@app.post("/api/meetings/{meeting_id}/minutes/generate", response_model=Meeting)
async def generate(meeting_id: str, request: Request):
    meeting = require_meeting(meeting_id, request.state.user, manage=True)
    if not meeting.transcript:
        raise HTTPException(409, "请先完成语音转写")
    try:
        meeting.minutes = await create_minutes(meeting.title, meeting.transcript)
    except Exception as exc:
        raise HTTPException(502, f"纪要生成失败：{exc}") from exc
    meeting.status = "generated"
    return store.save(meeting)


@app.put("/api/meetings/{meeting_id}/minutes", response_model=Meeting)
def update_minutes(meeting_id: str, minutes: Minutes, request: Request):
    meeting = require_meeting(meeting_id, request.state.user, manage=True)
    if meeting.minutes is None:
        raise HTTPException(409, "请先生成会议纪要")
    meeting.minutes = minutes
    meeting.status = "edited"
    return store.save(meeting)


@app.get("/api/meetings/{meeting_id}/export")
def export_minutes(meeting_id: str, request: Request, format: str = "docx"):
    meeting = require_meeting(meeting_id, request.state.user)
    if meeting.status != "edited" or meeting.minutes is None:
        raise HTTPException(409, "请先保存人工定稿，再导出")
    safe_name = f"meeting-{meeting.id[:8]}"
    if format == "md":
        content = markdown(meeting).encode("utf-8")
        store.save_export(meeting, "md", content, "text/markdown; charset=utf-8")
        return Response(
            content,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{safe_name}.md"'},
        )
    if format == "docx":
        content = docx_bytes(meeting)
        store.save_export(
            meeting,
            "docx",
            content,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        return Response(
            content,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{safe_name}.docx"'},
        )
    raise HTTPException(400, "导出格式仅支持 docx 或 md")
