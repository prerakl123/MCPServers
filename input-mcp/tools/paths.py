"""Well-known paths for input-mcp coordination files.

These live under ~/.mcp/input/ so any local consumer can discover them:

  token  — bearer token for HTTP API
  port   — UI service port
  pid    — UI app process id (for liveness/cleanup)
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path.home() / ".mcp" / "input"
TOKEN_FILE = ROOT / "token"
PORT_FILE = ROOT / "port"
PID_FILE = ROOT / "pid"


def ensure_root() -> Path:
    ROOT.mkdir(parents=True, exist_ok=True)
    return ROOT


def read_token() -> str | None:
    try:
        return TOKEN_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def read_port() -> int | None:
    try:
        return int(PORT_FILE.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def read_pid() -> int | None:
    try:
        return int(PID_FILE.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None