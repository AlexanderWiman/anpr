import httpx

from src import __version__
from src.config.settings import Settings
from src.models.event import AnprEvent
from src.utils.logging import get_logger

logger = get_logger(__name__)


class BackendStatus:
    """Result of checking connectivity and credentials against the backend."""

    __slots__ = ("ok", "code", "detail")

    def __init__(self, ok: bool, code: str, detail: str) -> None:
        self.ok = ok
        self.code = code
        self.detail = detail

    def as_dict(self) -> dict[str, str | bool]:
        return {"ok": self.ok, "code": self.code, "detail": self.detail, "reachable": self.ok}


class BackendClient:
    """HTTP client for remote ANPR backend API."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.backend_timeout_seconds),
            headers={
                "Authorization": f"Bearer {settings.anpr_agent_token}",
                "Content-Type": "application/json",
                "User-Agent": f"anpr-edge-agent/{__version__}",
            },
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def check_backend(self) -> BackendStatus:
        """Verify backend is reachable and the configured token is accepted."""
        base = self._settings.backend_url.rstrip("/")

        try:
            response = await self._client.get(f"{base}/health")
            if response.status_code >= 500:
                return BackendStatus(False, "down", "Backend svarar inte")
        except httpx.HTTPError:
            return BackendStatus(False, "down", "Kan inte nå backend — kontrollera internet")

        try:
            response = await self._client.get(self._settings.backend_expected_plates_url)
        except httpx.HTTPError as exc:
            return BackendStatus(False, "down", f"Kan inte nå backend: {exc}")

        if response.status_code == 200:
            return BackendStatus(True, "ok", base)
        if response.status_code in (401, 403):
            return BackendStatus(False, "invalid_token", "Token ogiltig — kontakta IT")
        if response.status_code == 422:
            return BackendStatus(
                False,
                "invalid_site",
                "Okänd anläggning — kontrollera SITE_ID i inställningarna",
            )
        if response.status_code == 503:
            return BackendStatus(False, "misconfigured", "Backend är inte konfigurerad för ANPR")

        return BackendStatus(
            False,
            "down",
            f"Backend svarade med oväntat fel ({response.status_code})",
        )

    async def healthcheck(self) -> bool:
        """True only when backend accepts our token."""
        return (await self.check_backend()).ok

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
