"""parse_flt_text MCP tool.

Heuristic parser for known full-length test result formats. Tries each
pattern in ``data/flt_format_patterns.json`` in order; first match wins.
The model can then fall back to a free-form LLM extraction if confidence is
low. Saves an LLM round-trip on the common case.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from ._logging import get_logger

log = get_logger("parse_flt")

_PATTERNS_FILE = Path(__file__).resolve().parents[1] / "data" / "flt_format_patterns.json"


@lru_cache(maxsize=1)
def _load_patterns() -> dict:
    with _PATTERNS_FILE.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _try_json(raw: str) -> dict | None:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    keys = {k.lower(): v for k, v in data.items()}
    out: dict[str, Any] = {}
    if "total" in keys or "total_score" in keys:
        out["total_score"] = keys.get("total") or keys.get("total_score")
    if "quant" in keys or "quant_score" in keys:
        out["quant_score"] = keys.get("quant") or keys.get("quant_score")
    if "verbal" in keys or "verbal_score" in keys:
        out["verbal_score"] = keys.get("verbal") or keys.get("verbal_score")
    if "di" in keys or "di_score" in keys or "data_insights" in keys:
        out["di_score"] = keys.get("di") or keys.get("di_score") or keys.get("data_insights")
    return out or None


def _coerce_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def parse(raw: str, source_hint: str | None = None) -> dict[str, Any]:
    if not isinstance(raw, str) or not raw.strip():
        return {"ok": False, "error": "raw must be a non-empty string"}
    raw = raw.strip()

    # 1) Try JSON parse first - many official exports are structured.
    j = _try_json(raw)
    if j is not None:
        log.info("parse_flt matched JSON envelope")
        return {
            "ok": True,
            "matched_pattern": "json_envelope",
            "confidence": 0.95,
            "scores": {
                "total_score": _coerce_int(j.get("total_score")),
                "quant_score": _coerce_int(j.get("quant_score")),
                "verbal_score": _coerce_int(j.get("verbal_score")),
                "di_score": _coerce_int(j.get("di_score")),
            },
            "percentiles": {},
        }

    cfg = _load_patterns()
    matched_name: str | None = None
    matched_groups: dict[str, str] = {}
    for pat in cfg.get("patterns", []):
        flags = re.IGNORECASE if pat.get("ignore_case") else 0
        try:
            m = re.search(pat["regex"], raw, flags)
        except re.error as exc:
            log.error("regex compile failed for pattern %s: %s", pat.get("name"), exc)
            continue
        if m:
            matched_name = pat.get("name")
            matched_groups = {k: v for k, v in m.groupdict().items() if v is not None}
            log.info("parse_flt matched pattern=%s groups=%s", matched_name, list(matched_groups))
            break

    if not matched_name:
        return {"ok": False, "error": "no known FLT pattern matched", "tried_patterns": [p.get("name") for p in cfg.get("patterns", [])]}

    scores = {
        "total_score": _coerce_int(matched_groups.get("total")),
        "quant_score": _coerce_int(matched_groups.get("quant")),
        "verbal_score": _coerce_int(matched_groups.get("verbal")),
        "di_score": _coerce_int(matched_groups.get("di")),
    }

    # Percentiles via the supplemental pattern.
    percentiles: dict[str, int] = {}
    pct_cfg = cfg.get("percentile_pattern")
    if pct_cfg:
        flags = re.IGNORECASE if pct_cfg.get("ignore_case") else 0
        for m in re.finditer(pct_cfg["regex"], raw, flags):
            sec = (m.group("section") or "").lower()
            val = _coerce_int(m.group("value"))
            if val is None:
                continue
            if "quant" in sec:
                percentiles["quant"] = val
            elif "verbal" in sec:
                percentiles["verbal"] = val
            elif "di" in sec or "insights" in sec:
                percentiles["di"] = val

    confidence = 0.85 if all(v is not None for v in scores.values()) else 0.6
    return {
        "ok": True,
        "matched_pattern": matched_name,
        "source_hint": source_hint,
        "confidence": confidence,
        "scores": scores,
        "percentiles": percentiles,
    }


INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "raw": {
            "type": "string",
            "description": "Raw FLT result text or JSON the user uploaded.",
        },
        "source_hint": {
            "type": "string",
            "description": "Optional hint: 'mba_com' | 'manhattan' | 'ttp' | 'official_practice' | etc. Currently unused for routing but echoed back for downstream logging.",
        },
    },
    "required": ["raw"],
    "additionalProperties": False,
}

DESCRIPTION = (
    "Extract GMAT Focus scores from raw FLT result text or JSON. Tries deterministic patterns "
    "(mba.com, Manhattan Prep, Target Test Prep, generic Q/V/DI/Total) and a JSON-envelope fast path. "
    "Returns {scores, percentiles, matched_pattern, confidence}. If no pattern matches, the caller "
    "should fall back to LLM extraction with the FLT analysis prompt."
)
