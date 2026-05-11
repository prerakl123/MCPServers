"""File grep + file find — Python regex over filesystem."""
from __future__ import annotations

import fnmatch
import os
import re
from pathlib import Path
from typing import Any

from ._logging import get_logger

log = get_logger("file_search")

_BINARY_EXTS = {
    ".exe", ".dll", ".so", ".dylib", ".bin", ".obj", ".o", ".a",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".tiff",
    ".pdf", ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar",
    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".mkv",
    ".pyc", ".pyo", ".class",
    ".db", ".sqlite", ".sqlite3",
}

_MAX_FILE_BYTES = 5_000_000  # skip files larger than 5 MB


def _looks_binary(path: Path) -> bool:
    if path.suffix.lower() in _BINARY_EXTS:
        return True
    try:
        with path.open("rb") as f:
            chunk = f.read(2048)
        return b"\x00" in chunk
    except Exception:
        return True


def file_grep(
    pattern: str,
    path: str,
    glob: str = "*",
    regex: bool = True,
    case_sensitive: bool = False,
    max_results: int = 200,
    context_lines: int = 0,
    max_file_bytes: int = _MAX_FILE_BYTES,
) -> dict[str, Any]:
    """Search file contents for `pattern`, returning matches with line numbers."""
    if not pattern:
        raise ValueError("pattern is required")
    base = Path(path).expanduser().resolve()
    if not base.exists():
        return {"error": f"path not found: {base}", "matches": []}

    flags = 0 if case_sensitive else re.IGNORECASE
    if regex:
        try:
            rx = re.compile(pattern, flags)
        except re.error as exc:
            return {"error": f"invalid regex: {exc}", "matches": []}
    else:
        rx = re.compile(re.escape(pattern), flags)

    matches: list[dict[str, Any]] = []
    files_scanned = 0
    files_matched: set[str] = set()

    if base.is_file():
        candidates = [base]
    else:
        candidates = list(base.rglob(glob))

    for fp in candidates:
        if len(matches) >= max_results:
            break
        if not fp.is_file():
            continue
        try:
            if fp.stat().st_size > max_file_bytes:
                continue
        except OSError:
            continue
        if _looks_binary(fp):
            continue
        files_scanned += 1
        try:
            with fp.open("r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except Exception as exc:
            log.debug("read failed %s: %s", fp, exc)
            continue

        for i, line in enumerate(lines):
            if rx.search(line):
                hit: dict[str, Any] = {
                    "file": str(fp),
                    "line_no": i + 1,
                    "line": line.rstrip("\n"),
                }
                if context_lines > 0:
                    lo = max(0, i - context_lines)
                    hi = min(len(lines), i + context_lines + 1)
                    hit["context"] = [
                        {"line_no": lo + k + 1, "line": lines[lo + k].rstrip("\n")}
                        for k in range(hi - lo)
                    ]
                matches.append(hit)
                files_matched.add(str(fp))
                if len(matches) >= max_results:
                    break

    log.info("file_grep pattern=%r path=%s matches=%d files=%d",
             pattern, base, len(matches), files_scanned)

    return {
        "pattern": pattern,
        "path": str(base),
        "match_count": len(matches),
        "files_scanned": files_scanned,
        "files_matched": len(files_matched),
        "truncated": len(matches) >= max_results,
        "matches": matches,
    }


def file_find(
    name_pattern: str,
    path: str,
    recursive: bool = True,
    max_results: int = 500,
    include_dirs: bool = False,
) -> dict[str, Any]:
    """Find files whose names match a glob pattern (e.g. '*.py', 'README*')."""
    if not name_pattern:
        raise ValueError("name_pattern is required")
    base = Path(path).expanduser().resolve()
    if not base.exists():
        return {"error": f"path not found: {base}", "results": []}

    matches: list[dict[str, Any]] = []
    walker: Any
    if recursive:
        walker = os.walk(base)
        for root, dirs, files in walker:
            entries = files + (dirs if include_dirs else [])
            for name in entries:
                if fnmatch.fnmatch(name, name_pattern):
                    full = Path(root) / name
                    try:
                        st = full.stat()
                        matches.append({
                            "path": str(full),
                            "name": name,
                            "type": "dir" if full.is_dir() else "file",
                            "size": st.st_size,
                            "mtime": st.st_mtime,
                        })
                    except OSError:
                        continue
                    if len(matches) >= max_results:
                        break
            if len(matches) >= max_results:
                break
    else:
        try:
            for child in base.iterdir():
                if not include_dirs and child.is_dir():
                    continue
                if fnmatch.fnmatch(child.name, name_pattern):
                    st = child.stat()
                    matches.append({
                        "path": str(child),
                        "name": child.name,
                        "type": "dir" if child.is_dir() else "file",
                        "size": st.st_size,
                        "mtime": st.st_mtime,
                    })
                    if len(matches) >= max_results:
                        break
        except OSError as exc:
            return {"error": str(exc), "results": []}

    log.info("file_find pattern=%r path=%s results=%d", name_pattern, base, len(matches))
    return {
        "pattern": name_pattern,
        "path": str(base),
        "result_count": len(matches),
        "truncated": len(matches) >= max_results,
        "results": matches,
    }