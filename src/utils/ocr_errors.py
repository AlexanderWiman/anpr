"""Human-readable OCR / model-load errors for logs and dashboard."""

from __future__ import annotations


def format_ocr_error(exc: BaseException) -> str:
    message = str(exc).strip()
    lowered = message.lower()

    if "winerror 206" in lowered or "filnamnstill" in lowered or "too long" in lowered:
        return (
            "OCR kunde inte starta: installationsvägen är för lång för PyTorch på Windows. "
            "Flytta agenten till C:\\ProgramData\\anpr-edge-agent och skapa om Python-miljön (.venv)."
        )

    if isinstance(exc, ImportError) or "no module named" in lowered:
        return (
            "OCR saknar Python-paket. Kör om installationen eller "
            "pip install -r requirements-ai.txt -r requirements-ocr.txt i .venv."
        )

    if isinstance(exc, FileNotFoundError) and "yolo" in lowered:
        return "YOLO-modellen saknas. Kör om installationen så att modellen laddas ner."

    if "winerror 126" in lowered or "c10.dll" in lowered:
        return (
            "PyTorch/OCR kunde inte laddas (saknad DLL). "
            "Installera Microsoft Visual C++ Redistributable x64 och kör om Python-miljön (.venv). "
            "Kör scripts\\install-prerequisites.ps1 som administratör (64-bit PowerShell, inte x86)"
        )

    if "certificate_verify_failed" in lowered or "ssl: cert" in lowered:
        return (
            "OCR-modellen kunde inte laddas ner (SSL-certifikat). "
            "Kör om installationen/uppdateringen som administratör så OCR-modellen laddas till models\\ocr, "
            "eller starta om agenten efter att certifi är installerat i .venv."
        )

    if message:
        return f"OCR-fel: {message}"
    return "OCR-fel: okänt fel vid modellstart"
