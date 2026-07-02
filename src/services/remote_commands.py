"""Handle IT-triggered remote commands delivered via heartbeat responses."""

from __future__ import annotations

import asyncio
import logging

from src.services.remote_update import spawn_remote_update

logger = logging.getLogger(__name__)


async def handle_heartbeat_commands_async(agent, commands: list[dict] | None) -> None:
    if not commands:
        return

    for command in commands:
        command_type = command.get("type")
        if command_type == "capture_frame":
            request_id = command.get("requestId")
            if request_id:
                asyncio.create_task(
                    agent.perform_remote_frame_capture(str(request_id)),
                    name=f"frame-capture-{request_id}",
                )
            continue
        if command_type == "update":
            await asyncio.to_thread(spawn_remote_update, command)
            return
