# kg-mcp

Knowledge-graph / memory MCP server. SQLite + FTS5 + a tiny relations table
giving you typed directed edges between memories.

## Storage

`~/.mcp/kg/memories.db` (override with `KG_MCP_DB_DIR` env var). Created on
first server start. `search-mcp`'s `search_memories` tool reads this file
read-only.

## Tools

- `save_memory(content, memory_type?, tags?, metadata?)`
- `get_memory(memory_id)`
- `list_memories(limit, offset, memory_type?)`
- `search_memories(query, memory_type?, limit)` — FTS5 BM25
- `update_memory(memory_id, ...)`
- `delete_memory(memory_id)`
- `link_memories(from_id, to_id, relation_type)`
- `unlink_memories(from_id, to_id, relation_type)`
- `get_related(memory_id, depth, relation_type?)` — graph walk
- `stats()`

## Setup

```powershell
cd C:\Users\Prerak\MCPServers\kg-mcp
uv sync
uv run python main.py
```

## LM Studio mcp.json

```json
"kg-mcp": {
  "command": "C:/Users/Prerak/MCPServers/kg-mcp/.venv/Scripts/python.exe",
  "args": ["main.py"],
  "cwd": "C:/Users/Prerak/MCPServers/kg-mcp",
  "env": { "KG_MCP_LOG_LEVEL": "info" }
}
```

Logs at `logs/mcp.log` (rotating, 2 MB × 5).