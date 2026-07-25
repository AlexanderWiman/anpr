import numpy as np
import pytest

from src.utils.motion_gate import MotionGate


def test_motion_gate_skips_static_scene(tmp_path):
    gate = MotionGate(threshold=0.05, active_seconds=10)
    frame = tmp_path / "frame.png"

    gray = np.full((120, 160, 3), 128, dtype=np.uint8)
    import cv2

    cv2.imwrite(str(frame), gray)

    assert gate.should_process(frame) is False
    assert gate.should_process(frame) is False
    assert gate.stats["frames_skipped"] == 2


def test_motion_gate_activates_on_change(tmp_path):
    gate = MotionGate(threshold=0.01, active_seconds=10)
    frame = tmp_path / "frame.png"

    import cv2

    cv2.imwrite(str(frame), np.full((120, 160, 3), 40, dtype=np.uint8))
    assert gate.should_process(frame) is False

    cv2.imwrite(str(frame), np.full((120, 160, 3), 220, dtype=np.uint8))
    assert gate.should_process(frame) is True
    assert gate.is_active is True
    assert gate.stats["activations"] == 1

    cv2.imwrite(str(frame), np.full((120, 160, 3), 220, dtype=np.uint8))
    assert gate.should_process(frame) is True


def test_motion_gate_periodic_scan_triggers_on_static_scene(tmp_path, monkeypatch):
    gate = MotionGate(threshold=0.05, active_seconds=10, periodic_scan_seconds=60)
    frame = tmp_path / "frame.png"

    import cv2

    gray = np.full((120, 160, 3), 128, dtype=np.uint8)
    cv2.imwrite(str(frame), gray)

    clock = iter([0.0, 0.0, 65.0, 65.0, 65.0])
    monkeypatch.setattr(
        "src.utils.motion_gate.time.monotonic",
        lambda: next(clock, 130.0),
    )

    assert gate.should_process(frame) is False
    assert gate.should_process(frame) is False
    assert gate.should_process(frame) is True
    assert gate.is_active is True
    assert gate.stats["activations"] == 1
