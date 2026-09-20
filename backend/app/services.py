import re
from pathlib import Path
from typing import TypedDict

import httpx
from langgraph.graph import END, START, StateGraph

from .config import settings
from .models import Minutes


class WorkflowState(TypedDict, total=False):
    title: str
    transcript: str
    minutes: dict


async def transcribe_audio(path: Path) -> str:
    if settings.asr_backend == "demo":
        return (
            "主持人：本次会议主要讨论产品第一阶段上线计划。\n"
            "张明：上传录音和语音转写功能已经进入联调，本周五前完成异常场景测试。\n"
            "李华：会议纪要需要支持人工修改，并导出 Word 文档。\n"
            "主持人：决定第一阶段先交付上传、转写、生成、修改和导出闭环。\n"
            "王芳：我负责整理验收清单，下周一组织演示。"
        )
    if settings.asr_backend != "openai":
        raise ValueError(f"不支持的 ASR_BACKEND：{settings.asr_backend}")
    if not settings.openai_api_key:
        raise ValueError("使用 openai 转写前请配置 OPENAI_API_KEY")

    headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
    async with httpx.AsyncClient(timeout=180) as client:
        with path.open("rb") as stream:
            response = await client.post(
                f"{settings.openai_base_url.rstrip('/')}/audio/transcriptions",
                headers=headers,
                data={"model": settings.asr_model, "response_format": "json"},
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
    if settings.openai_api_key:
        from langchain_openai import ChatOpenAI

        model = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            temperature=0,
        ).with_structured_output(Minutes)
        result = await model.ainvoke(
            "你是一名严谨的中文会议秘书。基于转写生成纪要，不得编造；行动项尽量包含负责人和时间。\n"
            f"会议名称：{state['title']}\n转写：\n{state['transcript']}"
        )
    else:
        result = _fallback_minutes(state["title"], state["transcript"])
    return {"minutes": result.model_dump()}


builder = StateGraph(WorkflowState)
builder.add_node("generate_minutes", generate_node)
builder.add_edge(START, "generate_minutes")
builder.add_edge("generate_minutes", END)
minutes_graph = builder.compile()


async def create_minutes(title: str, transcript: str) -> Minutes:
    result = await minutes_graph.ainvoke({"title": title, "transcript": transcript})
    return Minutes.model_validate(result["minutes"])

