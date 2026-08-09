from types import SimpleNamespace

from src.utils.detection_roi import (
    clamp_roi_top_fraction,
    detection_roi_slice,
    map_box_from_roi,
    merge_camera_config_roi_overrides,
    parse_detection_roi_by_camera,
    resolve_camera_roi,
    roi_upscale_factor,
    should_full_frame_fallback,
)


def test_detection_roi_disabled_uses_full_frame():
    assert detection_roi_slice(576, enabled=False, fraction=0.35) == (0, 576)


def test_detection_roi_enabled_crops_top_fraction():
    assert detection_roi_slice(576, enabled=True, fraction=0.35, band="top") == (0, 201)


def test_detection_roi_enabled_crops_bottom_fraction():
    # lower 35% of 576 → start at round(576*0.65)=374
    assert detection_roi_slice(576, enabled=True, fraction=0.35, band="bottom") == (
        374,
        576,
    )


def test_detection_roi_invalid_fraction_falls_back_to_full_frame():
    assert detection_roi_slice(576, enabled=True, fraction=0) == (0, 576)
    assert detection_roi_slice(576, enabled=True, fraction=1) == (0, 576)
    assert detection_roi_slice(576, enabled=True, fraction=1.5) == (0, 576)


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
        fraction=0.35,
        band="top",
        had_detections=False,
    )
    assert should_full_frame_fallback(
        roi_enabled=True,
        frame_height=576,
        fraction=0.35,
        band="bottom",
        had_detections=False,
    )
    assert not should_full_frame_fallback(
        roi_enabled=True,
        frame_height=576,
        fraction=0.35,
        had_detections=True,
    )
    assert not should_full_frame_fallback(
        roi_enabled=False,
        frame_height=576,
        fraction=0.35,
        had_detections=False,
    )


def test_parse_detection_roi_by_camera():
    parsed = parse_detection_roi_by_camera(
        '{"entrance-1":{"band":"top","fraction":0.45},'
        '"entrance-2":{"band":"bottom","fraction":0.40}}'
    )
    assert parsed["entrance-1"] == {
        "enabled": True,
        "band": "top",
        "fraction": 0.45,
    }
    assert parsed["entrance-2"] == {
        "enabled": True,
        "band": "bottom",
        "fraction": 0.40,
    }


def test_resolve_camera_roi_prefers_per_camera_override():
    by_camera = parse_detection_roi_by_camera(
        '{"entrance-2":{"band":"bottom","fraction":0.40}}'
    )
    enabled, band, fraction = resolve_camera_roi(
        "entrance-2",
        site_enabled=True,
        site_top_fraction=0.35,
        by_camera=by_camera,
    )
    assert (enabled, band, fraction) == (True, "bottom", 0.40)

    enabled, band, fraction = resolve_camera_roi(
        "entrance-1",
        site_enabled=True,
        site_top_fraction=0.35,
        by_camera=by_camera,
    )
    assert (enabled, band, fraction) == (True, "top", 0.35)


def test_merge_camera_config_roi_overrides_wins_over_env_map():
    by_camera = parse_detection_roi_by_camera(
        '{"entrance-1":{"band":"top","fraction":0.45}}'
    )
    cameras = [
        SimpleNamespace(
            id="entrance-1",
            detection_roi_enabled=True,
            detection_roi_band="bottom",
            detection_roi_fraction=0.40,
        ),
        SimpleNamespace(
            id="entrance-2",
            detection_roi_enabled=None,
            detection_roi_band=None,
            detection_roi_fraction=None,
        ),
    ]
    merged = merge_camera_config_roi_overrides(by_camera, cameras)
    assert merged["entrance-1"] == {
        "enabled": True,
        "band": "bottom",
        "fraction": 0.40,
    }
    assert "entrance-2" not in merged
