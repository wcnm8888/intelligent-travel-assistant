"""Local command-line entry point for the FastAPI service."""

import uvicorn

from intelligent_travel_assistant.settings import get_settings


def run() -> None:
    """Run the local API with the validated host and port settings."""

    settings = get_settings()
    uvicorn.run(
        "intelligent_travel_assistant.app:app",
        host=str(settings.api_host),
        port=settings.api_port,
    )


if __name__ == "__main__":
    run()
