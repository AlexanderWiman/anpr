from src.services.remote_camera_config import (
    camera_config_fingerprint,
    camera_configs_from_remote_payload,
)


def test_remote_payload_maps_detection_roi():
    cameras = camera_configs_from_remote_payload(
        {
            "cameras": [
                {
                    "id": "entrance-1",
                    "enabled": True,
                    "cameraType": "tapo",
                    "cameraIp": "192.168.1.10",
                    "detectionRoiEnabled": True,
                    "detectionRoiBand": "top",
                    "detectionRoiFraction": 0.45,
                },
                {
                    "id": "entrance-2",
                    "enabled": True,
                    "cameraType": "tapo",
                    "cameraIp": "192.168.1.11",
                    "detectionRoiEnabled": True,
                    "detectionRoiBand": "bottom",
                    "detectionRoiFraction": 0.40,
                },
            ]
        }
    )
    assert cameras[0].detection_roi_enabled is True
    assert cameras[0].detection_roi_band == "top"
    assert cameras[0].detection_roi_fraction == 0.45
    assert cameras[1].detection_roi_band == "bottom"
    assert cameras[1].detection_roi_fraction == 0.40

    fp1 = camera_config_fingerprint(cameras)
    cameras[1].detection_roi_fraction = 0.5
    assert camera_config_fingerprint(cameras) != fp1
