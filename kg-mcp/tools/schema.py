"""SQLite schema and connection helpers for the memory store."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

DB_DIR = Path(os.environ.get("KG_MCP_DB_DIR", str(Path.home() / ".mcp" / "kg")))
DB_PATH = DB_DIR / "memories.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    type TEXT,
    tags TEXT,
    metadata TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(type);
CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at);

CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    content,
    tags,
    content='memories',
    content_rowid='id',
    tokenize='porter unicode61'
);

CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, content, tags) VALUES (new.id, new.content, COALESCE(new.tags, ''));
END;

CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content, tags) VALUES('delete', old.id, old.content, COALESCE(old.tags, ''));
END;

CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content, tags) VALUES('delete', old.id, old.content, COALESCE(old.tags, ''));
    INSERT INTO memories_fts(rowid, content, tags) VALUES (new.id, new.content, COALESCE(new.tags, ''));
END;

CREATE TABLE IF NOT EXISTS relations (
    from_id INTEGER NOT NULL,
    to_id INTEGER NOT NULL,
    relation_type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (from_id, to_id, relation_type),
    FOREIGN KEY (from_id) REFERENCES memories(id) ON DELETE CASCADE,
    FOREIGN KEY (to_id) REFERENCES memories(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_relations_from ON relations(from_id);
CREATE INDEX IF NOT EXISTS idx_relations_to ON relations(to_id);
"""


def init_db() -> Path:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.executescript(_SCHEMA)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.commit()
    finally:
        conn.close()
    return DB_PATH


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=10.0)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn