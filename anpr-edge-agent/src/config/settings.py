from functools import lru_cache
from pathlib import Path
from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Site identity (set via sites/<name>.env)
    site_id: str = Field(default="falun", alias="SITE_ID")
    camera_id: str = Field(default="entrance-1", alias="CAMERA_ID")
    direction: str = Field(default="entry", alias="DIRECTION")

    # RTSP camera
    camera_rtsp_url: str = Field(alias="CAMERA_RTSP_URL")
    frame_interval_ms: int = Field(default=1000, alias="FRAME_INTERVAL_MS")
    motion_gate_enabled: bool = Field(default=True, alias="MOTION_GATE_ENABLED")
    motion_threshold: float = Field(default=0.012, alias="MOTION_THRESHOLD")
    motion_active_seconds: float = Field(default=45.0, alias="MOTION_ACTIVE_SECONDS")
    motion_scan_interval_ms: int = Field(default=5000, alias="MOTION_SCAN_INTERVAL_MS")
    rtsp_connect_timeout_ms: int = Field(default=10000, alias="RTSP_CONNECT_TIMEOUT_MS")
    rtsp_reconnect_delay_ms: int = Field(default=5000, alias="RTSP_RECONNECT_DELAY_MS")
    rtsp_transport: str = Field(default="tcp", alias="RTSP_TRANSPORT")

    # Backend
    backend_url: str = Field(alias="BACKEND_URL")
    anpr_agent_token: str = Field(alias="ANPR_AGENT_TOKEN")
    backend_timeout_seconds: float = Field(default=10.0, alias="BACKEND_TIMEOUT_SECONDS")
    backend_max_retries: int = Field(default=5, alias="BACKEND_MAX_RETRIES")
    backend_retry_base_delay_seconds: float = Field(
        default=2.0, alias="BACKEND_RETRY_BASE_DELAY_SECONDS"
    )
    booking_hints_enabled: bool = Field(default=True, alias="BOOKING_HINTS_ENABLED")
    booking_hints_refresh_seconds: int = Field(
        default=600, alias="BOOKING_HINTS_REFRESH_SECONDS"
    )
    heartbeat_enabled: bool = Field(default=True, alias="HEARTBEAT_ENABLED")
    heartbeat_interval_seconds: int = Field(default=60, alias="HEARTBEAT_INTERVAL_SECONDS")

    # YOLO + OCR
    min_confidence: float = Field(default=0.55, alias="MIN_CONFIDENCE")
    ocr_min_confidence: float = Field(default=0.55, alias="OCR_MIN_CONFIDENCE")
    plate_cooldown_seconds: int = Field(default=60, alias="PLATE_COOLDOWN_SECONDS")
    yolo_model_path: Path = Field(default=Path("./models/plate_yolov8.pt"), alias="YOLO_MODEL_PATH")
    yolo_confidence: float = Field(default=0.15, alias="YOLO_CONFIDENCE")
    yolo_max_image_width: int = Field(default=1280, alias="YOLO_MAX_IMAGE_WIDTH")

    # Storage
    storage_dir: Path = Field(default=Path("./storage"), alias="STORAGE_DIR")
    save_snapshots: bool = Field(default=False, alias="SAVE_SNAPSHOTS")
    frame_retention_hours: float = Field(default=24.0, alias="FRAME_RETENTION_HOURS")
    frame_max_files: int = Field(default=200, alias="FRAME_MAX_FILES")
    frame_max_storage_mb: int = Field(default=256, alias="FRAME_MAX_STORAGE_MB")
    frame_cleanup_interval_sec: int = Field(default=300, alias="FRAME_CLEANUP_INTERVAL_SEC")

    # Web dashboard + agent control
    health_host: str = Field(default="0.0.0.0", alias="HEALTH_HOST")
    health_port: int = Field(default=8080, alias="HEALTH_PORT")
    web_history_size: int = Field(default=100, alias="WEB_HISTORY_SIZE")
    agent_auto_start: bool = Field(default=False, alias="AGENT_AUTO_START")

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_dir: Path = Field(default=Path("./logs"), alias="LOG_DIR")

    @model_validator(mode="after")
    def normalize_backend_url(self) -> Self:
        url = self.backend_url.rstrip("/")
        for suffix in ("/api/anpr/events", "/api/anpr", "/api/v1"):
            while url.endswith(suffix):
                url = url[: -len(suffix)]
        object.__setattr__(self, "backend_url", url)
        return self

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Installed .env must beat stale Windows user/system environment variables.
        return init_settings, env_settings, dotenv_settings, file_secret_settings

    @property
    def frames_dir(self) -> Path:
        return self.storage_dir / "frames"

    @property
    def events_dir(self) -> Path:
        return self.storage_dir / "events"

    @property
    def queue_file(self) -> Path:
        return self.events_dir / "pending_queue.json"

    @property
    def backend_events_url(self) -> str:
        base = self.backend_url.rstrip("/")
        return f"{base}/api/anpr/events"

    @property
    def backend_expected_plates_url(self) -> str:
        base = self.backend_url.rstrip("/")
        return f"{base}/api/anpr/sites/{self.site_id}/expected-plates"

    @property
    def backend_heartbeat_url(self) -> str:
        base = self.backend_url.rstrip("/")
        return f"{base}/api/anpr/sites/{self.site_id}/heartbeat"

    @property
    def backend_frame_capture_url(self) -> str:
        base = self.backend_url.rstrip("/")
        return f"{base}/api/anpr/sites/{self.site_id}/frame-captures"


def load_settings() -> Settings:
    """Load settings from the installed support .env when available."""
    import os

    from src.config.env_sync import installed_support_env

    support = installed_support_env()
    if support is not None:
        for key in (
            "ANPR_AGENT_TOKEN",
            "BACKEND_URL",
            "SITE_ID",
            "CAMERA_RTSP_URL",
            "CAMERA_ID",
            "DIRECTION",
        ):
            os.environ.pop(key, None)
        return Settings(_env_file=str(support))
    return Settings()


def settings_env_path() -> str | None:
    from pathlib import Path

    from src.config.env_sync import installed_support_env

    support = installed_support_env()
    if support is not None:
        return str(support)
    local = Path(".env")
    return str(local.resolve()) if local.is_file() else None


@lru_cache
def get_settings() -> Settings:
    return load_settings()
