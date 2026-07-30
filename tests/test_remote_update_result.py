import json

from src.services.remote_update import load_pending_update_result


def test_load_pending_update_result_discards_non_uuid(tmp_path, monkeypatch):
    path = tmp_path / "update-result.json"
    path.write_text(
        json.dumps(
            {
                "requestId": "manual-abcd1234",
                "status": "failed",
                "error": "WinError 5",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "src.services.remote_update.update_result_path",
        lambda: path,
    )

    assert load_pending_update_result() is None
    assert not path.exists()


def test_load_pending_update_result_keeps_valid_uuid(tmp_path, monkeypatch):
    path = tmp_path / "update-result.json"
    request_id = "651c8114-f771-4c15-bb52-c0b9e8c7540a"
    path.write_text(
        json.dumps(
            {
                "requestId": request_id,
                "status": "failed",
                "error": "WinError 5",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "src.services.remote_update.update_result_path",
        lambda: path,
    )

    result = load_pending_update_result()
    assert result is not None
    assert result["requestId"] == request_id
    assert path.exists()
