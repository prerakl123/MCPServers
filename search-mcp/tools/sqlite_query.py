"""Generic SQLite query tool. Read-only by default."""
from __future__ import annotations

import sqlite3
import urllib.parse
from pathlib import Path
from typing import Any

from ._logging import get_logger

log = get_logger("sqlite_query")

_MAX_ROWS = 1000


def _is_select(query: str) -> bool:
    s = query.strip().lower()
    if not s:
        return False
    # allow SELECT, WITH ... SELECT, EXPLAIN, PRAGMA
    return s.startswith(("select", "with", "explain", "pragma"))


def query(
    db_path: str,
    sql: str,
    params: list[Any] | None = None,
    read_only: bool = True,
    max_rows: int = _MAX_ROWS,
) -> dict[str, Any]:
    """Run a SQL query against a SQLite DB.

    When read_only=True, opens the DB in URI ?mode=ro and refuses non-SELECT.
    """
    if not db_path:
        raise ValueError("db_path is required")
    if not sql or not sql.strip():
        raise ValueError("sql is required")
    db = Path(db_path).expanduser().resolve()
    if not db.exists():
        return {"error": f"database not found: {db}", "rows": []}

    if read_only and not _is_select(sql):
        return {"error": "read_only=True only permits SELECT/WITH/EXPLAIN/PRAGMA", "rows": []}

    params = list(params or [])
    max_rows = max(1, min(int(max_rows or _MAX_ROWS), 10_000))

    if read_only:
        uri = f"file:{urllib.parse.quote(str(db))}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=10.0)
    else:
        conn = sqlite3.connect(str(db), timeout=10.0)

    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        if cur.description is None:
            # non-SELECT in read_only=False mode
            conn.commit()
            log.info("sqlite_query (write) db=%s rows_affected=%d", db, cur.rowcount)
            return {
                "db_path": str(db),
                "sql": sql,
                "rows_affected": cur.rowcount,
                "columns": [],
                "rows": [],
                "row_count": 0,
            }

        columns = [d[0] for d in cur.description]
        rows: list[list[Any]] = []
        truncated = False
        for i, row in enumerate(cur):
            if i >= max_rows:
                truncated = True
                break
            rows.append(list(row))
        log.info("sqlite_query db=%s rows=%d truncated=%s", db, len(rows), truncated)
        return {
            "db_path": str(db),
            "sql": sql,
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "truncated": truncated,
        }
    except sqlite3.Error as exc:
        log.warning("sqlite error: %s", exc)
        return {"error": f"{type(exc).__name__}: {exc}", "rows": []}
    finally:
        conn.close()


def list_tables(db_path: str) -> dict[str, Any]:
    """List user tables and views in a SQLite DB."""
    db = Path(db_path).expanduser().resolve()
    if not db.exists():
        return {"error": f"database not found: {db}", "tables": []}
    uri = f"file:{urllib.parse.quote(str(db))}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=10.0)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT name, type, sql FROM sqlite_master "
            "WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' "
            "ORDER BY type, name"
        )
        tables = [{"name": r[0], "type": r[1], "schema": r[2]} for r in cur.fetchall()]
        return {"db_path": str(db), "count": len(tables), "tables": tables}
    finally:
        conn.close()