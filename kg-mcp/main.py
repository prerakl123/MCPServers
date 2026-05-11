"""kg-mcp — knowledge graph / memory store backed by SQLite + FTS5."""
from __future__ import annotations

from tools._logging import get_logger

log = get_logger()
log.info("=" * 60)
log.info("kg-mcp server starting")

from mcp.server.fastmcp import FastMCP

from tools import schema, store

# Initialise DB on startup so search-mcp's read-only access has something to open.
db_path = schema.init_db()
log.info("kg-mcp store ready at %s", db_path)

mcp = FastMCP("kg-mcp")


@mcp.tool()
def save_memory(
    content: str,
    memory_type: str | None = None,
    tags: list[str] | None = None,
    metadata: dict | None = None,
) -> dict:
    """Save a new memory. Returns id, timestamps, and the saved record.

    memory_type: free-form label, e.g. 'fact', 'preference', 'task', 'note'.
    tags: list of strings for filtering and FTS.
    metadata: arbitrary JSON-serialisable dict.
    """
    return store.save_memory(content, memory_type, tags, metadata)


@mcp.tool()
def get_memory(memory_id: int) -> dict:
    """Fetch a memory by id."""
    return store.get_memory(memory_id)


@mcp.tool()
def list_memories(limit: int = 50, offset: int = 0, memory_type: str | None = None) -> dict:
    """List memories newest-first. Optional type filter; paginated by limit/offset."""
    return store.list_memories(limit, offset, memory_type)


@mcp.tool()
def search_memories(query: str, memory_type: str | None = None, limit: int = 10) -> dict:
    """Full-text (FTS5) search memories. Returns BM25-ranked results.

    Supports FTS5 syntax: bare words ("api server"), phrase ("\"exact phrase\""),
    OR / AND / NOT, and prefix ("auth*").
    """
    return store.search_memories(query, memory_type, limit)


@mcp.tool()
def update_memory(
    memory_id: int,
    content: str | None = None,
    memory_type: str | None = None,
    tags: list[str] | None = None,
    metadata: dict | None = None,
) -> dict:
    """Update one or more fields on a memory. Pass None to leave a field unchanged."""
    return store.update_memory(memory_id, content, memory_type, tags, metadata)


@mcp.tool()
def delete_memory(memory_id: int) -> dict:
    """Delete a memory by id. Cascades to its relations."""
    return store.delete_memory(memory_id)


@mcp.tool()
def link_memories(from_id: int, to_id: int, relation_type: str) -> dict:
    """Create a typed directed relation between two memories.

    relation_type is free-form, e.g. 'depends_on', 'follows', 'related_to'.
    """
    return store.link_memories(from_id, to_id, relation_type)


@mcp.tool()
def unlink_memories(from_id: int, to_id: int, relation_type: str) -> dict:
    """Remove a specific relation."""
    return store.unlink_memories(from_id, to_id, relation_type)


@mcp.tool()
def get_related(memory_id: int, depth: int = 1, relation_type: str | None = None) -> dict:
    """Walk the graph from a memory up to `depth` hops (max 5). Returns nodes + edges."""
    return store.get_related(memory_id, depth, relation_type)


@mcp.tool()
def stats() -> dict:
    """Return store statistics: db path, total memories, total relations, counts by type."""
    return store.stats()


if __name__ == "__main__":
    log.info("entering FastMCP stdio loop")
    mcp.run()