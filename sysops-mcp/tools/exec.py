"""Shell command execution.

Local trust model — no allow/deny-list. Every invocation is logged with full
command, cwd, and exit code for audit.
"""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Any

from ._logging import get_logger

log = get_logger("exec")

_MAX_OUTPUT_BYTES = 100_000  # truncate stdout/stderr returned to caller


def _truncate(s: str, limit: int = _MAX_OUTPUT_BYTES) -> tuple[str, bool]:
    if len(s) <= limit:
        return s, False
    return s[:limit] + "\n...[truncated]", True


def _build_argv(command: str, shell: str) -> list[str]:
    s = (shell or "").lower().strip()
    if s in ("powershell", "pwsh", "ps"):
        exe = "pwsh" if s == "pwsh" else "powershell"
        return [exe, "-NoProfile", "-NonInteractive", "-Command", command]
    if s == "cmd":
        return ["cmd", "/c", command]
    if s == "bash":
        return ["bash", "-lc", command]
    raise ValueError(f"unsupported shell {shell!r}; choose powershell|cmd|bash|pwsh")


def execute_command(
    command: str,
    shell: str = "powershell",
    cwd: str | None = None,
    timeout_sec: int = 60,
    env_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    if not command or not command.strip():
        raise ValueError("command is required")

    timeout_sec = max(1, min(int(timeout_sec or 60), 600))
    work_dir = str(Path(cwd).expanduser().resolve()) if cwd else None

    env = os.environ.copy()
    if env_overrides:
        env.update({str(k): str(v) for k, v in env_overrides.items()})

    argv = _build_argv(command, shell)
    log.info("execute_command shell=%s cwd=%s cmd=%r", shell, work_dir, command[:300])

    started = time.time()
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            cwd=work_dir,
            env=env,
            shell=False,
        )
        duration = time.time() - started
        stdout, out_truncated = _truncate(proc.stdout or "")
        stderr, err_truncated = _truncate(proc.stderr or "")
        log.info("execute_command done exit=%d duration=%.2fs", proc.returncode, duration)
        return {
            "command": command,
            "shell": shell,
            "cwd": work_dir,
            "exit_code": proc.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "stdout_truncated": out_truncated,
            "stderr_truncated": err_truncated,
            "duration_sec": round(duration, 3),
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        duration = time.time() - started
        stdout, out_truncated = _truncate(exc.stdout.decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or ""))
        stderr, err_truncated = _truncate(exc.stderr.decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or ""))
        log.warning("execute_command timed out after %.2fs", duration)
        return {
            "command": command,
            "shell": shell,
            "cwd": work_dir,
            "exit_code": None,
            "stdout": stdout,
            "stderr": stderr,
            "stdout_truncated": out_truncated,
            "stderr_truncated": err_truncated,
            "duration_sec": round(duration, 3),
            "timed_out": True,
            "error": f"timeout after {timeout_sec}s",
        }
    except FileNotFoundError as exc:
        log.warning("shell binary missing: %s", exc)
        return {
            "command": command,
            "shell": shell,
            "exit_code": None,
            "stdout": "",
            "stderr": "",
            "timed_out": False,
            "error": f"shell binary not found for {shell!r}: {exc}",
        }
    except Exception as exc:  # noqa: BLE001
        log.exception("execute_command crashed: %s", exc)
        return {
            "command": command,
            "shell": shell,
            "exit_code": None,
            "stdout": "",
            "stderr": "",
            "timed_out": False,
            "error": f"{type(exc).__name__}: {exc}",
        }


def get_environment(name: str | None = None) -> dict[str, Any]:
    if name:
        return {"name": name, "value": os.environ.get(name)}
    return {"variables": dict(os.environ)}