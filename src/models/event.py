from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field


class AnprEvent(BaseModel):
    site_id: str
    camera_id: str
    plate: str
    confidence: float = Field(ge=0.0, le=1.0)
    captured_at: datetime
    provider: str
    direction: str = "entry"
    snapshot_path: str | None = None

    def to_backend_payload(self) -> dict:
        return {
            "siteId": self.site_id,
            "cameraId": self.camera_id,
            "plate": self.plate,
            "confidence": self.confidence,
            "capturedAt": self.captured_at.astimezone(timezone.utc).isoformat().replace(
                "+00:00", "Z"
            ),
            "provider": self.provider,
            "direction": self.direction,
            "snapshotBase64": None,
        }


class QueuedEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    event: AnprEvent
    history_id: str | None = None
    attempts: int = 0
    last_attempt_at: datetime | None = None
    next_retry_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
