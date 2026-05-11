"""score_percentile_lookup MCP tool.

Static GMAT Focus score → percentile lookup. Linearly interpolates between
known anchor scores; returns null for out-of-range inputs.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from ._logging import get_logger

log = get_logger("score_percentile")

_DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "score_percentiles.json"


@lru_cache(maxsize=1)
def _load() -> dict:
    with _DATA_FILE.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    # Normalise keys to int, drop the leading underscore note.
    return {
        section: {int(k): int(v) for k, v in sec.items()}
        for section, sec in data.items()
        if not section.startswith("_")
    }


def _interpolate(table: dict[int, int], score: int) -> float | None:
    if score in table:
        return float(table[score])
    sorted_scores = sorted(table)
    if score < sorted_scores[0] or score > sorted_scores[-1]:
        return None
    # Linear interpolation between the two adjacent anchors.
    lower = max(s for s in sorted_scores if s < score)
    upper = min(s for s in sorted_scores if s > score)
    span = upper - lower
    if span == 0:
        return float(table[lower])
    weight = (score - lower) / span
    return table[lower] + (table[upper] - table[lower]) * weight


def lookup(score: int, section: str = "total") -> dict[str, Any]:
    if not isinstance(score, int):
        try:
            score = int(score)
        except (TypeError, ValueError):
            return {"ok": False, "error": "score must be an integer"}
    section = (section or "total").upper() if section.lower() != "total" else "total"
    tables = _load()
    table = tables.get(section)
    if table is None:
        return {
            "ok": False,
            "error": f"unknown section {section!r}; supported: {list(tables.keys())}",
        }
    pct = _interpolate(table, score)
    log.info("score_percentile section=%s score=%d pct=%s", section, score, pct)
    if pct is None:
        return {
            "ok": True,
            "section": section,
            "score": score,
            "percentile": None,
            "out_of_range": True,
        }
    return {
        "ok": True,
        "section": section,
        "score": score,
        "percentile": round(pct),
        "out_of_range": False,
    }


INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {
            "type": "integer",
            "description": "GMAT Focus score. 205-805 for total, 60-90 for individual sections.",
        },
        "section": {
            "type": "string",
            "enum": ["total", "QUANT", "VERBAL", "DI"],
            "description": "Which percentile table to consult. Default 'total'.",
        },
    },
    "required": ["score"],
    "additionalProperties": False,
}

DESCRIPTION = (
    "Look up the percentile rank for a GMAT Focus Edition score. Section can be 'total' "
    "(default) or one of 'QUANT' / 'VERBAL' / 'DI'. Returns null percentile for out-of-range "
    "scores. Use this when generating analysis text or dashboard cards that need accurate "
    "percentile data without making up numbers."
)
