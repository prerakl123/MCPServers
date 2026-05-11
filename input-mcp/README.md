# input-mcp

MCP server that lets the LLM ask the actual user questions mid-turn through a
small popup UI. Mirrors Claude Code's AskUserQuestion functionality for local
LM Studio runs.

## Architecture

- **input-mcp** — FastMCP server. Spawns `ui_app` on startup and is the LLM-facing wrapper.
- **ui_app** — long-lived popup service. customtkinter dialogs + pystray + ThreadingHTTPServer.
- They communicate over loopback HTTP, authenticated by a per-startup random token at `~/.mcp/input/token`.

## Tools

- `ask_text(question, default="", multiline=False, placeholder="", timeout_sec=300, regex_validate=None)`
- `ask_choice(question, options, multi_select=False, allow_other=True, timeout_sec=300)`
- `ask_confirm(question, confirm_label="Yes", deny_label="No", default=None, timeout_sec=300)`
- `ask_file(question, mode="open"|"save"|"directory", filters=None, multiple=False, timeout_sec=300)`
- `ask_form(title, fields, timeout_sec=600)`
- `list_pending_requests()`

Every successful response carries `live: true`. Status one of: `answered`,
`cancelled`, `denied`, `timed_out`. If `live` is missing or false the answer
is **not** a real human response — treat as if no answer was received.

## Setup

```powershell
cd C:\Users\Prerak\MCPServers\input-mcp
uv sync
uv run python main.py
```

A tray icon appears in the system tray. The first incoming request opens a
popup window.

## LM Studio mcp.json

```json
"input-mcp": {
  "command": "uv run",
  "args": ["main.py"],
  "cwd": "C:/Users/Prerak/MCPServers/input-mcp",
  "env": {
    "INPUT_MCP_LOG_LEVEL": "info",
    "INPUT_MCP_THEME": "system"
  }
}
```

## Reuse from outside input-mcp

Any local script can drive the UI directly:

```python
import httpx, json
from pathlib import Path
root = Path.home() / ".mcp" / "input"
token = (root / "token").read_text().strip()
port = int((root / "port").read_text().strip())
r = httpx.post(
    f"http://127.0.0.1:{port}/ask",
    headers={"Authorization": f"Bearer {token}"},
    json={"type": "text", "prompt": "Hi from a script", "spec": {}, "timeout_sec": 60},
    timeout=120,
)
print(r.json())
```

See `docs/HTTP_API.md` for the full API.

## Logs

- `logs/mcp.log` — server side
- `logs/ui.log` — UI app side

Both rotating, 2 MB × 5.

## Trust model

Loopback-only HTTP, random per-startup token, file mode 0600 best-effort.
Any process running as your user can read the token and pop dialogs — that's
acceptable for the local MCP use case but **don't** expose the port off
localhost.
