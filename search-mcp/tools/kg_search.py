"""Read-only FTS5 search against the kg-mcp memory store.

Cross-server coupling is by file path only — kg-mcp owns writes.
DB lives at ~/.mcp/kg/memories.db.
"""
from __future__ import annotations

import json
import sqlite3
import urllib.parse
from pathlib import Path
from typing import Any

from ._logging import get_logger

log = get_logger("kg_search")

_KG_DB = Path.home() / ".mcp" / "kg" / "memories.db"


def search_memories(
    query_text: str,
    memory_type: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    if not query_text:
        raise ValueError("query_text is required")
    if not _KG_DB.exists():
        return {
            "error": f"kg-mcp store not found at {_KG_DB}; start kg-mcp once to create it",
            "results": [],
        }
    limit = max(1, min(int(limit or 10), 100))

    uri = f"file:{urllib.parse.quote(str(_KG_DB))}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=10.0)
    try:
        cur = conn.cursor()
        if memory_type:
            cur.execute(
                """
                SELECT m.id, m.content, m.type, m.tags, m.metadata,
                       m.created_at, m.updated_at, bm25(memories_fts) AS rank
                FROM memories_fts
                JOIN memories m ON m.id = memories_fts.rowid
                WHERE memories_fts MATCH ? AND m.type = ?
                ORDER BY rank LIMIT ?
                """,
                (query_text, memory_type, limit),
            )
        else:
            cur.execute(
                """
                SELECT m.id, m.content, m.type, m.tags, m.metadata,
                       m.created_at, m.updated_at, bm25(memories_fts) AS rank
                FROM memories_fts
                JOIN memories m ON m.id = memories_fts.rowid
                WHERE memories_fts MATCH ?
                ORDER BY rank LIMIT ?
                """,
                (query_text, limit),
            )
        rows = cur.fetchall()
        results = []
        for r in rows:
            results.append({
                "id": r[0],
                "content": r[1],
                "type": r[2],
                "tags": json.loads(r[3]) if r[3] else [],
                "metadata": json.loads(r[4]) if r[4] else {},
                "created_at": r[5],
                "updated_at": r[6],
                "rank": float(r[7]),
            })
        log.info("kg search query=%r type=%s results=%d", query_text, memory_type, len(results))
        return {
            "query": query_text,
            "type": memory_type,
            "result_count": len(results),
            "results": results,
        }
    except sqlite3.Error as exc:
        log.warning("kg search error: %s", exc)
        return {"error": f"{type(exc).__name__}: {exc}", "results": []}
    finally:
        conn.close()