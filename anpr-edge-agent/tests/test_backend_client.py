"""Tests for backend connectivity checks."""

import asyncio
from unittest.mock import AsyncMock

import httpx

from src.config.settings import Settings
from src.services.backend_client import BackendClient


def _settings() -> Settings:
    return Settings(
        site_id="falun",
        camera_id="entrance-1",
        direction="entry",
        camera_rtsp_url="rtsp://127.0.0.1/stream1",
        backend_url="https://backend.example.com",
        anpr_agent_token="secret-token",
    )


def test_check_backend_ok():
    client = BackendClient(_settings())
    health = httpx.Response(200, request=httpx.Request("GET", "https://backend.example.com/health"))
    plates = httpx.Response(
        200,
        request=httpx.Request(
            "GET",
            "https://backend.example.com/api/anpr/sites/falun/expected-plates",
        ),
    )
    client._client.get = AsyncMock(side_effect=[health, plates])  # noqa: SLF001

    status = asyncio.run(client.check_backend())

    assert status.ok is True
    assert status.code == "ok"


def test_check_backend_invalid_token():
    client = BackendClient(_settings())
    health = httpx.Response(200, request=httpx.Request("GET", "https://backend.example.com/health"))
    plates = httpx.Response(
        403,
        request=httpx.Request(
            "GET",
            "https://backend.example.com/api/anpr/sites/falun/expected-plates",
        ),
    )
    client._client.get = AsyncMock(side_effect=[health, plates])  # noqa: SLF001

    status = asyncio.run(client.check_backend())

    assert status.ok is False
    assert status.code == "invalid_token"


def test_check_backend_unreachable():
    client = BackendClient(_settings())
    client._client.get = AsyncMock(side_effect=httpx.ConnectError("offline"))  # noqa: SLF001

    status = asyncio.run(client.check_backend())

    assert status.ok is False
    assert status.code == "down"
