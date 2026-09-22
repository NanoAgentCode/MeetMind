"""Conversation endpoints and context compaction orchestration."""

from collections.abc import Callable

import httpx
from fastapi import APIRouter, HTTPException, Request

from .chat_context import plan_compaction, prompt_tokens
from .chat_store import ChatStore
from .config import settings
from .model_registry import ModelRegistry
from .models import ChatRequest, ChatResponse, ChatTurn, Meeting
from .provider_context import resolve_context_window
from .chat_service import answer_chat, chat_instruction, summarize_chat_history
from .store import MeetingStore


def create_chat_router(
    get_store: Callable[[], MeetingStore],
    get_registry: Callable[[], ModelRegistry],
    require_meeting: Callable[[str, dict], Meeting],
) -> APIRouter:
    router = APIRouter()

    @router.post("/api/chat", response_model=ChatResponse)
    async def chat(data: ChatRequest, request: Request):
        chats = ChatStore(get_store().database_path)
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
        registry = get_registry()
        try:
            instruction = chat_instruction(meeting)
            context_window = await resolve_context_window(registry, meeting, settings.app.chat_context_window_tokens)
            while (count := plan_compaction(instruction, data.question, history, summary, context_window)):
                while count > 1 and prompt_tokens("请摘要以下对话", "", history[:count], summary) >= int(context_window * 0.8):
                    count -= 1
                if prompt_tokens("请摘要以下对话", "", history[:count], summary) >= int(context_window * 0.8):
                    raise HTTPException(413, "单条对话过长，无法在模型上下文窗口内摘要")
                summary = await summarize_chat_history(summary, history[:count], meeting, registry, context_window)
                summarized_count += count
                history = history[count:]
            if prompt_tokens(instruction, data.question, history, summary) >= int(context_window * 0.8):
                raise HTTPException(413, "问题或会议内容超过模型上下文窗口的 80%，请缩短输入")
            answer = (await answer_chat(data.question, history, meeting, registry, summary=summary)
                      if summary else await answer_chat(data.question, history, meeting, registry))
            messages = all_messages + [
                {"role": "user", "content": data.question}, {"role": "assistant", "content": answer}]
            conversation_id = chats.save(owner_id, meeting_id, data.question, messages, data.conversation_id,
                                         summary, summarized_count)
            return ChatResponse(answer=answer, meeting_id=meeting_id, conversation_id=conversation_id)
        except (ValueError, httpx.HTTPError) as exc:
            raise HTTPException(502, f"对话失败：{exc}") from exc

    @router.get("/api/chat/conversations")
    def list_chat_conversations(request: Request):
        return ChatStore(get_store().database_path).list(request.state.user["id"])

    @router.get("/api/chat/conversations/{conversation_id}")
    def get_chat_conversation(conversation_id: str, request: Request):
        conversation = ChatStore(get_store().database_path).get(conversation_id, request.state.user["id"])
        if not conversation:
            raise HTTPException(404, "对话不存在")
        return conversation

    return router
