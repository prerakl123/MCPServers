"""Semantic vector search using sqlite-vec + fastembed.

Index files live at ~/.mcp/search/indexes/<name>.db.
Each index stores raw text + metadata in a `documents` table and dense vectors
in a `vec_index` virtual table. Embeddings are produced by fastembed
(default model: BAAI/bge-small-en-v1.5, 384-dim, ONNX, no torch dep).
"""
from __future__ import annotations

import json
import sqlite3
import struct
from pathlib import Path
from typing import Any

import sqlite_vec  # type: ignore

from ._logging import get_logger

log = get_logger("semantic")

_INDEX_DIR = Path.home() / ".mcp" / "search" / "indexes"
_DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"
_EMBED_DIM = 384

# Cache the model — first load downloads the ONNX file (~30 MB).
_model_cache: dict[str, Any] = {}


def _get_model(model_name: str = _DEFAULT_MODEL):
    if model_name not in _model_cache:
        log.info("loading fastembed model %s (first call may download)", model_name)
        from fastembed import TextEmbedding
        _model_cache[model_name] = TextEmbedding(model_name=model_name)
    return _model_cache[model_name]


def _embed(texts: list[str], model_name: str = _DEFAULT_MODEL) -> list[list[float]]:
    model = _get_model(model_name)
    return [list(map(float, vec)) for vec in model.embed(texts)]


def _vec_to_bytes(vec: list[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def _index_path(name: str) -> Path:
    safe = "".join(c for c in name if c.isalnum() or c in "_-").strip("_-")
    if not safe:
        raise ValueError(f"invalid index name {name!r}")
    _INDEX_DIR.mkdir(parents=True, exist_ok=True)
    return _INDEX_DIR / f"{safe}.db"


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=10.0)
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        f"""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            external_id TEXT,
            text TEXT NOT NULL,
            metadata TEXT
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS vec_index USING vec0(
            embedding float[{_EMBED_DIM}]
        );
        """
    )


def index_create(
    name: str,
    items: list[dict[str, Any]],
    replace: bool = False,
    model: str = _DEFAULT_MODEL,
) -> dict[str, Any]:
    """Build (or append to) a semantic index.

    items: [{id?: str, text: str, metadata?: dict}, ...]
    """
    if not items:
        raise ValueError("items must be a non-empty list")
    db_path = _index_path(name)
    if replace and db_path.exists():
        db_path.unlink()
        log.info("replaced existing index %s", db_path)

    conn = _connect(db_path)
    try:
        _ensure_schema(conn)
        texts = [str(item.get("text", "")).strip() for item in items]
        if any(not t for t in texts):
            raise ValueError("each item must have non-empty 'text'")

        log.info("embedding %d items for index %s", len(texts), name)
        vectors = _embed(texts, model_name=model)

        cur = conn.cursor()
        added = 0
        for item, vec in zip(items, vectors):
            ext_id = item.get("id")
            md = json.dumps(item.get("metadata") or {}, default=str)
            cur.execute(
                "INSERT INTO documents(external_id, text, metadata) VALUES (?,?,?)",
                (ext_id, item["text"], md),
            )
            doc_rowid = cur.lastrowid
            cur.execute(
                "INSERT INTO vec_index(rowid, embedding) VALUES (?, ?)",
                (doc_rowid, _vec_to_bytes(vec)),
            )
            added += 1
        conn.commit()
        log.info("index %s: added %d items", name, added)
        return {
            "index": name,
            "db_path": str(db_path),
            "added": added,
            "model": model,
            "embedding_dim": _EMBED_DIM,
        }
    finally:
        conn.close()


def search(
    name: str,
    query_text: str,
    top_k: int = 5,
    model: str = _DEFAULT_MODEL,
) -> dict[str, Any]:
    """Semantic search against an existing index. Returns top_k by cosine distance."""
    if not query_text:
        raise ValueError("query_text is required")
    db_path = _index_path(name)
    if not db_path.exists():
        return {"error": f"index {name!r} not found at {db_path}", "results": []}

    top_k = max(1, min(int(top_k or 5), 50))
    qvec = _embed([query_text], model_name=model)[0]

    conn = _connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT d.id, d.external_id, d.text, d.metadata, v.distance
            FROM vec_index v
            JOIN documents d ON d.id = v.rowid
            WHERE v.embedding MATCH ? AND k = ?
            ORDER BY v.distance ASC
            """,
            (_vec_to_bytes(qvec), top_k),
        )
        rows = cur.fetchall()
        results = []
        for row in rows:
            try:
                md = json.loads(row[3]) if row[3] else {}
            except Exception:
                md = {}
            results.append({
                "id": row[0],
                "external_id": row[1],
                "text": row[2],
                "metadata": md,
                "distance": float(row[4]),
                "score": 1.0 / (1.0 + float(row[4])),
            })
        log.info("semantic search index=%s query=%r results=%d", name, query_text, len(results))
        return {
            "index": name,
            "query": query_text,
            "result_count": len(results),
            "results": results,
        }
    finally:
        conn.close()


def list_indexes() -> dict[str, Any]:
    """List built semantic indexes."""
    if not _INDEX_DIR.exists():
        return {"index_dir": str(_INDEX_DIR), "indexes": []}
    items = []
    for f in sorted(_INDEX_DIR.glob("*.db")):
        try:
            st = f.stat()
            items.append({"name": f.stem, "path": str(f), "size_bytes": st.st_size})
        except OSError:
            continue
    return {"index_dir": str(_INDEX_DIR), "indexes": items}


def delete_index(name: str) -> dict[str, Any]:
    """Delete an index file."""
    db_path = _index_path(name)
    if not db_path.exists():
        return {"error": f"index {name!r} not found", "deleted": False}
    db_path.unlink()
    log.info("deleted index %s", db_path)
    return {"name": name, "deleted": True, "path": str(db_path)}