# search-mcp

MCP server consolidating search capabilities:

- **web_search_tool** — DuckDuckGo + httpx + trafilatura/BS4 scrape
- **file_grep / file_find** — Python regex + glob over the filesystem
- **sqlite_query_tool / sqlite_list_tables** — generic SQLite reader (read-only by default)
- **semantic_index_create / semantic_search / semantic_list_indexes / semantic_delete_index** — sqlite-vec + fastembed (BAAI/bge-small-en-v1.5)
- **search_memories** — read-only FTS5 over the kg-mcp store

## Setup

```powershell
cd C:\Users\Prerak\MCPServers\search-mcp
uv sync
uv run python main.py
```

The first `semantic_search` call downloads the BGE ONNX model (~30 MB) into
the fastembed cache.

## LM Studio mcp.json

```json
"search-mcp": {
  "command": "C:/Users/Prerak/MCPServers/search-mcp/.venv/Scripts/python.exe",
  "args": ["main.py"],
  "cwd": "C:/Users/Prerak/MCPServers/search-mcp",
  "env": { "SEARCH_MCP_LOG_LEVEL": "info" }
}
```

## Storage

- Semantic indexes: `~/.mcp/search/indexes/<name>.db`
- KG store (read-only): `~/.mcp/kg/memories.db` (created by kg-mcp)
- Logs: `logs/mcp.log` (rotating, 2 MB × 5)