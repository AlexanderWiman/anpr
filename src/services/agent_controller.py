import asyncio
from datetime import datetime, timezone
from enum import Enum

from src.utils.logging import get_logger

logger = get_logger(__name__)


class AgentState(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


class AgentController:
    """Start/stop ANPR capture and delivery while keeping the web UI running."""

    def __init__(self, agent: "AnprAgent") -> None:  # noqa: F821
        self._agent = agent
        self._state = AgentState.STOPPED
        self._tasks: list[asyncio.Task] = []
        self._lock = asyncio.Lock()
        self._error: str | None = None
        self._agent_started_at: datetime | None = None

    @property
    def state(self) -> AgentState:
        return self._state

    def status(self) -> dict:
        uptime = None
        if self._state == AgentState.RUNNING and self._agent_started_at:
            uptime = round(
                (datetime.now(timezone.utc) - self._agent_started_at).total_seconds(), 1
            )
        return {
            "state": self._state.value,
            "autoStart": self._agent.settings.agent_auto_start,
            "startedAt": (
                self._agent_started_at.isoformat() if self._agent_started_at else None
            ),
            "uptimeSeconds": uptime,
            "error": self._error,
            "canStart": self._state in (AgentState.STOPPED, AgentState.ERROR),
            "canStop": self._state == AgentState.RUNNING,
        }

    async def start(self) -> dict:
        async with self._lock:
            if self._state == AgentState.RUNNING:
                return {"ok": True, "message": "Agenten kör redan", **self.status()}

            if self._state in (AgentState.STARTING, AgentState.STOPPING):
                return {"ok": False, "message": "Vänta — agenten byter status", **self.status()}

            self._state = AgentState.STARTING
            self._error = None

            logger.info("agent start requested", extra={"event": "agent_start_requested"})

            try:
                self._tasks = [
                    asyncio.create_task(
                        self._agent.delivery.run_retry_loop(), name="retry-loop"
                    ),
                ]
                for pipeline in self._agent.pipelines.values():
                    camera_id = pipeline.camera_id

                    async def frame_callback(
                        frame_path,
                        bound_camera_id=camera_id,
                    ) -> None:
                        await self._agent.process_frame_background(
                            frame_path,
                            bound_camera_id,
                        )

                    async def run_loop(bound_pipeline=pipeline) -> None:
                        await bound_pipeline.capture.run_capture_loop(
                            frame_callback,
                            interval_ms=bound_pipeline.get_capture_interval_ms,
                        )

                    self._tasks.append(
                        asyncio.create_task(
                            run_loop(),
                            name=f"capture-loop-{camera_id}",
                        )
                    )

                self._state = AgentState.RUNNING
                self._agent_started_at = datetime.now(timezone.utc)

                for pipeline in self._agent.pipelines.values():
                    pipeline.reset_runtime_state()

                logger.info(
                    "agent started",
                    extra={
                        "event": "agent_started",
                        "site_id": self._agent.settings.site_id,
                        "camera_ids": list(self._agent.pipelines.keys()),
                    },
                )
                return {"ok": True, "message": "Agenten är startad", **self.status()}

            except Exception as exc:
                self._state = AgentState.ERROR
                self._error = str(exc)
                logger.exception("agent start failed", extra={"event": "agent_error"})
                return {"ok": False, "message": f"Start misslyckades: {exc}", **self.status()}

    async def stop(self) -> dict:
        async with self._lock:
            if self._state == AgentState.STOPPED:
                return {"ok": True, "message": "Agenten är redan stoppad", **self.status()}

            if self._state in (AgentState.STARTING, AgentState.STOPPING):
                return {"ok": False, "message": "Vänta — agenten byter status", **self.status()}

            self._state = AgentState.STOPPING
            logger.info("agent stop requested", extra={"event": "agent_stop_requested"})

            for task in self._tasks:
                task.cancel()

            if self._tasks:
                await asyncio.gather(*self._tasks, return_exceptions=True)

            self._tasks.clear()
            for pipeline in self._agent.pipelines.values():
                await pipeline.capture.disconnect()
            self._state = AgentState.STOPPED
            self._agent_started_at = None

            logger.info("agent stopped", extra={"event": "agent_stopped"})
            return {"ok": True, "message": "Agenten är stoppad", **self.status()}
