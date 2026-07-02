from src.queue.plate_confirmation import FramePlateBuffer


def test_does_not_reconfirm_previous_plate_when_new_plate_appears():
    buf = FramePlateBuffer(window_size=3, min_hits=2)

    assert buf.observe("IPP443", 0.8) is None
    assert buf.observe("IPP443", 0.82) == ("IPP443", 0.81)
    buf.mark_handled("IPP443")

    buf.observe_empty()

    assert buf.observe("JJS743", 0.85) is None
    assert buf.observe("JJS743", 0.87) == ("JJS743", 0.86)

    assert buf.observe("XPT772", 0.84) is None
    assert buf.observe("XPT772", 0.86) == ("XPT772", 0.85)


def test_long_scene_does_not_reconfirm_same_plate():
    buf = FramePlateBuffer(window_size=3, min_hits=2)

    assert buf.observe("BXB997", 0.7) is None
    assert buf.observe("BXB997", 0.72) == ("BXB997", 0.71)
    buf.mark_handled("BXB997")

    assert buf.observe("BXB997", 0.75) is None
    assert buf.observe("BXB997", 0.76) is None
    assert buf.observe("BXB997", 0.77) is None

    buf.observe_empty()
    assert buf.observe("BXB997", 0.7) is None
    assert buf.observe("BXB997", 0.72) == ("BXB997", 0.71)


def test_empty_frame_clears_stale_reads():
    buf = FramePlateBuffer(window_size=3, min_hits=2)

    buf.observe("IPP443", 0.8)
    buf.observe_empty()
    assert buf.observe("JJS743", 0.9) is None
