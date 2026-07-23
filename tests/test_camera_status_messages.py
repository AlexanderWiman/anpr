from src.camera.status_messages import camera_status_message, rtsp_host_label


def test_rtsp_host_label():
    assert rtsp_host_label("rtsp://user:pass@172.28.107.154:554/stream1") == "172.28.107.154:554"


def test_connection_timeout_message():
    msg = camera_status_message(
        status="error",
        reason="connection_timeout",
        rtsp_url="rtsp://u:p@172.28.107.154:554/stream1",
        timeout_ms=10000,
    )
    assert "172.28.107.154:554" in msg
    assert "Timeout" in msg


def test_no_frame_message_mentions_vlc():
    msg = camera_status_message(
        status="error",
        reason="no_frame_received",
        rtsp_url="rtsp://u:p@172.28.107.154:554/stream1",
    )
    assert "VLC" in msg


def test_connecting_message():
    msg = camera_status_message(
        status="connecting",
        rtsp_url="rtsp://u:p@172.28.107.226:554/stream1",
    )
    assert msg.startswith("Ansluter till 172.28.107.226:554")
