"""Tests for Windows-safe subprocess helpers."""

import subprocess
import sys

from installer import subprocess_utils as sp


def test_subprocess_text_kwargs_on_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    assert sp.subprocess_text_kwargs() == {"encoding": "utf-8", "errors": "replace"}


def test_subprocess_text_kwargs_on_unix():
    if sys.platform == "win32":
        return
    assert sp.subprocess_text_kwargs() == {}


def test_run_checked_passes_text_kwargs_on_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    captured: dict = {}

    def fake_run(cmd, **kwargs):
        captured.update(kwargs)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(sp.subprocess, "run", fake_run)
    sp.run_checked([sys.executable, "-c", "print(1)"])
    assert captured["encoding"] == "utf-8"
    assert captured["errors"] == "replace"
