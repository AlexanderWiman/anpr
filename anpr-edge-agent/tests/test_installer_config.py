"""Tests for installer .env readback."""

from installer.engine import decode_camera_url, parse_env_text, render_env, build_camera_url, InstallConfig


def test_parse_env_text_ignores_comments_and_quotes():
    text = """
# comment
SITE_ID=falun
ANPR_AGENT_TOKEN="secret-token"
"""
    env = parse_env_text(text)
    assert env["SITE_ID"] == "falun"
    assert env["ANPR_AGENT_TOKEN"] == "secret-token"


def test_decode_tapo_rtsp_url():
    cfg = decode_camera_url("rtsp://cam%40user:pa%3Ass@192.168.0.96:554/stream1")
    assert cfg["camera_type"] == "tapo"
    assert cfg["camera_ip"] == "192.168.0.96"
    assert cfg["camera_port"] == 554
    assert cfg["rtsp_user"] == "cam@user"
    assert cfg["rtsp_password"] == "pa:ss"


def test_decode_custom_rtsp_url():
    cfg = decode_camera_url("rtsp://192.168.1.10:8554/h264")
    assert cfg["camera_type"] == "rtsp"
    assert cfg["camera_ip"] == "192.168.1.10"
    assert cfg["rtsp_path"] == "/h264"


def test_decode_ip_webcam_url():
    cfg = decode_camera_url("http://192.168.0.50:8080/videofeed")
    assert cfg["camera_type"] == "ip_webcam"
    assert cfg["camera_port"] == 8080


def test_render_and_decode_roundtrip_tapo():
    cfg = InstallConfig(
        site_id="falun",
        camera_ip="192.168.0.96",
        camera_type="tapo",
        camera_port=554,
        rtsp_path="/stream1",
        rtsp_user="admin",
        rtsp_password="s3cret!",
        camera_id="entrance-1",
        direction="entry",
        backend_url="https://example.com",
        anpr_token="token-12345678",
    )
    env = parse_env_text(render_env(cfg))
    decoded = decode_camera_url(env["CAMERA_RTSP_URL"])
    assert decoded["camera_type"] == "tapo"
    assert decoded["camera_ip"] == cfg.camera_ip
    assert decoded["rtsp_user"] == cfg.rtsp_user
    assert decoded["rtsp_password"] == cfg.rtsp_password
    assert build_camera_url(cfg) == env["CAMERA_RTSP_URL"]
