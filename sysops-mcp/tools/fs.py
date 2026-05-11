"""Filesystem operations: read, write, list, move, copy, delete, info."""
from __future__ import annotations

import base64
import fnmatch
import shutil
from pathlib import Path
from typing import Any

from ._logging import get_logger

log = get_logger("fs")

_DEFAULT_MAX_BYTES = 500_000


def _resolve(path: str) -> Path:
    if not path:
        raise ValueError("path is required")
    return Path(path).expanduser().resolve()


def _looks_binary(sample: bytes) -> bool:
    return b"\x00" in sample


def read_file(
    path: str,
    encoding: str = "utf-8",
    max_bytes: int = _DEFAULT_MAX_BYTES,
    offset: int = 0,
) -> dict[str, Any]:
    p = _resolve(path)
    if not p.exists():
        return {"error": f"file not found: {p}", "content": ""}
    if not p.is_file():
        return {"error": f"not a regular file: {p}", "content": ""}

    max_bytes = max(1, min(int(max_bytes or _DEFAULT_MAX_BYTES), 5_000_000))
    offset = max(0, int(offset or 0))

    try:
        size = p.stat().st_size
        with p.open("rb") as f:
            if offset:
                f.seek(offset)
            raw = f.read(max_bytes)
    except OSError as exc:
        return {"error": f"read failed: {exc}", "content": ""}

    truncated = (offset + len(raw)) < size
    if _looks_binary(raw[:4096]):
        log.info("read_file binary path=%s size=%d", p, size)
        return {
            "path": str(p),
            "size": size,
            "encoding": "base64",
            "binary": True,
            "truncated": truncated,
            "content": base64.b64encode(raw).decode("ascii"),
            "bytes_read": len(raw),
        }

    try:
        text = raw.decode(encoding, errors="replace")
    except LookupError:
        text = raw.decode("utf-8", errors="replace")
        encoding = "utf-8"

    log.info("read_file text path=%s size=%d truncated=%s", p, size, truncated)
    return {
        "path": str(p),
        "size": size,
        "encoding": encoding,
        "binary": False,
        "truncated": truncated,
        "content": text,
        "bytes_read": len(raw),
    }


def write_file(
    path: str,
    content: str,
    encoding: str = "utf-8",
    create_dirs: bool = True,
    overwrite: bool = True,
    append: bool = False,
) -> dict[str, Any]:
    p = _resolve(path)
    if p.exists() and not overwrite and not append:
        return {"error": f"file exists and overwrite=False: {p}", "written": False}
    if create_dirs:
        p.parent.mkdir(parents=True, exist_ok=True)

    mode = "a" if append else "w"
    with p.open(mode, encoding=encoding, newline="") as f:
        f.write(content)
    written = len(content.encode(encoding, errors="replace"))
    log.info("write_file path=%s mode=%s bytes=%d", p, mode, written)
    return {
        "path": str(p),
        "written": True,
        "bytes_written": written,
        "appended": append,
    }


def list_directory(
    path: str,
    recursive: bool = False,
    glob: str | None = None,
    include_hidden: bool = False,
    max_entries: int = 1000,
) -> dict[str, Any]:
    p = _resolve(path)
    if not p.exists():
        return {"error": f"path not found: {p}", "entries": []}
    if not p.is_dir():
        return {"error": f"not a directory: {p}", "entries": []}

    max_entries = max(1, min(int(max_entries or 1000), 10_000))
    entries: list[dict[str, Any]] = []
    truncated = False

    def _add(entry: Path) -> bool:
        if not include_hidden and entry.name.startswith("."):
            return True
        if glob and not fnmatch.fnmatch(entry.name, glob):
            return True
        try:
            st = entry.stat()
            entries.append({
                "name": entry.name,
                "path": str(entry),
                "type": "dir" if entry.is_dir() else "file",
                "size": st.st_size,
                "mtime": st.st_mtime,
            })
        except OSError:
            return True
        return len(entries) < max_entries

    if recursive:
        for root, dirs, files in p.walk() if hasattr(p, "walk") else _walk_compat(p):
            if not include_hidden:
                dirs[:] = [d for d in dirs if not d.startswith(".")]
            for name in files + dirs:
                if not _add(Path(root) / name):
                    truncated = True
                    break
            if truncated:
                break
    else:
        for child in sorted(p.iterdir()):
            if not _add(child):
                truncated = True
                break

    log.info("list_directory path=%s recursive=%s entries=%d", p, recursive, len(entries))
    return {
        "path": str(p),
        "recursive": recursive,
        "entry_count": len(entries),
        "truncated": truncated,
        "entries": entries,
    }


def _walk_compat(p: Path):
    import os
    return os.walk(str(p))


def move_file(src: str, dst: str, overwrite: bool = False) -> dict[str, Any]:
    sp = _resolve(src)
    dp = _resolve(dst)
    if not sp.exists():
        return {"error": f"source not found: {sp}", "moved": False}
    if dp.exists() and not overwrite:
        return {"error": f"destination exists and overwrite=False: {dp}", "moved": False}
    if dp.exists() and overwrite:
        if dp.is_dir():
            shutil.rmtree(dp)
        else:
            dp.unlink()
    dp.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(sp), str(dp))
    log.warning("moved %s -> %s", sp, dp)
    return {"src": str(sp), "dst": str(dp), "moved": True}


def copy_file(src: str, dst: str, overwrite: bool = False) -> dict[str, Any]:
    sp = _resolve(src)
    dp = _resolve(dst)
    if not sp.exists():
        return {"error": f"source not found: {sp}", "copied": False}
    if dp.exists() and not overwrite:
        return {"error": f"destination exists and overwrite=False: {dp}", "copied": False}
    dp.parent.mkdir(parents=True, exist_ok=True)
    if sp.is_dir():
        if dp.exists():
            shutil.rmtree(dp)
        shutil.copytree(str(sp), str(dp))
    else:
        shutil.copy2(str(sp), str(dp))
    log.info("copied %s -> %s", sp, dp)
    return {"src": str(sp), "dst": str(dp), "copied": True, "is_directory": sp.is_dir()}


def delete_path(path: str, recursive: bool = False) -> dict[str, Any]:
    p = _resolve(path)
    if not p.exists():
        return {"error": f"path not found: {p}", "deleted": False}
    log.warning("delete_path path=%s recursive=%s is_dir=%s", p, recursive, p.is_dir())
    if p.is_dir():
        if not recursive:
            return {"error": f"path is a directory; pass recursive=True to delete: {p}", "deleted": False}
        shutil.rmtree(p)
    else:
        p.unlink()
    return {"path": str(p), "deleted": True}


def create_directory(path: str, parents: bool = True, exist_ok: bool = True) -> dict[str, Any]:
    p = _resolve(path)
    p.mkdir(parents=parents, exist_ok=exist_ok)
    log.info("create_directory path=%s", p)
    return {"path": str(p), "created": True}


def file_info(path: str) -> dict[str, Any]:
    p = _resolve(path)
    if not p.exists():
        return {"path": str(p), "exists": False}
    st = p.stat()
    return {
        "path": str(p),
        "exists": True,
        "type": "dir" if p.is_dir() else ("symlink" if p.is_symlink() else "file"),
        "size": st.st_size,
        "mtime": st.st_mtime,
        "ctime": st.st_ctime,
        "is_symlink": p.is_symlink(),
        "absolute": str(p.absolute()),
    }