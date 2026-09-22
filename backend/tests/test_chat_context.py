from backend.app.chat_context import estimate_tokens, plan_compaction
from backend.app.models import ChatTurn
from backend.app import chat_service
import asyncio


def test_compaction_starts_at_eighty_percent_and_keeps_recent_turns():
    history = [ChatTurn(role="user" if index % 2 == 0 else "assistant", content="甲" * 24)
               for index in range(8)]
    budget = estimate_tokens("规则" + "新问题" + "\n".join(turn.content for turn in history))
    assert plan_compaction("规则", "新问题", history, "", budget * 2) == 0
    assert plan_compaction("规则", "新问题", history, "", budget) == 4


def test_summary_counts_toward_window_budget():
    history = [ChatTurn(role="user", content="甲" * 30), ChatTurn(role="assistant", content="乙" * 30)]
    assert plan_compaction("规则", "问题", history, "旧摘要" * 50, 160) == 2


def test_answer_prompt_contains_summary_and_only_selected_recent_turns(monkeypatch):
    class Model:
        async def ainvoke(self, prompt):
            assert "较早对话摘要：\n早期结论" in prompt
            assert "助手：最近答复" in prompt
            assert "很久以前的内容" not in prompt
            return type("Response", (), {"content": "完成"})()

    class Registry:
        def get_default_model(self, _type):
            return (object(), object(), "")

    monkeypatch.setattr(chat_service, "build_managed_chat_model", lambda *_args: Model())
    result = asyncio.run(chat_service.answer_chat("新问题", [ChatTurn(role="assistant", content="最近答复")],
                                             registry=Registry(), summary="早期结论"))
    assert result == "完成"
