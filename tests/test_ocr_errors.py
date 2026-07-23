"""Tests for OCR error formatting."""

from src.utils.ocr_errors import format_ocr_error


def test_format_ocr_error_winerror_206():
    exc = OSError(
        "[WinError 206] Filnamnet eller filnamnstillägget är för långt: "
        "'C:\\\\Users\\\\Olles Falun\\\\AppData\\\\Local\\\\anpr-edge-agent\\\\.venv\\\\Lib\\\\site-packages\\\\torch\\\\lib'"
    )
    message = format_ocr_error(exc)
    assert "för lång" in message.lower()
    assert "programdata" in message.lower()
