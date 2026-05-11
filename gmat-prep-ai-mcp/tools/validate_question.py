"""validate_question_payload MCP tool.

Mirrors the strict checks from ``server/utils/validators.js`` so Gemma can
self-correct in-loop. The JS validator stays as the post-hoc fast-fail gate
in Express; this is the in-conversation surface the model can consult.
"""
from __future__ import annotations

import json
import re
from typing import Any

from ._logging import get_logger
from .taxonomy import _load as _load_taxonomy

log = get_logger("validate_question")

_LABEL_PATTERN = re.compile(r"^[A-E]$")


def _taxonomy_codes() -> dict[str, set[str]]:
    tax = _load_taxonomy()
    return {
        "sections": {it["code"] for it in tax["sections"]},
        "content_domains": {it["code"] for it in tax["content_domains"]},
        "question_types": {it["code"] for it in tax["question_types"]},
        "fundamental_skills": {it["code"] for it in tax["fundamental_skills"]},
        "answer_formats": set(tax["answer_formats"]),
    }


def _qt_section(code: str) -> str | None:
    for it in _load_taxonomy()["question_types"]:
        if it["code"] == code:
            return it["section"]
    return None


def _validate_single_choice(payload: dict, errors: list[str]) -> None:
    options = payload.get("options") or []
    if not isinstance(options, list) or not (4 <= len(options) <= 5):
        errors.append(f"single_choice/data_sufficiency requires 4-5 options, got {len(options)}")
        return
    labels: list[str] = []
    for i, opt in enumerate(options):
        if not isinstance(opt, dict):
            errors.append(f"options[{i}] must be an object")
            continue
        label = (opt.get("label") or "").strip()
        text = (opt.get("text") or "").strip()
        if not _LABEL_PATTERN.match(label):
            errors.append(f"options[{i}].label must be A-E, got {label!r}")
        if not text:
            errors.append(f"options[{i}].text must be non-empty")
        labels.append(label)
    if len(set(labels)) != len(labels):
        errors.append(f"duplicate option labels: {labels}")
    ca = (payload.get("correct_answer") or "").strip()
    if ca not in labels:
        errors.append(f"correct_answer {ca!r} must match one of {labels}")


def _validate_two_part(payload: dict, errors: list[str]) -> None:
    ap = payload.get("answer_payload") or {}
    cols = ap.get("columns") or []
    rows = ap.get("rows") or []
    if not isinstance(cols, list) or len(cols) != 2:
        errors.append("two_part requires answer_payload.columns of length 2")
    if not isinstance(rows, list) or len(rows) < 2:
        errors.append("two_part requires answer_payload.rows (>= 2 entries)")
    ca = (payload.get("correct_answer") or "").strip()
    if not re.match(r"^[^|]+\|[^|]+$", ca):
        errors.append("two_part correct_answer must be 'col1Choice|col2Choice'")


def _validate_table(payload: dict, errors: list[str], multi: bool) -> None:
    fmt = "table_checkbox" if multi else "table_radio"
    ap = payload.get("answer_payload") or {}
    rows = ap.get("rows") or []
    cols = ap.get("columns") or []
    if not isinstance(rows, list) or len(rows) < 2:
        errors.append(f"{fmt} requires answer_payload.rows (>= 2)")
    if not isinstance(cols, list) or len(cols) < 2:
        errors.append(f"{fmt} requires answer_payload.columns (>= 2)")
    ca = (payload.get("correct_answer") or "").strip()
    if not ca:
        errors.append(f"{fmt} correct_answer must be a non-empty serialized string")
        return
    try:
        parsed = json.loads(ca)
    except json.JSONDecodeError as exc:
        errors.append(f"{fmt} correct_answer must be valid JSON; parse failed: {exc}")
        return
    if not isinstance(parsed, dict):
        errors.append(f"{fmt} correct_answer JSON must be an object keyed by row")
        return
    row_ids = {r.get("id") or r.get("label") or r.get("key") for r in rows if isinstance(r, dict)}
    col_ids = {c.get("id") or c.get("label") or c.get("key") if isinstance(c, dict) else c for c in cols}
    for k, v in parsed.items():
        if row_ids and k not in row_ids:
            errors.append(f"{fmt} correct_answer references unknown row {k!r}")
        if multi:
            if not isinstance(v, list):
                errors.append(f"{fmt} correct_answer[{k!r}] must be a list")
                continue
            for item in v:
                if col_ids and item not in col_ids:
                    errors.append(f"{fmt} correct_answer[{k!r}] has unknown column {item!r}")
        else:
            if col_ids and v not in col_ids:
                errors.append(f"{fmt} correct_answer[{k!r}] has unknown column {v!r}")


def _validate_inline_dropdown(payload: dict, errors: list[str]) -> None:
    ap = payload.get("answer_payload") or {}
    template = ap.get("template")
    slots = ap.get("slots") or {}
    if not isinstance(template, str) or len(template) < 5:
        errors.append("inline_dropdown requires answer_payload.template (>= 5 chars)")
    if not isinstance(slots, dict) or not slots:
        errors.append("inline_dropdown requires answer_payload.slots map")
    ca = (payload.get("correct_answer") or "").strip()
    if not ca:
        errors.append("inline_dropdown correct_answer must be JSON of slot=>choice")
        return
    try:
        parsed = json.loads(ca)
    except json.JSONDecodeError as exc:
        errors.append(f"inline_dropdown correct_answer must be valid JSON; parse failed: {exc}")
        return
    if not isinstance(parsed, dict):
        errors.append("inline_dropdown correct_answer JSON must be an object")
        return
    for slot, choice in parsed.items():
        if slot not in slots:
            errors.append(f"correct_answer references unknown slot {slot!r}")
            continue
        allowed = slots.get(slot) or []
        if isinstance(allowed, list) and choice not in allowed:
            errors.append(f"correct_answer[{slot!r}]={choice!r} not in declared options {allowed}")


def validate(payload: dict) -> dict[str, Any]:
    """Return ``{"valid": bool, "errors": [str], "normalized": dict|None}``."""
    if not isinstance(payload, dict):
        return {"valid": False, "errors": ["payload must be an object"], "normalized": None}

    codes = _taxonomy_codes()
    errors: list[str] = []

    section = payload.get("section")
    if section not in codes["sections"]:
        errors.append(f"invalid section: {section!r}")

    qt = payload.get("question_type")
    if qt not in codes["question_types"]:
        errors.append(f"invalid question_type: {qt!r}")
    else:
        sec_for_qt = _qt_section(qt)
        if section and sec_for_qt and sec_for_qt != section:
            errors.append(
                f"section/question_type mismatch: {section} vs {qt} (expects {sec_for_qt})"
            )

    cd = payload.get("content_domain")
    if cd is not None and cd not in codes["content_domains"]:
        errors.append(f"invalid content_domain: {cd!r}")

    fs = payload.get("fundamental_skill")
    if fs is not None and fs not in codes["fundamental_skills"]:
        errors.append(f"invalid fundamental_skill: {fs!r}")

    if section == "VERBAL" and cd is not None:
        errors.append("VERBAL questions must have content_domain = null")
    if section == "DI" and fs is not None:
        errors.append("DI questions must have fundamental_skill = null")

    diff = payload.get("difficulty_level")
    if not isinstance(diff, int) or not 1 <= diff <= 5:
        errors.append(f"difficulty_level must be integer 1..5, got {diff!r}")

    text = payload.get("question_text")
    if not isinstance(text, str) or len(text.strip()) < 20:
        errors.append("question_text must be a string of length >= 20")

    fmt = payload.get("answer_format")
    if fmt not in codes["answer_formats"]:
        errors.append(f"invalid answer_format: {fmt!r}")
    else:
        if fmt in ("single_choice", "data_sufficiency"):
            _validate_single_choice(payload, errors)
        elif fmt == "two_part":
            _validate_two_part(payload, errors)
        elif fmt == "table_radio":
            _validate_table(payload, errors, multi=False)
        elif fmt == "table_checkbox":
            _validate_table(payload, errors, multi=True)
        elif fmt == "inline_dropdown":
            _validate_inline_dropdown(payload, errors)

    expl = payload.get("explanation")
    if not isinstance(expl, str) or len(expl.strip()) < 10:
        errors.append("explanation must be a string of length >= 10")

    tags = payload.get("topic_tags")
    if tags is not None:
        if not isinstance(tags, list) or any(not isinstance(t, str) for t in tags):
            errors.append("topic_tags must be a list of strings")
        elif len(tags) > 8:
            errors.append("topic_tags must contain at most 8 entries")

    valid = len(errors) == 0
    log.info("validate_question valid=%s errors=%d", valid, len(errors))
    return {"valid": valid, "errors": errors, "normalized": payload if valid else None}


INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "payload": {
            "type": "object",
            "description": "The candidate question JSON. Must include section, question_type, difficulty_level, answer_format, question_text, correct_answer, explanation, topic_tags, plus options or answer_payload depending on the format.",
            "additionalProperties": True,
        }
    },
    "required": ["payload"],
    "additionalProperties": False,
}

DESCRIPTION = (
    "Run strict semantic validation on a candidate GMAT question payload before returning it. "
    "Catches invalid taxonomy codes, section/question_type mismatches, malformed DI tabular or "
    "dropdown answer encodings, missing fields, and label inconsistencies. Returns "
    "{valid: bool, errors: [string]}. If valid is false, fix the listed errors and retry."
)
