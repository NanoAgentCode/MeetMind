from backend.app.config import Settings


def test_settings_are_grouped_and_keep_existing_environment_names(monkeypatch):
    monkeypatch.setenv("MAX_UPLOAD_MB", "512")
    monkeypatch.setenv("ASR_BACKEND", "openai")
    monkeypatch.setenv("ASR_MODEL", "whisper-large")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("LLM_MODEL", "qwen3:8b")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")
    monkeypatch.setenv("RUSTFS_ENDPOINT", "http://rustfs:9000")
    monkeypatch.setenv("RUSTFS_BUCKET", "meeting-files")

    config = Settings()

    assert config.app.max_upload_mb == 512
    assert config.asr.backend == "openai"
    assert config.asr.model == "whisper-large"
    assert config.llm.provider == "ollama"
    assert config.llm.model == "qwen3:8b"
    assert config.ollama.base_url == "http://ollama:11434"
    assert config.rustfs.endpoint == "http://rustfs:9000"
    assert config.rustfs.bucket == "meeting-files"
