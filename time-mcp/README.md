# time-mcp

MCP server for time and timezone operations. Stdlib `zoneinfo` + `tzdata` (for
IANA names on Windows) + `python-dateutil` for forgiving time string parsing.

## Tools

- `get_current_time(timezone="UTC")`
- `convert_time(time_str, from_tz, to_tz)`
- `get_timezone_info(timezone)`
- `list_timezones(filter="")`
- `format_time(iso_str, format, timezone=None)`

## Setup

```powershell
cd C:\Users\Prerak\MCPServers\time-mcp
uv sync
uv run python main.py
```

## LM Studio mcp.json

```json
"time-mcp": {
  "command": "C:/Users/Prerak/MCPServers/time-mcp/.venv/Scripts/python.exe",
  "args": ["main.py"],
  "cwd": "C:/Users/Prerak/MCPServers/time-mcp",
  "env": { "TIME_MCP_LOG_LEVEL": "info" }
}
```

Logs at `logs/mcp.log` (rotating, 2 MB × 5).