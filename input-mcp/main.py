"""input-mcp — MCP server for live user input via popup UI.

On startup we spawn (or reuse) the ui_app process and wait for it to be
healthy, then enter the FastMCP stdio loop.
"""
from __future__ import annotations

from tools._logging import get_logger

log = get_logger()
log.info("=" * 60)
log.info("input-mcp server starting")

from mcp.server.fastmcp import FastMCP

from tools.prompts import Prompts

_p = Prompts()

mcp = FastMCP("input-mcp")


@mcp.tool()
def ask_text(
    question: str,
    default: str = "",
    multiline: bool = False,
    placeholder: str = "",
    timeout_sec: int = 300,
    regex_validate: str | None = None,
) -> dict:
    """Show a text-input dialog to the actual user and return their reply.

    The response always carries `live: true` when the user typed/clicked. If
    `status` is anything other than "answered", the user is not engaging
    (cancelled / timed_out) — DO NOT proceed with the original action.

    Args:
        question: Plain-text prompt shown above the input box.
        default: Pre-filled value (editable).
        multiline: Use a multi-line text area instead of a single-line entry.
        placeholder: Greyed-out hint text (single-line only).
        timeout_sec: Auto-cancel after this many seconds (1-3600).
        regex_validate: Optional regex; submission is blocked if input doesn't fully match.
    """
    return _p.ask_text(question, default, multiline, placeholder, timeout_sec, regex_validate)


@mcp.tool()
def ask_choice(
    question: str,
    options: list,
    multi_select: bool = False,
    allow_other: bool = True,
    timeout_sec: int = 300,
) -> dict:
    """Show a single- or multi-select dialog and return the user's pick.

    options: list of strings OR list of {label, value?, description?}. When
    multi_select=true the user can pick any number; when allow_other=true an
    "Other" free-text field is shown alongside the options.

    Returns `value` as a single value (single-select) or a list (multi-select).
    `live: true` only when the user submitted; on cancel/timeout `value: null`.
    """
    return _p.ask_choice(question, options, multi_select, allow_other, timeout_sec)


@mcp.tool()
def ask_confirm(
    question: str,
    confirm_label: str = "Yes",
    deny_label: str = "No",
    default: str | None = None,
    timeout_sec: int = 300,
) -> dict:
    """Show a confirm/deny dialog. Returns:
      - status='answered', value=true   → user clicked confirm
      - status='denied',   value=false  → user actively clicked deny
      - status='cancelled', value=null  → user dismissed (Esc / Cancel)
      - status='timed_out', value=null  → no response in time

    `default`: 'yes' or 'no' to focus that button on open.
    """
    return _p.ask_confirm(question, confirm_label, deny_label, default, timeout_sec)


@mcp.tool()
def ask_file(
    question: str,
    mode: str = "open",
    filters: list | None = None,
    multiple: bool = False,
    timeout_sec: int = 300,
) -> dict:
    """Open the OS-native file/directory picker.

    mode: 'open' | 'save' | 'directory'
    filters: [{name, patterns}], e.g. [{"name":"Python","patterns":["*.py"]}]
    multiple: only valid for mode='open'

    Returns absolute path(s) on answered.
    """
    return _p.ask_file(question, mode, filters, multiple, timeout_sec)


@mcp.tool()
def ask_form(
    title: str,
    fields: list,
    timeout_sec: int = 600,
) -> dict:
    """Show a composite multi-field form.

    fields: list of {name, type, label, required?, default?, options?, placeholder?, ...}.
    type ∈ {text, password, multiline, number, checkbox, choice, multi_choice}.

    Returns `value` as {field_name: value, ...} on answered. Required fields
    that are blank prevent submission.
    """
    return _p.ask_form(title, fields, timeout_sec)


@mcp.tool()
def list_pending_requests() -> dict:
    """List the request IDs currently queued or showing in the UI service."""
    return _p.list_pending_requests()


@mcp.tool()
def diagnostic_check() -> dict:
    """Diagnose the input-mcp integration.

    Returns basic information now that UI is rendered directly within the tool call.
    """
    return {
        "client": "internal",
        "status": "ok",
        "description": "UI rendered synchronously using root.mainloop()"
    }


if __name__ == "__main__":
    log.info("entering FastMCP stdio loop")
    mcp.run()
