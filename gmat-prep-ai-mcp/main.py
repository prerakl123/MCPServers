"""GMAT Prep AI MCP server.

Stdio transport. Registers seven tools across three tiers (see plan
``i-think-there-still-noble-octopus.md``). Designed to be launched by
LM Studio via ``%USERPROFILE%/.lmstudio/mcp.json``.

The first thing this module does on import is initialise file logging. If
anything below crashes during stdio handshake, the trace lands in
``logs/mcp.log`` instead of vanishing into LM Studio's developer pane.
"""
from __future__ import annotations

# Logger first - if anything else explodes on import we still get a trace.
from tools._logging import get_logger

log = get_logger()
log.info("=" * 60)
log.info("gmat-prep-ai MCP server starting")

import json
import sys
from typing import Any

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent, Tool
except ImportError as exc:
    log.error("mcp package not installed: %s", exc)
    log.error("Run: pip install -r requirements.txt")
    raise

from tools import (
    code_interpreter,
    difficulty,
    parse_flt,
    render_artifact,
    score_percentile,
    taxonomy,
    validate_question,
)

server = Server("gmat-prep-ai")


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------
#
# Each entry: (name, module-with-DESCRIPTION+INPUT_SCHEMA, handler-callable).
# Handlers receive the raw arguments dict and return any JSON-serialisable
# payload. The ``call_tool`` wrapper turns that into the MCP TextContent
# response and guarantees we never raise out of a tool call (LM Studio
# treats handler exceptions as fatal protocol errors).

def _h_code_interpreter(args: dict[str, Any]) -> dict:
    return code_interpreter.run(
        code=args.get("code", ""),
        timeout_s=args.get("timeout_s"),
    )


def _h_taxonomy(args: dict[str, Any]) -> dict:
    return taxonomy.lookup(
        query=args.get("query", "all"),
        section=args.get("section"),
    )


def _h_validate(args: dict[str, Any]) -> dict:
    return validate_question.validate(args.get("payload") or {})


def _h_difficulty(args: dict[str, Any]) -> dict:
    return difficulty.estimate(args.get("payload") or {})


def _h_render(args: dict[str, Any]) -> dict:
    return render_artifact.render(args.get("kind", ""), args.get("spec") or {})


def _h_parse_flt(args: dict[str, Any]) -> dict:
    return parse_flt.parse(args.get("raw", ""), args.get("source_hint"))


def _h_score_pct(args: dict[str, Any]) -> dict:
    return score_percentile.lookup(args.get("score", 0), args.get("section", "total"))


_TOOL_TABLE = [
    ("code_interpreter", code_interpreter, _h_code_interpreter),
    ("taxonomy_lookup", taxonomy, _h_taxonomy),
    ("validate_question_payload", validate_question, _h_validate),
    ("difficulty_estimator", difficulty, _h_difficulty),
    ("render_artifact", render_artifact, _h_render),
    ("parse_flt_text", parse_flt, _h_parse_flt),
    ("score_percentile_lookup", score_percentile, _h_score_pct),
]


@server.list_tools()
async def list_tools() -> list[Tool]:
    log.info("list_tools called")
    return [
        Tool(
            name=name,
            description=mod.DESCRIPTION,
            inputSchema=mod.INPUT_SCHEMA,
        )
        for name, mod, _h in _TOOL_TABLE
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any] | None) -> list[TextContent]:
    args = arguments or {}
    args_preview = json.dumps(args, ensure_ascii=False)[:300]
    log.info("call_tool name=%s args=%s", name, args_preview)

    handler = next((h for n, _m, h in _TOOL_TABLE if n == name), None)
    if handler is None:
        log.warning("unknown tool %r", name)
        return [TextContent(type="text", text=json.dumps({
            "error": f"unknown tool: {name}",
            "supported": [n for n, _m, _h in _TOOL_TABLE],
        }))]

    try:
        result = handler(args)
    except Exception as exc:  # noqa: BLE001
        log.exception("tool %s raised: %s", name, exc)
        return [TextContent(type="text", text=json.dumps({
            "error": f"{type(exc).__name__}: {exc}",
            "tool": name,
        }))]

    payload = json.dumps(result, ensure_ascii=False, default=str)
    if len(payload) > 16_000:
        log.warning("tool %s payload large (%d chars); will be returned as-is", name, len(payload))
    log.info("tool %s ok payload_chars=%d", name, len(payload))
    return [TextContent(type="text", text=payload)]


async def main() -> None:
    log.info("entering stdio_server loop")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    import asyncio

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("interrupted by signal")
    except Exception as exc:  # noqa: BLE001
        log.exception("server crashed: %s", exc)
        sys.exit(1)
