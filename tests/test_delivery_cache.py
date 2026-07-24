import asyncio
from unittest.mock import AsyncMock

from src.config.settings import Settings
from src.queue.event_queue import EventQueue
from src.services.backend_client import BackendClient, BackendStatus
from src.services.delivery import DeliveryService


def _settings(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "\n".join(
            [
                "SITE_ID=falun",
                "BACKEND_URL=https://backend.example",
                "ANPR_AGENT_TOKEN=secret",
                "CAMERA_RTSP_URL=rtsp://127.0.0.1/stream",
                "STORAGE_DIR=./storage",
                "LOG_DIR=./logs",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return Settings(_env_file=env)


def test_refresh_backend_status_uses_cache(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    backend = BackendClient(settings)
    backend.check_backend = AsyncMock(
        return_value=BackendStatus(True, "ok", "https://backend.example")
    )
    delivery = DeliveryService(settings, backend, EventQueue(tmp_path / "queue.json"))

    async def run() -> None:
        first = await delivery.refresh_backend_status(force=True)
        second = await delivery.refresh_backend_status()
        assert first.ok is True
        assert second.ok is True
        assert backend.check_backend.await_count == 1

    asyncio.run(run())
