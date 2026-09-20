from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from .config import settings
from .exporter import docx_bytes, markdown
from .models import Meeting, Minutes
from .services import create_minutes, transcribe_audio
from .store import store

app = FastAPI(title="会智录 API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_SUFFIXES = {".mp3", ".wav", ".m4a", ".webm", ".mp4", ".mpeg", ".ogg"}


def require_meeting(meeting_id: str) -> Meeting:
    meeting = store.get(meeting_id)
    if not meeting:
        raise HTTPException(404, "会议不存在")
    return meeting


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "asr_backend": settings.asr_backend,
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
    }


@app.post("/api/meetings", response_model=Meeting, status_code=201)
async def upload_meeting(file: UploadFile = File(...), title: str = Form(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(400, "仅支持 MP3、WAV、M4A、WEBM、MP4、MPEG 或 OGG 文件")
    content = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"文件不能超过 {settings.max_upload_mb} MB")
    if not content:
        raise HTTPException(400, "录音文件不能为空")
    meeting_id = uuid4().hex
    meeting = Meeting(
        id=meeting_id,
        filename=file.filename or f"recording{suffix}",
        title=title.strip() or "未命名会议",
        created_at=datetime.now(timezone.utc),
        status="uploaded",
    )
    try:
        store.save_audio(meeting, content, file.content_type or "application/octet-stream")
    except Exception as exc:
        raise HTTPException(503, f"RustFS 存储不可用：{exc}") from exc
    return store.save(meeting)


@app.get("/api/meetings/{meeting_id}", response_model=Meeting)
def get_meeting(meeting_id: str):
    return require_meeting(meeting_id)


@app.post("/api/meetings/{meeting_id}/transcribe", response_model=Meeting)
async def transcribe(meeting_id: str):
    meeting = require_meeting(meeting_id)
    try:
        audio = store.get_audio(meeting)
        with NamedTemporaryFile(suffix=Path(meeting.filename).suffix) as temporary:
            temporary.write(audio)
            temporary.flush()
            meeting.transcript = await transcribe_audio(Path(temporary.name))
    except (ValueError, httpx.HTTPError) as exc:
        raise HTTPException(502, f"转写服务失败：{exc}") from exc
    meeting.status = "transcribed"
    return store.save(meeting)


@app.post("/api/meetings/{meeting_id}/minutes/generate", response_model=Meeting)
async def generate(meeting_id: str):
    meeting = require_meeting(meeting_id)
    if not meeting.transcript:
        raise HTTPException(409, "请先完成语音转写")
    try:
        meeting.minutes = await create_minutes(meeting.title, meeting.transcript)
    except Exception as exc:
        raise HTTPException(502, f"纪要生成失败：{exc}") from exc
    meeting.status = "generated"
    return store.save(meeting)


@app.put("/api/meetings/{meeting_id}/minutes", response_model=Meeting)
def update_minutes(meeting_id: str, minutes: Minutes):
    meeting = require_meeting(meeting_id)
    if meeting.minutes is None:
        raise HTTPException(409, "请先生成会议纪要")
    meeting.minutes = minutes
    meeting.status = "edited"
    return store.save(meeting)


@app.get("/api/meetings/{meeting_id}/export")
def export_minutes(meeting_id: str, format: str = "docx"):
    meeting = require_meeting(meeting_id)
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
