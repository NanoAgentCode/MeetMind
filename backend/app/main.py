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
from .model_registry import model_registry
from .models import Meeting, MeetingAnswer, MeetingQuestion, Minutes, ModelConfig, ModelConfigInput, Provider, ProviderInput
from .services import answer_meeting_question, create_minutes, transcribe_audio
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


@app.post("/api/model-providers/{provider_id}/test")
async def test_model_provider(provider_id: str):
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
        url = f"{provider.base_url.rstrip('/')}/v1/models"
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
    else:
        url = f"{provider.base_url.rstrip('/')}/api/tags"
        headers = {}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(url, headers=headers)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"连接测试失败：{exc}") from exc
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
async def upload_meeting(file: UploadFile = File(...), title: str = Form(...)):
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
    )
    try:
        store.save_audio(meeting, content, file.content_type or "application/octet-stream")
    except Exception as exc:
        raise HTTPException(503, f"RustFS 存储不可用：{exc}") from exc
    return store.save(meeting)


@app.get("/api/meetings", response_model=list[Meeting])
def list_meetings():
    return store.list()


@app.get("/api/meetings/{meeting_id}", response_model=Meeting)
def get_meeting(meeting_id: str):
    return require_meeting(meeting_id)


@app.delete("/api/meetings/{meeting_id}", status_code=204)
def delete_meeting(meeting_id: str):
    meeting = require_meeting(meeting_id)
    store.delete(meeting)


@app.post("/api/meetings/{meeting_id}/transcribe", response_model=Meeting)
async def transcribe(meeting_id: str):
    meeting = require_meeting(meeting_id)
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
async def ask_meeting(meeting_id: str, data: MeetingQuestion):
    meeting = require_meeting(meeting_id)
    try:
        return MeetingAnswer(answer=await answer_meeting_question(meeting, data.question, model_registry))
    except (ValueError, httpx.HTTPError) as exc:
        raise HTTPException(502, f"会议问答失败：{exc}") from exc


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
