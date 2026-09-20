"""Executable entry point for the MeetMind backend service."""

import uvicorn

if __package__:
    from .app.config import settings
    from .app.main import app
else:
    from app.config import settings
    from app.main import app


def main() -> None:
    """Start the FastAPI application with the configured host and port."""
    uvicorn.run(app, host=settings.app.host, port=settings.app.port)


if __name__ == "__main__":
    main()
