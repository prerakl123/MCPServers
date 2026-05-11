"""time-mcp — MCP server for time and timezone operations.

Stdio transport via FastMCP. Launched by LM Studio through mcp.json.
"""
from __future__ import annotations

from tools._logging import get_logger

log = get_logger()
log.info("=" * 60)
log.info("time-mcp server starting")

from mcp.server.fastmcp import FastMCP

from tools import clock

mcp = FastMCP("time-mcp")


@mcp.tool()
def get_current_time(timezone: str = "UTC") -> dict:
    """Return the current date and time in the given IANA timezone.

    Args:
        timezone: IANA timezone name, e.g. "UTC", "America/New_York", "Asia/Tokyo".
    """
    return clock.get_current_time(timezone)


@mcp.tool()
def convert_time(time_str: str, from_tz: str, to_tz: str) -> dict:
    """Convert a date/time string from one timezone to another.

    time_str accepts ISO-8601 or any common format ("May 9 2025 2:30 PM").
    If the string carries no timezone, from_tz is assumed.
    """
    return clock.convert_time(time_str, from_tz, to_tz)


@mcp.tool()
def get_timezone_info(timezone: str) -> dict:
    """Return offset, DST status, and upcoming DST transitions for an IANA tz."""
    return clock.get_timezone_info(timezone)


@mcp.tool()
def list_timezones(filter: str = "") -> dict:
    """List IANA timezone names. Substring filter (case-insensitive). Capped at 500."""
    return clock.list_timezones(filter)


@mcp.tool()
def format_time(iso_str: str, format: str = "%Y-%m-%d %H:%M:%S %Z", timezone: str | None = None) -> dict:
    """Format an ISO-8601 timestamp using a strftime pattern, optionally
    converting to `timezone` first.
    """
    return clock.format_time(iso_str, format, timezone)


if __name__ == "__main__":
    log.info("entering FastMCP stdio loop")
    mcp.run()