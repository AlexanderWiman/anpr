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


def test_format_ocr_error_winerror_126():
    exc = OSError(
        "[WinError 126] Det går inte att hitta den angivna modulen. "
        "Error loading 'C:\\\\ProgramData\\\\anpr-edge-agent\\\\.venv\\\\Lib\\\\site-packages\\\\torch\\\\lib\\\\c10.dll' "
        "or one of its dependencies."
    )
    message = format_ocr_error(exc)
    assert "visual c++" in message.lower()
    assert "c10.dll" not in message.lower()
