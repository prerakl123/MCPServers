"""Memory CRUD + relations + FTS5 search."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from . import schema
from ._logging import get_logger

log = get_logger("store")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    if d.get("tags"):
        try:
            d["tags"] = json.loads(d["tags"])
        except Exception:
            d["tags"] = []
    else:
        d["tags"] = []
    if d.get("metadata"):
        try:
            d["metadata"] = json.loads(d["metadata"])
        except Exception:
            d["metadata"] = {}
    else:
        d["metadata"] = {}
    return d


def save_memory(
    content: str,
    memory_type: str | None = None,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not content or not content.strip():
        raise ValueError("content is required")
    now = _now_iso()
    tags_json = json.dumps(list(tags or []))
    md_json = json.dumps(dict(metadata or {}), default=str)

    conn = schema.connect()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO memories(content, type, tags, metadata, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?)",
            (content, memory_type, tags_json, md_json, now, now),
        )
        conn.commit()
        new_id = cur.lastrowid
        log.info("save_memory id=%s type=%s tags=%d", new_id, memory_type, len(tags or []))
        return {
            "id": new_id,
            "created_at": now,
            "updated_at": now,
            "content": content,
            "type": memory_type,
            "tags": list(tags or []),
            "metadata": dict(metadata or {}),
        }
    finally:
        conn.close()


def get_memory(memory_id: int) -> dict[str, Any]:
    conn = schema.connect()
    try:
        row = conn.execute("SELECT * FROM memories WHERE id = ?", (int(memory_id),)).fetchone()
        if not row:
            return {"error": f"memory id={memory_id} not found"}
        return _row_to_dict(row)
    finally:
        conn.close()


def list_memories(
    limit: int = 50,
    offset: int = 0,
    memory_type: str | None = None,
) -> dict[str, Any]:
    limit = max(1, min(int(limit or 50), 500))
    offset = max(0, int(offset or 0))

    conn = schema.connect()
    try:
        if memory_type:
            rows = conn.execute(
                "SELECT * FROM memories WHERE type = ? ORDER BY id DESC LIMIT ? OFFSET ?",
                (memory_type, limit, offset),
            ).fetchall()
            total = conn.execute(
                "SELECT COUNT(*) FROM memories WHERE type = ?", (memory_type,)
            ).fetchone()[0]
        else:
            rows = conn.execute(
                "SELECT * FROM memories ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            total = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "type": memory_type,
            "results": [_row_to_dict(r) for r in rows],
        }
    finally:
        conn.close()


def search_memories(
    query_text: str,
    memory_type: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    if not query_text:
        raise ValueError("query_text is required")
    limit = max(1, min(int(limit or 10), 100))

    conn = schema.connect()
    try:
        if memory_type:
            rows = conn.execute(
                """
                SELECT m.*, bm25(memories_fts) AS rank
                FROM memories_fts
                JOIN memories m ON m.id = memories_fts.rowid
                WHERE memories_fts MATCH ? AND m.type = ?
                ORDER BY rank LIMIT ?
                """,
                (query_text, memory_type, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT m.*, bm25(memories_fts) AS rank
                FROM memories_fts
                JOIN memories m ON m.id = memories_fts.rowid
                WHERE memories_fts MATCH ?
                ORDER BY rank LIMIT ?
                """,
                (query_text, limit),
            ).fetchall()
        results = []
        for row in rows:
            d = _row_to_dict(row)
            d["rank"] = float(row["rank"])
            results.append(d)
        log.info("search_memories query=%r type=%s results=%d",
                 query_text, memory_type, len(results))
        return {
            "query": query_text,
            "type": memory_type,
            "result_count": len(results),
            "results": results,
        }
    except sqlite3.Error as exc:
        log.warning("search_memories error: %s", exc)
        return {"error": f"{type(exc).__name__}: {exc}", "results": []}
    finally:
        conn.close()


def update_memory(
    memory_id: int,
    content: str | None = None,
    memory_type: str | None = None,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fields: list[str] = []
    params: list[Any] = []
    if content is not None:
        fields.append("content = ?")
        params.append(content)
    if memory_type is not None:
        fields.append("type = ?")
        params.append(memory_type)
    if tags is not None:
        fields.append("tags = ?")
        params.append(json.dumps(list(tags)))
    if metadata is not None:
        fields.append("metadata = ?")
        params.append(json.dumps(dict(metadata), default=str))
    if not fields:
        return {"error": "no fields provided to update", "updated": False}

    fields.append("updated_at = ?")
    now = _now_iso()
    params.append(now)
    params.append(int(memory_id))

    conn = schema.connect()
    try:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE memories SET {', '.join(fields)} WHERE id = ?",
            params,
        )
        conn.commit()
        if cur.rowcount == 0:
            return {"error": f"memory id={memory_id} not found", "updated": False}
        log.info("update_memory id=%s fields=%s", memory_id, len(fields) - 1)
        row = conn.execute("SELECT * FROM memories WHERE id = ?", (int(memory_id),)).fetchone()
        return _row_to_dict(row) if row else {"updated": True, "id": memory_id}
    finally:
        conn.close()


def delete_memory(memory_id: int) -> dict[str, Any]:
    conn = schema.connect()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM memories WHERE id = ?", (int(memory_id),))
        conn.commit()
        deleted = cur.rowcount > 0
        log.warning("delete_memory id=%s deleted=%s", memory_id, deleted)
        if not deleted:
            return {"error": f"memory id={memory_id} not found", "deleted": False}
        return {"id": memory_id, "deleted": True}
    finally:
        conn.close()


def link_memories(from_id: int, to_id: int, relation_type: str) -> dict[str, Any]:
    if not relation_type:
        raise ValueError("relation_type is required")
    now = _now_iso()
    conn = schema.connect()
    try:
        # ensure both endpoints exist
        present = conn.execute(
            "SELECT id FROM memories WHERE id IN (?, ?)", (int(from_id), int(to_id))
        ).fetchall()
        ids = {row["id"] for row in present}
        if int(from_id) not in ids or int(to_id) not in ids:
            return {
                "error": f"one or both memories not found: {from_id}, {to_id}",
                "linked": False,
            }

        try:
            conn.execute(
                "INSERT INTO relations(from_id, to_id, relation_type, created_at) "
                "VALUES (?,?,?,?)",
                (int(from_id), int(to_id), relation_type, now),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            return {"linked": False, "error": "relation already exists"}

        log.info("link_memories %s -> %s [%s]", from_id, to_id, relation_type)
        return {
            "from_id": int(from_id),
            "to_id": int(to_id),
            "relation_type": relation_type,
            "created_at": now,
            "linked": True,
        }
    finally:
        conn.close()


def unlink_memories(from_id: int, to_id: int, relation_type: str) -> dict[str, Any]:
    conn = schema.connect()
    try:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM relations WHERE from_id = ? AND to_id = ? AND relation_type = ?",
            (int(from_id), int(to_id), relation_type),
        )
        conn.commit()
        return {"unlinked": cur.rowcount > 0, "from_id": from_id, "to_id": to_id,
                "relation_type": relation_type}
    finally:
        conn.close()


def get_related(
    memory_id: int,
    depth: int = 1,
    relation_type: str | None = None,
) -> dict[str, Any]:
    depth = max(1, min(int(depth or 1), 5))
    conn = schema.connect()
    try:
        seen: set[int] = {int(memory_id)}
        frontier = {int(memory_id)}
        edges: list[dict[str, Any]] = []
        nodes: dict[int, dict[str, Any]] = {}

        # seed node
        seed_row = conn.execute("SELECT * FROM memories WHERE id = ?", (int(memory_id),)).fetchone()
        if not seed_row:
            return {"error": f"memory id={memory_id} not found", "nodes": [], "edges": []}
        nodes[int(memory_id)] = _row_to_dict(seed_row)

        for _ in range(depth):
            if not frontier:
                break
            placeholders = ",".join("?" * len(frontier))
            params: list[Any] = list(frontier)
            sql = (
                f"SELECT from_id, to_id, relation_type FROM relations "
                f"WHERE (from_id IN ({placeholders}) OR to_id IN ({placeholders}))"
            )
            params = params + params
            if relation_type:
                sql += " AND relation_type = ?"
                params.append(relation_type)
            rels = conn.execute(sql, params).fetchall()

            next_frontier: set[int] = set()
            for r in rels:
                edges.append({
                    "from_id": r["from_id"],
                    "to_id": r["to_id"],
                    "relation_type": r["relation_type"],
                })
                for nid in (r["from_id"], r["to_id"]):
                    if nid not in seen:
                        next_frontier.add(nid)
                        seen.add(nid)
            if next_frontier:
                rows = conn.execute(
                    f"SELECT * FROM memories WHERE id IN ({','.join('?' * len(next_frontier))})",
                    list(next_frontier),
                ).fetchall()
                for row in rows:
                    nodes[row["id"]] = _row_to_dict(row)
            frontier = next_frontier

        return {
            "root_id": int(memory_id),
            "depth": depth,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "nodes": list(nodes.values()),
            "edges": edges,
        }
    finally:
        conn.close()


def stats() -> dict[str, Any]:
    conn = schema.connect()
    try:
        total = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        rels = conn.execute("SELECT COUNT(*) FROM relations").fetchone()[0]
        types = conn.execute(
            "SELECT type, COUNT(*) AS n FROM memories GROUP BY type ORDER BY n DESC"
        ).fetchall()
        return {
            "db_path": str(schema.DB_PATH),
            "total_memories": total,
            "total_relations": rels,
            "by_type": [{"type": r["type"], "count": r["n"]} for r in types],
        }
    finally:
        conn.close()