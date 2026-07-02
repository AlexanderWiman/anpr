"""Detect and optionally install system prerequisites for ANPR."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path


def _ensure_path() -> None:
    """GUI-launched apps on macOS often miss Homebrew in PATH."""
    if sys.platform == "darwin":
        extra = ["/opt/homebrew/bin", "/usr/local/bin"]
    elif sys.platform == "win32":
        extra = [
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Links"),
            r"C:\ffmpeg\bin",
        ]
    else:
        extra = ["/usr/local/bin"]

    current = os.environ.get("PATH", "")
    parts = [p for p in current.split(os.pathsep) if p]
    for directory in reversed(extra):
        if directory and directory not in parts:
            parts.insert(0, directory)
    os.environ["PATH"] = os.pathsep.join(parts)


_ensure_path()


def _extra_search_dirs() -> list[Path]:
    dirs: list[Path] = []
    if sys.platform == "darwin":
        dirs.extend([Path("/opt/homebrew/bin"), Path("/usr/local/bin")])
    elif sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA", "")
        if local:
            dirs.append(Path(local) / "Microsoft" / "WinGet" / "Links")
        dirs.append(Path(r"C:\ffmpeg\bin"))
    dirs.extend(Path(p) for p in os.environ.get("PATH", "").split(os.pathsep) if p)
    return dirs


def find_executable(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    for directory in _extra_search_dirs():
        candidate = directory / name
        if sys.platform == "win32" and not name.lower().endswith(".exe"):
            candidate = directory / f"{name}.exe"
        if candidate.is_file():
            return str(candidate)
    return None


def find_ffmpeg() -> str | None:
    return find_executable("ffmpeg")


def _is_windows_store_stub(path: str) -> bool:
    normalized = path.replace("/", "\\").lower()
    return "windowsapps" in normalized


def _subprocess_flags() -> int:
    if sys.platform == "win32" and hasattr(subprocess, "CREATE_NO_WINDOW"):
        return subprocess.CREATE_NO_WINDOW
    return 0


def _python_version_ok(path: str) -> bool:
    if _is_windows_store_stub(path):
        return False
    if not os.path.isfile(path):
        return False
    try:
        proc = subprocess.run(
            [path, "-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"],
            capture_output=True,
            timeout=20,
            creationflags=_subprocess_flags(),
        )
        return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def find_python_executable() -> str | None:
    if sys.platform != "win32":
        if sys.version_info >= (3, 11) and not _is_windows_store_stub(sys.executable):
            return sys.executable
        for name in ("python3", "python"):
            found = find_executable(name)
            if found and _python_version_ok(found):
                return found
        return None

    candidates: list[str] = []
    py_launcher = find_executable("py")
    if py_launcher:
        for flag in ("-3.12", "-3.11", "-3"):
            try:
                proc = subprocess.run(
                    [py_launcher, flag, "-c", "import sys; print(sys.executable)"],
                    capture_output=True,
                    text=True,
                    timeout=20,
                    creationflags=_subprocess_flags(),
                )
                if proc.returncode == 0:
                    candidates.append(proc.stdout.strip())
            except (OSError, subprocess.TimeoutExpired):
                continue

    for name in ("python", "python3"):
        found = find_executable(name)
        if found:
            candidates.append(found)

    local = os.environ.get("LOCALAPPDATA", "")
    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    for version in ("313", "312", "311"):
        candidates.append(os.path.join(local, "Programs", "Python", f"Python{version}", "python.exe"))
        candidates.append(os.path.join(program_files, f"Python{version}", "python.exe"))

    seen: set[str] = set()
    for path in candidates:
        if not path or path in seen:
            continue
        seen.add(path)
        if _python_version_ok(path):
            return path
    return None


def _has_winget() -> bool:
    return sys.platform == "win32" and find_executable("winget") is not None


def _has_brew() -> bool:
    return sys.platform == "darwin" and find_executable("brew") is not None


@dataclass
class PrereqItem:
    id: str
    name: str
    ok: bool
    message: str
    can_auto_install: bool
    manual_url: str | None = None
    manual_hint: str | None = None


def get_prerequisite_status() -> list[PrereqItem]:
    if sys.platform == "win32":
        py_path = find_python_executable()
        py_ok = py_path is not None
        if py_ok:
            py_msg = f"Python — OK"
        else:
            py_msg = "Python 3.11+ saknas (Microsoft Store-alias räknas inte som Python)"
    else:
        py_ok = sys.version_info >= (3, 11)
        if py_ok:
            py_msg = f"Python {sys.version_info.major}.{sys.version_info.minor} — OK"
        else:
            py_msg = "Python 3.11+ saknas"

    ff_path = find_ffmpeg()
    ff_ok = ff_path is not None

    if ff_ok:
        ff_msg = "ffmpeg — OK"
    else:
        ff_msg = "ffmpeg saknas (behövs för kameraström)"

    py_auto = _has_winget() or _has_brew()
    ff_auto = _has_winget() or _has_brew()

    return [
        PrereqItem(
            id="python",
            name="Python 3.11+",
            ok=py_ok,
            message=py_msg,
            can_auto_install=py_auto and not py_ok,
            manual_url="https://www.python.org/downloads/",
            manual_hint=(
                "Windows: kryssa i «Add Python to PATH» eller stäng av Store-alias under Appkörningsalias"
                if sys.platform == "win32"
                else "Mac: ladda ner installationspaketet från python.org"
            ),
        ),
        PrereqItem(
            id="ffmpeg",
            name="FFmpeg",
            ok=ff_ok,
            message=ff_msg,
            can_auto_install=ff_auto and not ff_ok,
            manual_url="https://ffmpeg.org/download.html",
            manual_hint=(
                "Windows: winget install Gyan.FFmpeg"
                if sys.platform == "win32"
                else "Mac: brew install ffmpeg"
            ),
        ),
    ]


def prerequisites_ok() -> bool:
    return all(item.ok for item in get_prerequisite_status())


def check_prerequisites() -> list[str]:
    return [item.message for item in get_prerequisite_status() if not item.ok]


def prerequisite_status_payload() -> dict:
    items = get_prerequisite_status()
    return {
        "ok": all(item.ok for item in items),
        "items": [asdict(item) for item in items],
        "platform": sys.platform,
        "restart_hint": _restart_hint(),
    }


def _restart_hint() -> str | None:
    if sys.platform == "win32":
        return (
            "Stäng guiden och starta launch\\Installer.cmd igen efter att Python installerats. "
            "Om felet kvarstår: stäng av python.exe under Inställningar → Appkörningsalias."
        )
    if sys.platform == "darwin":
        return "Starta om installationsguiden om programmen inte hittas direkt."
    return None


def _run_install(cmd: list[str], log: Callable[[str], None]) -> None:
    log(f"Kör: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def install_prerequisite(item_id: str, log: Callable[[str], None]) -> dict:
    """Try to install one prerequisite. Returns {ok, message, needs_restart}."""
    items = {item.id: item for item in get_prerequisite_status()}
    item = items.get(item_id)
    if item is None:
        return {"ok": False, "message": f"Okänd komponent: {item_id}", "needs_restart": False}
    if item.ok:
        return {"ok": True, "message": f"{item.name} är redan installerat", "needs_restart": False}

    try:
        if item_id == "ffmpeg":
            return _install_ffmpeg(log)
        if item_id == "python":
            return _install_python(log)
    except subprocess.CalledProcessError as exc:
        return {
            "ok": False,
            "message": f"Installation misslyckades (kod {exc.returncode}). Prova manuell installation.",
            "needs_restart": False,
        }
    except FileNotFoundError:
        return {
            "ok": False,
            "message": "Automatisk installation stöds inte på den här datorn. Följ länken nedan.",
            "needs_restart": False,
        }

    return {"ok": False, "message": "Kunde inte installera", "needs_restart": False}


def _install_ffmpeg(log: Callable[[str], None]) -> dict:
    if _has_winget():
        _run_install(
            [
                "winget",
                "install",
                "-e",
                "--id",
                "Gyan.FFmpeg",
                "--accept-package-agreements",
                "--accept-source-agreements",
            ],
            log,
        )
        if find_ffmpeg():
            return {"ok": True, "message": "ffmpeg installerat", "needs_restart": False}
        return {
            "ok": True,
            "message": "ffmpeg installerat — starta om guiden om kameran inte fungerar",
            "needs_restart": True,
        }

    if _has_brew():
        _run_install(["brew", "install", "ffmpeg"], log)
        return {"ok": True, "message": "ffmpeg installerat via Homebrew", "needs_restart": False}

    raise FileNotFoundError("no package manager")


def _install_python(log: Callable[[str], None]) -> dict:
    if _has_winget():
        _run_install(
            [
                "winget",
                "install",
                "-e",
                "--id",
                "Python.Python.3.12",
                "--accept-package-agreements",
                "--accept-source-agreements",
            ],
            log,
        )
        return {
            "ok": True,
            "message": "Python installerat — stäng guiden och starta Install ANPR igen",
            "needs_restart": True,
        }

    if _has_brew():
        _run_install(["brew", "install", "python@3.12"], log)
        return {
            "ok": True,
            "message": "Python installerat via Homebrew — starta om guiden",
            "needs_restart": True,
        }

    if sys.platform == "darwin":
        subprocess.run(["open", "https://www.python.org/downloads/"], check=False)
        return {
            "ok": False,
            "message": "Öppnade python.org — installera Python och starta sedan om guiden",
            "needs_restart": True,
        }

    raise FileNotFoundError("no package manager")


def install_all_missing(log: Callable[[str], None]) -> dict:
    results: list[dict] = []
    needs_restart = False
    for item in get_prerequisite_status():
        if item.ok:
            continue
        if not item.can_auto_install:
            results.append(
                {
                    "id": item.id,
                    "ok": False,
                    "message": f"{item.name}: automatisk installation ej tillgänglig",
                }
            )
            continue
        result = install_prerequisite(item.id, log)
        result["id"] = item.id
        results.append(result)
        needs_restart = needs_restart or result.get("needs_restart", False)

    ok = prerequisites_ok() or (needs_restart and any(r.get("ok") for r in results))
    return {"ok": ok, "results": results, "needs_restart": needs_restart}


def bootstrap_shell_commands() -> list[str]:
    """Commands for shell launchers to run before starting the wizard."""
    cmds: list[str] = []
    if sys.platform == "win32":
        if find_ffmpeg() is None and _has_winget():
            cmds.append(
                "winget install -e --id Gyan.FFmpeg "
                "--accept-package-agreements --accept-source-agreements"
            )
        return cmds

    if sys.platform == "darwin":
        if find_ffmpeg() is None and _has_brew():
            cmds.append("brew install ffmpeg")
        if sys.version_info < (3, 11) and _has_brew():
            cmds.append("brew install python@3.12")
    return cmds
