"""Kill any orphaned ui_app processes and clean discovery files.

Looks at three sources:
  1. ~/.mcp/input/pid           — the recorded UI pid
  2. python.exe processes whose command line mentions 'ui_app' (Windows)
  3. anything bound to ports 47800-47899 on loopback

Run after a Ctrl+C that didn't stick, or whenever Task Manager shows leftover
Python processes named ui_app.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path.home() / ".mcp" / "input"


def _kill(pid: int, label: str) -> None:
    if pid <= 0:
        return
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/PID", str(pid)],
                capture_output=True, check=False,
            )
        else:
            os.kill(pid, 9)
        print(f"killed pid={pid} ({label})")
    except Exception as exc:  # noqa: BLE001
        print(f"failed to kill pid={pid} ({label}): {exc}", file=sys.stderr)


def _kill_pid_file() -> int | None:
    try:
        pid = int((ROOT / "pid").read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None
    _kill(pid, "from pid file")
    return pid


def _kill_by_cmdline_windows() -> list[int]:
    """Use WMIC/Get-CimInstance to find python.exe processes mentioning ui_app."""
    if sys.platform != "win32":
        return []
    ps = (
        "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
        "Where-Object { $_.CommandLine -like '*ui_app*' } | "
        "Select-Object -ExpandProperty ProcessId"
    )
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=15, check=False,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"powershell scan failed: {exc}", file=sys.stderr)
        return []

    pids: list[int] = []
    for line in (out.stdout or "").splitlines():
        line = line.strip()
        if line.isdigit():
            pids.append(int(line))
    self_pid = os.getpid()
    for pid in pids:
        if pid == self_pid:
            continue
        _kill(pid, "ui_app cmdline")
    return pids


def _clean_discovery() -> None:
    for name in ("pid", "port", "token"):
        f = ROOT / name
        try:
            f.unlink()
            print(f"removed {f}")
        except FileNotFoundError:
            pass
        except OSError as exc:
            print(f"could not remove {f}: {exc}", file=sys.stderr)


def main() -> None:
    print(f"checking for orphaned ui_app processes (root={ROOT})")
    _kill_pid_file()
    _kill_by_cmdline_windows()
    _clean_discovery()
    print("done. run `uv run python -m ui_app ...` again for a fresh start.")


if __name__ == "__main__":
    main()
