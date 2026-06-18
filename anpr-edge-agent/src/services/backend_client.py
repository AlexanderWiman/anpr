import httpx

from src.config.settings import Settings
from src.models.event import AnprEvent
from src.utils.logging import get_logger

logger = get_logger(__name__)


class BackendClient:
    """HTTP client for remote ANPR backend API."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.backend_timeout_seconds),
            headers={
                "Authorization": f"Bearer {settings.anpr_agent_token}",
                "Content-Type": "application/json",
                "User-Agent": "anpr-edge-agent/0.1.0",
            },
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def healthcheck(self) -> bool:
        """Check if backend is reachable."""
        base = self._settings.backend_url.rstrip("/")
        # Try common health paths; fall back to HEAD on base URL
        for path in ("/health", "/api/health", ""):
            try:
                url = f"{base}{path}" if path else base
                response = await self._client.get(url)
                if response.status_code < 500:
                    return True
            except httpx.HTTPError:
                continue
        return False

    async def send_anpr_event(self, event: AnprEvent) -> dict:
        """
        Send ANPR event to backend.

        Returns parsed JSON response on success.
        Raises httpx.HTTPError on failure.
        """
        payload = event.to_backend_payload()
        url = self._settings.backend_events_url

        logger.debug(
            "sending event to backend",
            extra={
                "event": "event_sending",
                "plate": event.plate,
                "url": url,
            },
        )

        response = await self._client.post(url, json=payload)
        response.raise_for_status()

        result = response.json()
        logger.info(
            "event delivered",
            extra={
                "event": "event_delivered",
                "plate": event.plate,
                "status_code": response.status_code,
                "response": result,
            },
        )
        return result

    async def fetch_expected_plates(self) -> dict:
        """Fetch today's expected registration numbers for this site."""
        url = self._settings.backend_expected_plates_url
        response = await self._client.get(url)
        response.raise_for_status()
        return response.json()
