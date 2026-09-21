from backend.app.main import app


def test_split_routes_keep_original_paths_and_methods():
    expected = {
        ("/api/auth/login", "POST"),
        ("/api/auth/me", "GET"),
        ("/api/notifications", "GET"),
        ("/api/users", "GET"),
        ("/api/users", "POST"),
        ("/api/roles", "GET"),
        ("/api/roles", "POST"),
        ("/api/departments", "GET"),
        ("/api/departments", "POST"),
        ("/api/model-providers", "GET"),
        ("/api/model-providers", "POST"),
        ("/api/model-providers/{provider_id}/models", "GET"),
        ("/api/model-configs", "GET"),
        ("/api/model-configs", "POST"),
        ("/api/meetings", "POST"),
        ("/api/meetings", "GET"),
    }
    paths = app.openapi()["paths"]
    for path, method in expected:
        assert method.lower() in paths[path]
