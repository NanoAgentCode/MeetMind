import asyncio

from backend.app import services


class EmptyModelRegistry:
    def get_default_model(self, _model_type):
        return (object(), object(), "")


class Response:
    content = """```json
    {
      "title": "项目周会纪要",
      "summary": "确认第一阶段范围。",
      "key_points": ["完成协议适配"],
      "decisions": ["支持四种模型协议"],
      "action_items": ["张明周五前完成联调"]
    }
    ```"""


class FakeModel:
    async def ainvoke(self, prompt):
        assert "只返回 JSON" in prompt
        return Response()


def test_generation_normalizes_provider_json(monkeypatch):
    monkeypatch.setattr(services, "model_registry", EmptyModelRegistry())
    monkeypatch.setattr(services, "build_managed_chat_model", lambda *_args: FakeModel())
    result = asyncio.run(
        services.generate_node({"title": "项目周会", "transcript": "会议确认第一阶段范围。"})
    )
    assert result["minutes"]["title"] == "项目周会纪要"
    assert result["minutes"]["action_items"] == ["张明周五前完成联调"]


def test_generation_rejects_non_json_response(monkeypatch):
    monkeypatch.setattr(services, "model_registry", EmptyModelRegistry())
    class InvalidModel:
        async def ainvoke(self, prompt):
            return type("Response", (), {"content": "这不是 JSON"})()

    monkeypatch.setattr(services, "build_managed_chat_model", lambda *_args: InvalidModel())
    try:
        asyncio.run(services.generate_node({"title": "项目周会", "transcript": "内容"}))
    except ValueError:
        pass
    else:
        raise AssertionError("invalid provider output must fail validation")
