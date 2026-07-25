from datetime import datetime, timedelta, timezone

from src.services.status_report import effective_camera_status


def test_effective_status_stays_connected_during_reconnect_with_recent_frame():
    now = datetime(2026, 7, 25, 12, 0, 0, tzinfo=timezone.utc)
    last_frame = now - timedelta(seconds=30)

    assert (
        effective_camera_status(
            "reconnecting",
            last_frame,
            agent_running=True,
            now=now,
        )
        == "connected"
    )


def test_effective_status_shows_reconnecting_when_frame_is_stale():
    now = datetime(2026, 7, 25, 12, 0, 0, tzinfo=timezone.utc)
    last_frame = now - timedelta(minutes=5)

    assert (
        effective_camera_status(
            "reconnecting",
            last_frame,
            agent_running=True,
            now=now,
        )
        == "reconnecting"
    )


def test_effective_status_idle_when_agent_stopped():
    now = datetime.now(timezone.utc)
    assert (
        effective_camera_status(
            "connected",
            now,
            agent_running=False,
            now=now,
        )
        == "idle"
    )
