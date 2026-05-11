# gmat-prep-ai MCP server

Python MCP server that backs the GMAT Prep AI app with deterministic tools the LLM can call during generation. Stdio transport. Designed to be launched by LM Studio.

## Tools

| Name | Tier | What it does |
|---|---|---|
| `code_interpreter` | 1 | Sandboxed Python (sympy, numpy, pandas, matplotlib pre-imported). Math verification, ad-hoc compute, chart authoring. |
| `taxonomy_lookup` | 1 | Canonical GMAT taxonomy: sections, types, skills, domains, time budgets, answer formats. |
| `validate_question_payload` | 1 | Strict semantic validation of a candidate question JSON. Mirrors `server/utils/validators.js`. |
| `difficulty_estimator` | 2 | Heuristic LLM-free difficulty score (1–5) with reasons. Catches calibration drift. |
| `render_artifact` | 2 | Renders a chart (matplotlib → PNG) or markdown table from a structured spec. |
| `parse_flt_text` | 3 | Heuristic extractor for known FLT result formats (mba.com, Manhattan, TTP, generic). |
| `score_percentile_lookup` | 3 | Static GMAT Focus score → percentile lookup. |

> Web search now lives in the standalone [`search-mcp`](../search-mcp/) server. Register both in LM Studio to give the LLM both GMAT-specific tools and general web search.

## Setup

```powershell
cd C:\Users\Prerak\MCPServers\gmat-prep-ai-mcp
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\pip install -e ".[dev]"
.\.venv\Scripts\pytest                 # all tests should pass
```

## Register with LM Studio

Edit `%USERPROFILE%\.lmstudio\mcp.json` (create the file if it doesn't exist):

```json
{
  "mcpServers": {
    "gmat-prep-ai": {
      "command": "C:/Users/Prerak/MCPServers/gmat-prep-ai-mcp/.venv/Scripts/python.exe",
      "args": ["main.py"],
      "cwd": "C:/Users/Prerak/MCPServers/gmat-prep-ai-mcp",
      "env": {
        "GMAT_MCP_LOG_LEVEL": "info",
        "PYTHONDONTWRITEBYTECODE": "1"
      }
    }
  }
}
```

Notes:
- **Use the full `python.exe` path.** LM Studio launches stdio servers as a non-shell child on Windows; bare `python` resolves unpredictably.
- **Always set `cwd`.** `data/`, `logs/`, and `sandbox/` paths are resolved relative to it.
- **Pass env explicitly.** LM Studio does not load any `.env` file for stdio servers.

After editing `mcp.json`, restart LM Studio and check the **Developer → MCP Servers** pane: you should see `gmat-prep-ai` listed with all 7 tools.

## Logs

All operational logs go to `logs/mcp.log` (rotated, 5 × 2 MB) plus stderr (which LM Studio surfaces in its developer log). Level controlled via `GMAT_MCP_LOG_LEVEL` (debug | info | warn | error).

## Sandbox notes

- `code_interpreter` spawns `python -I sandbox/runner.py` per call. Resource limits are POSIX-only (RLIMIT_AS, RLIMIT_CPU); on Windows the parent-side `subprocess.run` timeout is the only floor. Adequate for a single-user local tool.
- **Network is allowed.** Per project decision; the sandbox can hit URLs.
- **Stdout cap**: 4 KB per call. If a tool result blows past that we truncate and append a `[truncated N chars]` marker. Lower this if you see context-window pressure in the Express logs.
- Generated artifacts (figures, files) land in `logs/sandbox/<run-id>/` and the runner returns their paths in the envelope.

## Sync taxonomy from the GMAT app

The taxonomy in `data/taxonomy.json` is a snapshot of `server/utils/constants.js`. Re-sync after taxonomy changes on the JS side:

```powershell
node scripts/sync_taxonomy.mjs
```

(Set `GMAT_CONSTANTS=<abs-path-to-constants.js>` if your checkout layout differs from the default.)

## Direct invocation (for dev)

You can run the server standalone for ad-hoc protocol probing:

```powershell
.\.venv\Scripts\python.exe main.py
```

It will block on stdin waiting for JSON-RPC frames. Useful with the [`mcp-cli`](https://pypi.org/project/mcp/) inspector.
