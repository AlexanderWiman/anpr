from src.utils.detection_roi import (
    clamp_roi_top_fraction,
    detection_roi_slice,
    map_box_from_roi,
    roi_upscale_factor,
    should_full_frame_fallback,
)


def test_detection_roi_disabled_uses_full_frame():
    assert detection_roi_slice(576, enabled=False, top_fraction=0.35) == (0, 576)


def test_detection_roi_enabled_crops_top_fraction():
    assert detection_roi_slice(576, enabled=True, top_fraction=0.35) == (0, 201)


def test_detection_roi_invalid_fraction_falls_back_to_full_frame():
    assert detection_roi_slice(576, enabled=True, top_fraction=0) == (0, 576)
    assert detection_roi_slice(576, enabled=True, top_fraction=1) == (0, 576)
    assert detection_roi_slice(576, enabled=True, top_fraction=1.5) == (0, 576)


def test_clamp_roi_top_fraction():
    assert clamp_roi_top_fraction(0.35) == 0.35
    assert clamp_roi_top_fraction(0) == 0.0
    assert clamp_roi_top_fraction("bad") == 0.0


def test_roi_upscale_factor_enlarges_narrow_roi():
    assert roi_upscale_factor(1024, target_width=1280) == 1280 / 1024
    assert roi_upscale_factor(1280, target_width=1280) == 1.0
    assert roi_upscale_factor(2000, target_width=1280) == 1.0


def test_map_box_from_roi_undoes_scale_and_offset():
    assert map_box_from_roi(100, 40, 200, 80, y_offset=10, scale=2.0) == (50, 30, 100, 50)


def test_should_full_frame_fallback_when_roi_empty():
    assert should_full_frame_fallback(
        roi_enabled=True,
        frame_height=576,
        top_fraction=0.35,
        had_detections=False,
    )
    assert not should_full_frame_fallback(
        roi_enabled=True,
        frame_height=576,
        top_fraction=0.35,
        had_detections=True,
    )
    assert not should_full_frame_fallback(
        roi_enabled=False,
        frame_height=576,
        top_fraction=0.35,
        had_detections=False,
    )
