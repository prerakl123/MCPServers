"""Child process: executes user-supplied Python under resource limits.

Invoked by ``tools.code_interpreter`` via ``python -I sandbox/runner.py``.
The parent passes user code over stdin (UTF-8) and reads a JSON envelope
from stdout when execution completes:

    {
      "status": "ok" | "error",
      "stdout": str,
      "stderr": str,
      "result": <repr of the last expression, if any>,
      "artifacts": [{"path": "...", "kind": "image/png"}],
      "duration_ms": int,
      "error": {"type": "...", "message": "...", "traceback": "..."}  # only on error
    }

Artifacts (matplotlib figures, written files) live under
``logs/sandbox/<run_id>/`` and the parent surfaces their paths.

Resource limits applied here, not at subprocess.run time, because
``resource`` is POSIX-only. On Windows, parent-side ``timeout`` is the only
floor and we accept that.
"""
from __future__ import annotations

import builtins
import io
import json
import os
import sys
import time
import traceback
import uuid
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

MAX_OUTPUT_CHARS = 4096  # mirrors the 4 KB cap in the plan


def _try_set_rlimits(memory_mb: int = 1024, cpu_seconds: int = 30) -> None:
    """Best-effort POSIX resource limits. No-op on Windows."""
    try:
        import resource  # type: ignore
    except ImportError:
        return  # Windows
    try:
        resource.setrlimit(
            resource.RLIMIT_AS,
            (memory_mb * 1024 * 1024, memory_mb * 1024 * 1024),
        )
    except (ValueError, OSError):
        pass
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
    except (ValueError, OSError):
        pass


def _truncate(text: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    head = MAX_OUTPUT_CHARS - 80
    return text[:head] + f"\n... [truncated {len(text) - head} chars] ..."


def _make_artifact_dir() -> Path:
    root = Path(__file__).resolve().parents[1] / "logs" / "sandbox"
    run_id = uuid.uuid4().hex[:12]
    out = root / run_id
    out.mkdir(parents=True, exist_ok=True)
    return out


def _detect_artifacts(artifact_dir: Path) -> list[dict]:
    items: list[dict] = []
    if not artifact_dir.exists():
        return items
    for p in sorted(artifact_dir.iterdir()):
        kind = "application/octet-stream"
        suffix = p.suffix.lower()
        if suffix in (".png",):
            kind = "image/png"
        elif suffix in (".svg",):
            kind = "image/svg+xml"
        elif suffix in (".json",):
            kind = "application/json"
        elif suffix in (".csv",):
            kind = "text/csv"
        elif suffix in (".txt", ".md"):
            kind = "text/plain"
        items.append({"path": str(p), "kind": kind, "size": p.stat().st_size})
    return items


def _build_namespace(artifact_dir: Path) -> dict:
    """The execution namespace pre-populates safe-by-default tools.

    matplotlib uses the non-interactive Agg backend so figures save to disk
    without spawning a GUI thread. ``ARTIFACT_DIR`` is exposed so user code
    can drop arbitrary files for the parent to surface.
    """
    import matplotlib  # type: ignore
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # type: ignore
    import numpy as np  # type: ignore
    import pandas as pd  # type: ignore
    import sympy  # type: ignore

    ns: dict = {
        "__name__": "__main__",
        "__builtins__": builtins.__dict__,
        "ARTIFACT_DIR": str(artifact_dir),
        "np": np,
        "pd": pd,
        "sympy": sympy,
        "sp": sympy,
        "plt": plt,
        "matplotlib": matplotlib,
    }
    return ns


def main() -> int:
    _try_set_rlimits()
    code = sys.stdin.read()
    artifact_dir = _make_artifact_dir()

    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    started = time.time()

    envelope: dict
    try:
        ns = _build_namespace(artifact_dir)
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            # Compile in 'exec' mode so multi-statement code works. We don't
            # try to capture a "last expression" result because exec() doesn't
            # give us one for free; users can `print(...)` if they want output.
            compiled = compile(code, "<sandbox>", "exec")
            exec(compiled, ns)
        # Flush matplotlib figures the user may have left open.
        try:
            import matplotlib.pyplot as plt  # type: ignore
            for i, num in enumerate(plt.get_fignums()):
                fig = plt.figure(num)
                out_path = artifact_dir / f"figure_{i + 1}.png"
                fig.savefig(out_path, dpi=120, bbox_inches="tight")
                plt.close(fig)
        except Exception as fig_err:  # pragma: no cover - never crash flushing
            stderr_buf.write(f"\n[sandbox] figure flush failed: {fig_err}\n")
        envelope = {
            "status": "ok",
            "stdout": _truncate(stdout_buf.getvalue()),
            "stderr": _truncate(stderr_buf.getvalue()),
            "artifacts": _detect_artifacts(artifact_dir),
            "duration_ms": int((time.time() - started) * 1000),
        }
    except SystemExit as exc:
        envelope = {
            "status": "error",
            "stdout": _truncate(stdout_buf.getvalue()),
            "stderr": _truncate(stderr_buf.getvalue()),
            "duration_ms": int((time.time() - started) * 1000),
            "error": {
                "type": "SystemExit",
                "message": f"sys.exit({exc.code!r})",
                "traceback": "",
            },
        }
    except BaseException as exc:  # noqa: BLE001 - we want to capture *anything*
        envelope = {
            "status": "error",
            "stdout": _truncate(stdout_buf.getvalue()),
            "stderr": _truncate(stderr_buf.getvalue()),
            "duration_ms": int((time.time() - started) * 1000),
            "error": {
                "type": exc.__class__.__name__,
                "message": str(exc),
                "traceback": _truncate(traceback.format_exc()),
            },
        }

    sys.stdout.write(json.dumps(envelope, ensure_ascii=False))
    sys.stdout.flush()
    return 0 if envelope["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
