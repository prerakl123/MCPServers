"""taxonomy_lookup MCP tool.

Reads ``data/taxonomy.json`` (the synced mirror of
``server/utils/constants.js``) and answers structured queries from it. Cached
in-process; the data file is small and immutable for the life of the server.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from ._logging import get_logger

log = get_logger("taxonomy")

_DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "taxonomy.json"


@lru_cache(maxsize=1)
def _load() -> dict:
    with _DATA_FILE.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    log.info("taxonomy loaded from %s", _DATA_FILE.name)
    return data


def _filter_by_section(items: list[dict], section: str | None) -> list[dict]:
    if not section:
        return items
    return [it for it in items if it.get("section") == section]


def lookup(query: str, section: str | None = None) -> dict[str, Any]:
    """Return canonical taxonomy data for ``query``.

    Supported queries:
      - "all"                   → entire taxonomy
      - "sections"              → list of {code, label}
      - "question_types"        → optionally filtered by ``section``
      - "fundamental_skills"    → optionally filtered by ``section``
      - "content_domains"       → optionally filtered by ``section``
      - "difficulty_levels"     → 1..5 with labels
      - "answer_formats"        → list of strings
      - "time_budgets"          → full nested map
      - "<exact code>"          → details for that specific code
                                  (e.g. "Q_RATES_RATIOS_PERCENT")
    """
    data = _load()
    q = (query or "").strip()

    if q in ("", "all"):
        return data

    if q == "sections":
        return {"items": data["sections"]}
    if q == "question_types":
        return {"items": _filter_by_section(data["question_types"], section)}
    if q == "fundamental_skills":
        return {"items": _filter_by_section(data["fundamental_skills"], section)}
    if q == "content_domains":
        return {"items": _filter_by_section(data["content_domains"], section)}
    if q == "difficulty_levels":
        return {"items": data["difficulty_levels"]}
    if q == "answer_formats":
        return {"items": data["answer_formats"]}
    if q == "time_budgets":
        return {"items": data["time_budgets_seconds"]}

    # Treat as an exact code lookup across all enums.
    for bucket in ("sections", "content_domains", "question_types", "fundamental_skills"):
        for item in data[bucket]:
            if item["code"] == q:
                return {"bucket": bucket, "item": item}

    log.warning("taxonomy unknown query: %r", q)
    return {"error": f"unknown taxonomy query: {q!r}", "supported": [
        "all", "sections", "question_types", "fundamental_skills",
        "content_domains", "difficulty_levels", "answer_formats", "time_budgets",
        "<exact-code>",
    ]}


INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "What to look up. Use 'all' for the full taxonomy, a category name (e.g. 'question_types'), or an exact code (e.g. 'Q_RATES_RATIOS_PERCENT').",
        },
        "section": {
            "type": "string",
            "enum": ["QUANT", "VERBAL", "DI"],
            "description": "Optional section filter for category queries (question_types, fundamental_skills, content_domains).",
        },
    },
    "required": ["query"],
    "additionalProperties": False,
}

DESCRIPTION = (
    "Return canonical GMAT Focus Edition taxonomy: section codes, question types, "
    "fundamental skills, content domains, difficulty levels, answer formats, time budgets. "
    "Call this any time you're unsure which exact code to use - never invent codes. "
    "Filter by section via the optional 'section' arg (QUANT / VERBAL / DI)."
)
