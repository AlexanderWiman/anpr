from src.utils.ocr_errors import format_ocr_error
from src.utils.ssl_certs import configure_ssl_certificates


def test_configure_ssl_certificates_sets_env(monkeypatch):
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)

    bundle = configure_ssl_certificates()
    assert bundle
    import os

    assert os.environ["SSL_CERT_FILE"] == bundle
    assert os.environ["REQUESTS_CA_BUNDLE"] == bundle


def test_format_ocr_error_ssl_certificate():
    exc = OSError(
        "<urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: "
        "unable to get local issuer certificate (_ssl.c:1010)>"
    )
    message = format_ocr_error(exc)
    assert "ssl" in message.lower() or "certifikat" in message.lower()
