from src.utils.detection_roi import clamp_roi_top_fraction, detection_roi_slice


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
