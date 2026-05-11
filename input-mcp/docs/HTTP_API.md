# input-mcp UI service — HTTP API

Loopback-only. All endpoints require `Authorization: Bearer <token>` where
`<token>` is the contents of `~/.mcp/input/token` (32 hex chars, regenerated
each MCP server startup).

Discovery files under `~/.mcp/input/`:

- `token` — bearer token
- `port`  — TCP port the UI is listening on
- `pid`   — UI process id

## POST /ask

Submit an input request. Blocks until the user answers, cancels, or the
request times out.

### Request body

```json
{
  "type": "text" | "choice" | "confirm" | "file" | "form",
  "prompt": "string",
  "spec": { ... type-specific ... },
  "timeout_sec": 300,
  "origin": "string (free-form attribution)",
  "request_id": "uuid (optional)"
}
```

### Response

```json
{
  "status": "answered" | "cancelled" | "denied" | "timed_out",
  "live": true,
  "value": <type-dependent or null>,
  "user_note": "string",
  "answered_at": "ISO-8601 UTC",
  "elapsed_ms": 12345,
  "request_id": "uuid",
  "type": "text"
}
```

`live: true` is set only when the response originated from the actual
dialog. Synthetic / error paths return `live: false`.

### `spec` per type

| type    | spec fields                                                                    | `value` on answered                  |
|---------|--------------------------------------------------------------------------------|--------------------------------------|
| text    | `default`, `multiline`, `placeholder`, `regex_validate?`                       | string                               |
| choice  | `options`, `multi_select`, `allow_other`                                       | one value, or list of values         |
| confirm | `confirm_label`, `deny_label`, `default`                                       | `true` (denied → status='denied', value=false) |
| file    | `mode (open|save|directory)`, `filters: [{name, patterns}]`, `multiple`        | absolute path, or list of paths      |
| form    | `fields: [{name, type, label, required?, default?, options?, placeholder?}]`   | `{field_name: value, ...}`           |

Form field types: `text`, `password`, `multiline`, `number`, `checkbox`,
`choice`, `multi_choice`.

## GET /health

```json
{"ok": true, "version": "0.1.0", "pending_count": 0, "uptime_sec": 12.3}
```

## GET /pending

```json
{"pending": [{"request_id": "...", "type": "text", "origin": "...", "state": "showing|queued"}]}
```

## POST /cancel/{request_id}

Force-cancel a queued/showing request from outside. The blocked `/ask` call
returns immediately with `status="cancelled"`.

## POST /shutdown

Graceful exit of the UI service. Any in-flight requests resolve as
`cancelled` first.
