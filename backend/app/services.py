import re
import json
from pathlib import Path
from typing import TypedDict

import httpx
from langgraph.graph import END, START, StateGraph

from .config import settings
from .model_registry import ModelRegistry, model_registry
from .models import ChatTurn, Meeting, Minutes
from .providers import build_chat_model, build_managed_chat_model


class WorkflowState(TypedDict, total=False):
    title: str
    transcript: str
    minutes: dict


async def transcribe_audio(path: Path, registry: ModelRegistry | None = None) -> str:
    registry = registry or model_registry
    managed = registry.get_default_model("asr")
    if managed:
        model, provider, api_key = managed
        if provider.protocol not in {"openai", "openai_compatible"}:
            raise ValueError("语音转文字模型目前仅支持 OpenAI 或 OpenAI Compatible 协议")
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        async with httpx.AsyncClient(timeout=180) as client:
            with path.open("rb") as stream:
                response = await client.post(
                    f"{provider.base_url.rstrip('/')}/audio/transcriptions",
                    headers=headers,
                    data={"model": model.model_id, "response_format": "json"},
                    files={"file": (path.name, stream, "application/octet-stream")},
                )
        response.raise_for_status()
        return response.json()["text"].strip()
    if settings.asr.backend == "demo":
        return (
            "主持人：本次会议主要讨论产品第一阶段上线计划。\n"
            "张明：上传录音和语音转写功能已经进入联调，本周五前完成异常场景测试。\n"
            "李华：会议纪要需要支持人工修改，并导出 Word 文档。\n"
            "主持人：决定第一阶段先交付上传、转写、生成、修改和导出闭环。\n"
            "王芳：我负责整理验收清单，下周一组织演示。"
        )
    if settings.asr.backend != "openai":
        raise ValueError(f"不支持的 ASR_BACKEND：{settings.asr.backend}")
    if not settings.openai.api_key:
        raise ValueError("使用 openai 转写前请配置 OPENAI_API_KEY")

    headers = {"Authorization": f"Bearer {settings.openai.api_key}"}
    async with httpx.AsyncClient(timeout=180) as client:
        with path.open("rb") as stream:
            response = await client.post(
                f"{settings.openai.base_url.rstrip('/')}/audio/transcriptions",
                headers=headers,
                data={"model": settings.asr.model, "response_format": "json"},
                files={"file": (path.name, stream, "application/octet-stream")},
            )
    response.raise_for_status()
    return response.json()["text"].strip()


def _sentences(text: str) -> list[str]:
    return [item.strip() for item in re.split(r"[。！？\n]+", text) if len(item.strip()) > 5]


def _fallback_minutes(title: str, transcript: str) -> Minutes:
    sentences = _sentences(transcript)
    decisions = [s for s in sentences if any(word in s for word in ("决定", "确定", "达成", "先交付"))]
    actions = [s for s in sentences if any(word in s for word in ("负责", "完成", "本周", "下周", "截止"))]
    points = [s for s in sentences if s not in decisions and s not in actions][:5]
    return Minutes(
        title=f"{title}会议纪要",
        summary="；".join(sentences[:3]) + ("。" if sentences else ""),
        key_points=points or sentences[:3],
        decisions=decisions or ["暂无明确决策，建议人工补充"],
        action_items=actions or ["暂无明确行动项，建议人工补充负责人和截止时间"],
    )


async def generate_node(state: WorkflowState) -> WorkflowState:
    managed = model_registry.get_default_model("llm")
    model = build_managed_chat_model(*managed) if managed else build_chat_model()
    if model is None:
        result = _fallback_minutes(state["title"], state["transcript"])
    else:
        response = await model.ainvoke(
            "你是一名严谨的中文会议秘书。基于转写生成纪要，不得编造；行动项尽量包含负责人和时间。\n"
            "只返回 JSON，不要使用 Markdown 代码块。JSON 必须包含以下字段："
            "title 字符串、summary 字符串、key_points 字符串数组、decisions 字符串数组、"
            "action_items 字符串数组。\n"
            f"会议名称：{state['title']}\n转写：\n{state['transcript']}"
        )
        content = response.content
        if not isinstance(content, str):
            raise ValueError("模型未返回文本格式的 JSON")
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.IGNORECASE)
        result = Minutes.model_validate(json.loads(cleaned))
    return {"minutes": result.model_dump()}


builder = StateGraph(WorkflowState)
builder.add_node("generate_minutes", generate_node)
builder.add_edge(START, "generate_minutes")
builder.add_edge("generate_minutes", END)
minutes_graph = builder.compile()


async def create_minutes(title: str, transcript: str) -> Minutes:
    result = await minutes_graph.ainvoke({"title": title, "transcript": transcript})
    return Minutes.model_validate(result["minutes"])


async def answer_meeting_question(
    meeting: Meeting, question: str, registry: ModelRegistry = model_registry
) -> str:
    return await answer_chat(question, [], meeting, registry)


async def answer_chat(
    question: str,
    history: list[ChatTurn],
    meeting: Meeting | None = None,
    registry: ModelRegistry = model_registry,
) -> str:
    managed = (
        registry.get_default_model("rag") or registry.get_default_model("llm")
        if meeting else registry.get_default_model("llm")
    )
    model = build_managed_chat_model(*managed) if managed else build_chat_model()
    if model is None:
        mode = "会议 RAG 或 LLM" if meeting else "LLM"
        return f"当前使用演示模型，请先在模型服务中配置并启用默认的{mode}模型。"
    history_text = "\n".join(
        f"{'用户' if turn.role == 'user' else '助手'}：{turn.content}" for turn in history[-10:]
    )
    if meeting:
        context = meeting.transcript
        if meeting.minutes:
            context += f"\n结构化纪要：{meeting.minutes.model_dump_json()}"
        if not context.strip():
            raise ValueError("该会议尚无可用于问答的转写或纪要")
        instruction = (
            "你是会议内容问答助手。只能根据给定会议内容回答；若内容中没有答案，明确回答“会议内容中未提及”，"
            "不得补充外部知识或编造。\n"
            f"会议名称：{meeting.title}\n会议内容：\n{context}"
        )
    else:
        instruction = "你是专业、简洁的中文 AI 助手，请直接回答用户问题。"
    prompt = f"{instruction}\n"
    if history_text:
        prompt += f"\n最近对话：\n{history_text}\n"
    response = await model.ainvoke(f"{prompt}\n用户问题：{question}")
    content = response.content
    if isinstance(content, str):
        return content.strip()
    raise ValueError("模型未返回文本答案")
