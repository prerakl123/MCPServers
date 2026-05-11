"""Time and timezone tool implementations."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, available_timezones

from dateutil import parser as _dt_parser

from ._logging import get_logger

log = get_logger("clock")


def _zone(name: str) -> ZoneInfo:
    if not name or not isinstance(name, str):
        raise ValueError("timezone must be a non-empty IANA name (e.g. 'UTC', 'America/New_York')")
    try:
        return ZoneInfo(name)
    except Exception as exc:
        raise ValueError(f"unknown timezone {name!r}: {exc}") from exc


def _format_offset(td: timedelta | None) -> str:
    if td is None:
        return "+00:00"
    total_min = int(td.total_seconds() // 60)
    sign = "+" if total_min >= 0 else "-"
    total_min = abs(total_min)
    return f"{sign}{total_min // 60:02d}:{total_min % 60:02d}"


def _describe(dt: datetime) -> dict[str, Any]:
    off = dt.utcoffset()
    dst = dt.dst()
    return {
        "iso": dt.isoformat(),
        "unix": dt.timestamp(),
        "tz": str(dt.tzinfo) if dt.tzinfo else None,
        "utc_offset": _format_offset(off),
        "utc_offset_seconds": int(off.total_seconds()) if off else 0,
        "dst_active": bool(dst and dst.total_seconds() != 0),
        "abbreviation": dt.tzname() or "",
        "year": dt.year,
        "month": dt.month,
        "day": dt.day,
        "hour": dt.hour,
        "minute": dt.minute,
        "second": dt.second,
        "weekday": dt.strftime("%A"),
    }


def get_current_time(timezone_name: str = "UTC") -> dict[str, Any]:
    tz = _zone(timezone_name)
    now = datetime.now(tz=tz)
    log.info("get_current_time tz=%s -> %s", timezone_name, now.isoformat())
    return _describe(now)


def convert_time(time_str: str, from_tz: str, to_tz: str) -> dict[str, Any]:
    if not time_str:
        raise ValueError("time_str is required")
    src = _zone(from_tz)
    dst = _zone(to_tz)

    parsed = _dt_parser.parse(time_str)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=src)
    else:
        parsed = parsed.astimezone(src)

    converted = parsed.astimezone(dst)
    src_off = parsed.utcoffset() or timedelta(0)
    dst_off = converted.utcoffset() or timedelta(0)
    delta_hours = (dst_off - src_off).total_seconds() / 3600.0

    log.info("convert_time %s %s -> %s : %s", time_str, from_tz, to_tz, converted.isoformat())
    return {
        "input": time_str,
        "from": _describe(parsed),
        "to": _describe(converted),
        "offset_difference_hours": delta_hours,
    }


def get_timezone_info(timezone_name: str) -> dict[str, Any]:
    tz = _zone(timezone_name)
    now = datetime.now(tz=tz)
    info: dict[str, Any] = {
        "name": timezone_name,
        "abbreviation": now.tzname() or "",
        "current_offset": _format_offset(now.utcoffset()),
        "dst_active": bool(now.dst() and now.dst().total_seconds() != 0),
    }
    try:
        transitions = _find_dst_transitions(tz, now)
        info["dst_starts"] = transitions.get("start")
        info["dst_ends"] = transitions.get("end")
        info["has_dst"] = transitions.get("has_dst", False)
    except Exception as exc:
        log.warning("dst probing failed for %s: %s", timezone_name, exc)
        info["has_dst"] = None
    return info


def _find_dst_transitions(tz: ZoneInfo, anchor: datetime) -> dict[str, Any]:
    start = (anchor - timedelta(days=180)).replace(minute=0, second=0, microsecond=0)
    end = anchor + timedelta(days=200)
    cur = start
    prev_off = cur.replace(tzinfo=tz).utcoffset()
    transitions: list[tuple[datetime, timedelta | None]] = []
    while cur <= end:
        nxt = cur + timedelta(hours=1)
        off = nxt.replace(tzinfo=tz).utcoffset()
        if off != prev_off:
            transitions.append((nxt, off))
            prev_off = off
        cur = nxt

    has_dst = len(transitions) > 0
    out: dict[str, Any] = {"has_dst": has_dst}
    for ts, _off in transitions[:2]:
        as_local = ts.replace(tzinfo=tz)
        if as_local.dst() and as_local.dst().total_seconds() != 0:
            out["start"] = as_local.isoformat()
        else:
            out["end"] = as_local.isoformat()
    return out


def list_timezones(filter_text: str = "") -> dict[str, Any]:
    needle = (filter_text or "").lower().strip()
    names = sorted(available_timezones())
    if needle:
        names = [n for n in names if needle in n.lower()]
    return {"count": len(names), "filter": filter_text, "timezones": names[:500]}


def format_time(iso_str: str, format_str: str = "%Y-%m-%d %H:%M:%S %Z", timezone_name: str | None = None) -> dict[str, Any]:
    parsed = _dt_parser.parse(iso_str)
    if timezone_name:
        tz = _zone(timezone_name)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=tz)
        else:
            parsed = parsed.astimezone(tz)
    return {"input": iso_str, "format": format_str, "formatted": parsed.strftime(format_str)}