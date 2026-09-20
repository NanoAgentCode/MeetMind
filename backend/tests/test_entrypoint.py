from backend import main as entrypoint


def test_main_starts_uvicorn_with_app_settings(monkeypatch):
    captured = {}

    def fake_run(app, **kwargs):
        captured["app"] = app
        captured.update(kwargs)

    monkeypatch.setattr(entrypoint.uvicorn, "run", fake_run)
    monkeypatch.setattr(entrypoint.settings.app, "host", "0.0.0.0")
    monkeypatch.setattr(entrypoint.settings.app, "port", 9002)

    entrypoint.main()

    assert captured == {
        "app": entrypoint.app,
        "host": "0.0.0.0",
        "port": 9002,
    }
