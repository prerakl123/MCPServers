# sysops-mcp

MCP server for filesystem operations and shell command execution. Stdlib only.

## Tools

- `read_file`, `write_file`, `list_directory`, `file_info`
- `move_file`, `copy_file`, `delete_path`, `create_directory`
- `execute_command(command, shell, cwd, timeout_sec, env_overrides)` —
  PowerShell / cmd / bash / pwsh
- `get_environment` — read env vars

## Setup

```powershell
cd C:\Users\Prerak\MCPServers\sysops-mcp
uv sync
uv run python main.py
```

## LM Studio mcp.json

```json
"sysops-mcp": {
  "command": "C:/Users/Prerak/MCPServers/sysops-mcp/.venv/Scripts/python.exe",
  "args": ["main.py"],
  "cwd": "C:/Users/Prerak/MCPServers/sysops-mcp",
  "env": { "SYSOPS_MCP_LOG_LEVEL": "info" }
}
```

## Trust model

`execute_command` runs arbitrary commands with the user's privileges. There
is no allow-list. Every invocation is logged in `logs/mcp.log` with the
command, cwd, and exit code for audit. Use accordingly.