from backend.app.model_registry import ModelRegistry
from backend.app.models import ModelConfigInput, ProviderInput


def provider_input(name="OpenAI", api_key="sk-secret-value"):
    return ProviderInput(
        name=name,
        protocol="openai",
        base_url="https://api.openai.com/v1/",
        api_key=api_key,
    )


def test_provider_secret_is_masked_and_preserved_on_empty_update(tmp_path):
    registry = ModelRegistry(tmp_path / "registry.db")
    created = registry.save_provider("provider-1", provider_input())

    assert created.api_key_configured is True
    assert created.api_key_masked == "sk-••••alue"
    assert created.base_url == "https://api.openai.com/v1"

    updated = registry.save_provider("provider-1", provider_input(name="OpenAI Updated", api_key=""))
    credentials = registry.get_provider_credentials("provider-1")
    assert updated.name == "OpenAI Updated"
    assert credentials and credentials[1] == "sk-secret-value"


def test_only_one_default_model_per_type(tmp_path):
    registry = ModelRegistry(tmp_path / "registry.db")
    registry.save_provider("provider-1", provider_input())
    first = ModelConfigInput(
        provider_id="provider-1", name="问答模型 A", model_id="gpt-a", model_type="rag", is_default=True
    )
    second = ModelConfigInput(
        provider_id="provider-1", name="问答模型 B", model_id="gpt-b", model_type="rag", is_default=True
    )

    registry.save_model("model-a", first)
    registry.save_model("model-b", second)

    models = {model.id: model for model in registry.list_models()}
    assert models["model-a"].is_default is False
    assert models["model-b"].is_default is True


def test_deleting_provider_cascades_its_models(tmp_path):
    registry = ModelRegistry(tmp_path / "registry.db")
    registry.save_provider("provider-1", provider_input())
    registry.save_model(
        "model-1",
        ModelConfigInput(
            provider_id="provider-1", name="转写模型", model_id="whisper-1", model_type="asr"
        ),
    )

    assert registry.delete_provider("provider-1") is True
    assert registry.list_models() == []
