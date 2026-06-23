"""Tests for prerequisite detection."""

import sys
from unittest.mock import patch

from installer import prerequisites as prereq


def test_windows_store_stub_detection():
    assert prereq._is_windows_store_stub(
        r"C:\Users\me\AppData\Local\Microsoft\WindowsApps\python.exe"
    )
    assert not prereq._is_windows_store_stub(
        r"C:\Users\me\AppData\Local\Programs\Python\Python312\python.exe"
    )


def test_find_python_executable_uses_current_interpreter_on_unix():
    if sys.platform == "win32":
        return
    found = prereq.find_python_executable()
    assert found
    assert prereq._python_version_ok(found)


def test_get_prerequisite_status_reports_python_on_unix():
    if sys.platform == "win32":
        return
    items = {item.id: item for item in prereq.get_prerequisite_status()}
    assert items["python"].ok


def test_run_optional_does_not_raise(tmp_path):
    from installer.engine import _run

    log_messages: list[str] = []

    def log(msg: str) -> None:
        log_messages.append(msg)

    _run(["false"], tmp_path, log, optional=True)
    assert log_messages
