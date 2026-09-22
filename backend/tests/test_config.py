from pathlib import Path
import asyncio

from backend.app.config import Settings
from backend.app import services


def test_settings_are_grouped_and_keep_existing_environment_names(monkeypatch):
    monkeypatch.setenv("MAX_UPLOAD_MB", "512")
    monkeypatch.setenv("APP_HOST", "0.0.0.0")
    monkeypatch.setenv("APP_PORT", "9002")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("ASR_BACKEND", "openai")
    monkeypatch.setenv("RUSTFS_ENDPOINT", "http://rustfs:9000")
    monkeypatch.setenv("RUSTFS_BUCKET", "meeting-files")
    monkeypatch.setenv("DATABASE_PATH", "work/test-meetings.db")

    config = Settings()

    assert config.app.max_upload_mb == 512
    assert config.app.host == "0.0.0.0"
    assert config.app.port == 9002
    assert not hasattr(config, "asr")
    assert not hasattr(config, "llm")
    assert config.rustfs.endpoint == "http://rustfs:9000"
    assert config.rustfs.bucket == "meeting-files"
    assert config.database.path == Path("work/test-meetings.db")


def test_legacy_model_environment_does_not_select_models(monkeypatch, tmp_path):
    monkeypatch.setenv("ASR_BACKEND", "openai")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "legacy-key")

    class Registry:
        def get_default_model(self, _model_type):
            return None

    recording = tmp_path / "sample.mp3"
    recording.write_bytes(b"audio")
    assert "本次会议" in asyncio.run(services.transcribe_audio(recording, Registry()))
    monkeypatch.setattr(services, "model_registry", Registry())
    result = asyncio.run(services.generate_node({"title": "测试", "transcript": "会议决定先交付录音转写功能。"}))
    assert result["minutes"]["title"] == "测试会议纪要"
