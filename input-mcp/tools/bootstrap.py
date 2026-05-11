"""Bootstrap: token gen, port pick, UI subprocess spawn, health poll.

Called from main.py at MCP server startup. Records discovery files under
~/.mcp/input/ so any consumer can find the running UI service.
"""
from __future__ import annotations

import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx

from . import paths
from ._logging import get_logger

log = get_logger("bootstrap")

PORT_RANGE = range(47800, 47900)
HEALTH_TIMEOUT_S = 12.0


def _is_port_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def _pick_port(host: str = "127.0.0.1") -> int:
    for p in PORT_RANGE:
        if _is_port_free(host, p):
            return p
    raise RuntimeError(f"no free port found in {PORT_RANGE.start}-{PORT_RANGE.stop - 1}")


def _process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _ui_healthy(token: str, port: int, timeout: float = 1.5) -> bool:
    try:
        r = httpx.get(
            f"http://127.0.0.1:{port}/health",
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout,
        )
        return r.status_code == 200 and r.json().get("ok") is True
    except Exception:
        return False


def _try_reuse_existing() -> tuple[int, int, str] | None:
    """If a healthy UI is already running, return (pid, port, token)."""
    pid = paths.read_pid()
    port = paths.read_port()
    token = paths.read_token()
    if not (pid and port and token):
        return None
    if not _process_alive(pid):
        return None
    if not _ui_healthy(token, port):
        return None
    return pid, port, token


def _spawn_ui(port: int, token_file: Path, parent_pid: int) -> subprocess.Popen:
    project_root = Path(__file__).resolve().parents[1]
    venv_python = project_root / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        python = str(venv_python)
    else:
        python = sys.executable

    args = [
        python, "-m", "ui_app",
        "--port", str(port),
        "--token-file", str(token_file),
        "--parent-pid", str(parent_pid),
    ]
    creationflags = 0
    if sys.platform == "win32":
        # Detach: no console window, new process group.
        creationflags = (
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
    log.info("spawning ui: %s", " ".join(args))
    return subprocess.Popen(
        args,
        cwd=str(project_root),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
        close_fds=True,
    )


def start_ui() -> tuple[int, str]:
    """Ensure a UI service is running. Returns (port, token).

    Reuses an existing healthy UI if present; otherwise spawns a fresh one.
    """
    paths.ensure_root()

    existing = _try_reuse_existing()
    if existing:
        pid, port, token = existing
        log.info("reusing existing ui pid=%d port=%d", pid, port)
        return port, token

    token = secrets.token_hex(32)
    port = _pick_port()
    paths.TOKEN_FILE.write_text(token, encoding="utf-8")
    paths.PORT_FILE.write_text(str(port), encoding="utf-8")
    if sys.platform != "win32":
        try:
            os.chmod(paths.TOKEN_FILE, 0o600)
        except OSError:
            pass

    proc = _spawn_ui(port, paths.TOKEN_FILE, os.getpid())
    paths.PID_FILE.write_text(str(proc.pid), encoding="utf-8")

    deadline = time.time() + HEALTH_TIMEOUT_S
    while time.time() < deadline:
        if proc.poll() is not None:
            log.error("ui_app exited early with code %s", proc.returncode)
            raise RuntimeError(f"ui_app exited with {proc.returncode} during startup")
        if _ui_healthy(token, port):
            log.info("ui_app healthy at 127.0.0.1:%d (pid=%d)", port, proc.pid)
            return port, token
        time.sleep(0.2)

    log.error("ui_app failed health check within %.1fs", HEALTH_TIMEOUT_S)
    proc.terminate()
    raise RuntimeError("ui_app failed to become healthy in time")


def shutdown_ui(token: str, port: int) -> None:
    try:
        httpx.post(
            f"http://127.0.0.1:{port}/shutdown",
            headers={"Authorization": f"Bearer {token}"},
            timeout=2.0,
        )
    except Exception as exc:  # noqa: BLE001
        log.debug("graceful shutdown POST failed: %s", exc)
