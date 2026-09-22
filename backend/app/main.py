import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

import httpx
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from .access import has_permission, required_route_permissions
from .access_routes import create_access_router
from .auth import auth_store
from .chat_context import plan_compaction, prompt_tokens
from .chat_store import ChatStore
from .config import settings
from .exporter import docx_bytes, markdown
from .model_registry import model_registry
from .model_routes import create_model_router
from .models import ChatRequest, ChatResponse, ChatTurn, Meeting, MeetingAnswer, MeetingQuestion, Minutes
from .provider_context import resolve_context_window
from .services import answer_chat, answer_meeting_question, chat_instruction, create_minutes, summarize_chat_history, transcribe_audio
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

app.include_router(create_access_router(lambda: auth_store, lambda: store))
app.include_router(create_model_router(lambda: model_registry, lambda: httpx.AsyncClient))


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
    chats = ChatStore(store.database_path)
    owner_id = request.state.user["id"]
    conversation = chats.get(data.conversation_id, owner_id) if data.conversation_id else None
    if data.conversation_id and not conversation:
        raise HTTPException(404, "对话不存在")
    meeting_id = conversation["meeting_id"] if conversation else data.meeting_id
    meeting = require_meeting(meeting_id, request.state.user) if meeting_id else None
    all_messages = conversation["messages"] if conversation else [turn.model_dump() for turn in data.history]
    summarized_count = conversation["summarized_count"] if conversation else 0
    summary = conversation["summary_text"] if conversation else ""
    history = [ChatTurn(**turn) for turn in all_messages[summarized_count:]]
    try:
        instruction = chat_instruction(meeting)
        context_window = await resolve_context_window(model_registry, meeting, settings.app.chat_context_window_tokens)
        while (count := plan_compaction(instruction, data.question, history, summary, context_window)):
            while count > 1 and prompt_tokens("请摘要以下对话", "", history[:count], summary) >= int(context_window * 0.8):
                count -= 1
            if prompt_tokens("请摘要以下对话", "", history[:count], summary) >= int(context_window * 0.8):
                raise HTTPException(413, "单条对话过长，无法在模型上下文窗口内摘要")
            summary = await summarize_chat_history(summary, history[:count], meeting, model_registry, context_window)
            summarized_count += count
            history = history[count:]
        if prompt_tokens(instruction, data.question, history, summary) >= int(context_window * 0.8):
            raise HTTPException(413, "问题或会议内容超过模型上下文窗口的 80%，请缩短输入")
        answer = (await answer_chat(data.question, history, meeting, model_registry, summary=summary)
                  if summary else await answer_chat(data.question, history, meeting, model_registry))
        messages = all_messages + [
            {"role": "user", "content": data.question}, {"role": "assistant", "content": answer}]
        conversation_id = chats.save(owner_id, meeting_id, data.question, messages, data.conversation_id,
                                     summary, summarized_count)
        return ChatResponse(answer=answer, meeting_id=meeting_id, conversation_id=conversation_id)
    except (ValueError, httpx.HTTPError) as exc:
        raise HTTPException(502, f"对话失败：{exc}") from exc


@app.get("/api/chat/conversations")
def list_chat_conversations(request: Request):
    return ChatStore(store.database_path).list(request.state.user["id"])


@app.get("/api/chat/conversations/{conversation_id}")
def get_chat_conversation(conversation_id: str, request: Request):
    conversation = ChatStore(store.database_path).get(conversation_id, request.state.user["id"])
    if not conversation:
        raise HTTPException(404, "对话不存在")
    return conversation


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
