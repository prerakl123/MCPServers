"""code_interpreter MCP tool.

Spawns ``python -I sandbox/runner.py`` as a subprocess, pipes user code over
stdin, returns the runner's JSON envelope.

Why subprocess and not exec() in-process?
- A crash inside user code can corrupt module-level matplotlib state, leak
  open figures, or trigger ``sys.exit`` on the server itself.
- The runner sets POSIX rlimits (no-op on Windows, where parent-side timeout
  is the only floor).
- Network is allowed per user decision; the venv's installed packages are
  the only attack surface.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from ._logging import get_logger

log = get_logger("code_interpreter")

_SERVER_ROOT = Path(__file__).resolve().parents[1]
_RUNNER = _SERVER_ROOT / "sandbox" / "runner.py"

# Defaults; the model can override via tool args.
DEFAULT_TIMEOUT_S = 20
MAX_TIMEOUT_S = 60


def _python_executable() -> str:
    # If the MCP server itself was launched from a venv, reuse that python so
    # the user's code sees the same site-packages (sympy / numpy / etc.).
    return sys.executable or "python"


def run(code: str, timeout_s: int | None = None) -> dict[str, Any]:
    """Execute ``code`` in the sandbox subprocess and return the envelope."""
    if not isinstance(code, str) or not code.strip():
        return _error("code must be a non-empty string", error_type="ArgumentError")

    requested = int(timeout_s) if timeout_s else DEFAULT_TIMEOUT_S
    requested = max(1, min(requested, MAX_TIMEOUT_S))

    cmd = [_python_executable(), "-I", str(_RUNNER)]
    log.info(
        "code_interpreter → spawn",
        extra=None,
    )
    log.info(
        "code_interpreter spawn cmd=%s timeout_s=%s code_chars=%d",
        cmd, requested, len(code),
    )

    try:
        proc = subprocess.run(
            cmd,
            input=code,
            capture_output=True,
            text=True,
            timeout=requested,
            check=False,
            cwd=str(_SERVER_ROOT),
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
    except subprocess.TimeoutExpired as exc:
        log.warning("code_interpreter timeout after %ds", requested)
        return _error(
            f"sandbox exceeded {requested}s timeout",
            error_type="Timeout",
            stdout=(exc.stdout or b"").decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or ""),
            stderr=(exc.stderr or b"").decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or ""),
            duration_ms=requested * 1000,
        )
    except OSError as exc:
        log.error("code_interpreter spawn failed: %s", exc)
        return _error(f"failed to spawn sandbox: {exc}", error_type="SpawnError")

    raw = (proc.stdout or "").strip()
    if not raw:
        log.error(
            "code_interpreter produced empty envelope. rc=%s stderr=%s",
            proc.returncode, (proc.stderr or "")[:400],
        )
        return _error(
            "sandbox produced no output",
            error_type="EmptyEnvelope",
            stderr=proc.stderr or "",
        )

    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError as exc:
        log.error("code_interpreter envelope parse failed: %s; raw=%s", exc, raw[:400])
        return _error(
            f"could not parse sandbox envelope: {exc}",
            error_type="EnvelopeParseError",
            stdout=raw[:1000],
            stderr=proc.stderr or "",
        )

    log.info(
        "code_interpreter → done status=%s duration_ms=%s artifacts=%d",
        envelope.get("status"),
        envelope.get("duration_ms"),
        len(envelope.get("artifacts") or []),
    )
    return envelope


def _error(message: str, *, error_type: str, **extra) -> dict[str, Any]:
    return {
        "status": "error",
        "error": {"type": error_type, "message": message, "traceback": ""},
        "stdout": extra.get("stdout", ""),
        "stderr": extra.get("stderr", ""),
        "artifacts": [],
        "duration_ms": extra.get("duration_ms", 0),
    }


# MCP-facing schema. Mirrors what we register in main.py.
INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "code": {
            "type": "string",
            "description": "Python source to execute. The sandbox pre-imports numpy as np, pandas as pd, sympy (also as sp), and matplotlib.pyplot as plt. Open figures are auto-saved as PNG artifacts. Use ARTIFACT_DIR to write your own files.",
        },
        "timeout_s": {
            "type": "integer",
            "minimum": 1,
            "maximum": MAX_TIMEOUT_S,
            "description": f"Per-call timeout in seconds. Default {DEFAULT_TIMEOUT_S}, max {MAX_TIMEOUT_S}.",
        },
    },
    "required": ["code"],
    "additionalProperties": False,
}

DESCRIPTION = (
    "Run Python in a sandboxed subprocess (sympy, numpy, pandas, matplotlib pre-imported). "
    "Use this to verify arithmetic, derive answer keys symbolically, sanity-check distractors, "
    "or generate intermediate computations. Output is the JSON envelope from the runner: "
    "stdout, stderr, generated artifact paths, and any error info. Network access is permitted; "
    "filesystem writes outside ARTIFACT_DIR are discouraged."
)
