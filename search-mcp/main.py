"""search-mcp — web, file, SQLite, semantic, and KG search."""
from __future__ import annotations

from tools._logging import get_logger

log = get_logger()
log.info("=" * 60)
log.info("search-mcp server starting")

from mcp.server.fastmcp import FastMCP

from tools import file_search, kg_search, semantic, sqlite_query, web_search

mcp = FastMCP("search-mcp")


@mcp.tool()
def web_search_tool(
    query: str,
    max_results: int = 8,
    scrape: bool = True,
    scrape_top: int = 3,
    max_chars_per_page: int = 2000,
) -> dict:
    """Search the web (DuckDuckGo) and scrape the top result pages.

    Returns search hits with title, snippet, url, and (when scrape=True) the
    page's main text via trafilatura/BeautifulSoup. Iterates through results
    until `scrape_top` succeed; one bad URL doesn't sink the call.
    """
    return web_search.search(query, max_results, scrape, scrape_top, max_chars_per_page)


@mcp.tool()
def file_grep(
    pattern: str,
    path: str,
    glob: str = "*",
    regex: bool = True,
    case_sensitive: bool = False,
    max_results: int = 200,
    context_lines: int = 0,
) -> dict:
    """Search file contents for `pattern` under `path`. Returns matches with
    file, line_no, line, and optional context. Skips binaries and >5MB files.
    Set regex=False to treat pattern as a literal string.
    """
    return file_search.file_grep(
        pattern, path, glob, regex, case_sensitive, max_results, context_lines
    )


@mcp.tool()
def file_find(
    name_pattern: str,
    path: str,
    recursive: bool = True,
    max_results: int = 500,
    include_dirs: bool = False,
) -> dict:
    """Find files whose names match a glob (e.g. '*.py', 'README*')."""
    return file_search.file_find(name_pattern, path, recursive, max_results, include_dirs)


@mcp.tool()
def sqlite_query_tool(
    db_path: str,
    sql: str,
    params: list | None = None,
    read_only: bool = True,
    max_rows: int = 1000,
) -> dict:
    """Run SQL against a SQLite DB. read_only=True opens with mode=ro and
    refuses non-SELECT. Returns columns and rows.
    """
    return sqlite_query.query(db_path, sql, params, read_only, max_rows)


@mcp.tool()
def sqlite_list_tables(db_path: str) -> dict:
    """List tables and views in a SQLite database."""
    return sqlite_query.list_tables(db_path)


@mcp.tool()
def semantic_index_create(
    name: str,
    items: list,
    replace: bool = False,
) -> dict:
    """Build a semantic search index from text items.

    items: list of {id?, text, metadata?} dicts. Index is stored at
    ~/.mcp/search/indexes/<name>.db using sqlite-vec + BAAI/bge-small-en-v1.5
    embeddings (384-dim). First call downloads the ~30 MB ONNX model.
    """
    return semantic.index_create(name, items, replace)


@mcp.tool()
def semantic_search(name: str, query: str, top_k: int = 5) -> dict:
    """Semantic search against an existing index. Returns top_k by cosine distance."""
    return semantic.search(name, query, top_k)


@mcp.tool()
def semantic_list_indexes() -> dict:
    """List built semantic indexes."""
    return semantic.list_indexes()


@mcp.tool()
def semantic_delete_index(name: str) -> dict:
    """Delete a semantic index by name."""
    return semantic.delete_index(name)


@mcp.tool()
def search_memories(query: str, memory_type: str | None = None, limit: int = 10) -> dict:
    """Full-text search the knowledge-graph store (kg-mcp). Read-only.

    memory_type: optional filter, e.g. 'fact', 'preference', 'task'.
    Returns memories ranked by FTS5 BM25 score.
    """
    return kg_search.search_memories(query, memory_type, limit)


if __name__ == "__main__":
    log.info("entering FastMCP stdio loop")
    mcp.run()