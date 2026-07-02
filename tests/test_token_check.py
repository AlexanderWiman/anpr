"""Tests for installer backend token validation."""

from unittest.mock import MagicMock, patch

from installer.token_check import validate_backend_credentials


def test_validate_backend_credentials_ok():
    response = MagicMock()
    response.status = 200
    response.__enter__ = MagicMock(return_value=response)
    response.__exit__ = MagicMock(return_value=False)

    with patch("installer.token_check.urllib.request.urlopen", return_value=response):
        ok, message = validate_backend_credentials(
            site_id="falun",
            backend_url="https://backend.example.com",
            token="good-token",
        )

    assert ok is True
    assert "godkänd" in message.lower()


def test_validate_backend_credentials_invalid_token():
    import urllib.error

    error = urllib.error.HTTPError(
        "https://backend.example.com/api/anpr/sites/falun/expected-plates",
        403,
        "Forbidden",
        hdrs=None,
        fp=MagicMock(read=MagicMock(return_value=b'{"message":"Invalid token"}')),
    )

    with patch("installer.token_check.urllib.request.urlopen", side_effect=error):
        ok, message = validate_backend_credentials(
            site_id="falun",
            backend_url="https://backend.example.com",
            token="bad-token",
        )

    assert ok is False
    assert "ogiltig" in message.lower()
