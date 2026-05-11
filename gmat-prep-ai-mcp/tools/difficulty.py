"""difficulty_estimator MCP tool.

Heuristic, LLM-free score for question complexity. Used by the generation
retry loop to reject items whose declared difficulty drifts from the
estimated value by more than 1 level.

Signals (additive; weighted in ``_score()``):
  - Reasoning steps in the explanation (sentence + connector count).
  - Vocabulary complexity (long-word ratio).
  - Distractor proximity for numeric MCQ answers.
  - Question-text length and clause density.
  - Section-specific markers (e.g. nested conditionals in DS, multi-source
    references in MSR).
"""
from __future__ import annotations

import math
import re
from typing import Any

from ._logging import get_logger

log = get_logger("difficulty")

_SENTENCE_RE = re.compile(r"[.!?](?:\s|$)")
_STEP_CONNECTORS = re.compile(
    r"\b(first|then|next|finally|therefore|thus|hence|so|because|since|"
    r"step\s*\d+|consequently|substituting|solving|notice that|observe)\b",
    re.IGNORECASE,
)
_LONG_WORD = re.compile(r"\b\w{8,}\b")
_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?(?:/\d+)?")
_CONDITIONAL_RE = re.compile(r"\b(if|unless|provided that|given that|either|neither)\b", re.IGNORECASE)


def _count_steps(explanation: str) -> int:
    sentences = max(1, len(_SENTENCE_RE.findall(explanation)))
    connectors = len(_STEP_CONNECTORS.findall(explanation))
    return sentences + connectors


def _vocab_complexity(text: str) -> float:
    words = re.findall(r"\b\w+\b", text)
    if not words:
        return 0.0
    long_ratio = len(_LONG_WORD.findall(text)) / len(words)
    return min(1.0, long_ratio * 4.0)  # 25% long words → 1.0


def _numeric_proximity(options: list[dict]) -> float:
    """If options are numeric, return how close together they are.

    Closer values → harder to discriminate → higher difficulty.
    Returns 0..1.
    """
    if not options or len(options) < 2:
        return 0.0
    nums: list[float] = []
    for o in options:
        text = (o.get("text") or "").strip() if isinstance(o, dict) else ""
        m = _NUM_RE.search(text)
        if not m:
            continue
        try:
            tok = m.group(0)
            if "/" in tok:
                num, den = tok.split("/", 1)
                nums.append(float(num) / float(den))
            else:
                nums.append(float(tok))
        except (ValueError, ZeroDivisionError):
            continue
    if len(nums) < 2:
        return 0.0
    nums = sorted(nums)
    gaps = [nums[i + 1] - nums[i] for i in range(len(nums) - 1) if nums[i + 1] != nums[i]]
    if not gaps:
        return 1.0  # all identical → trap-tight
    span = max(nums) - min(nums)
    if span == 0:
        return 1.0
    rel_min_gap = min(gaps) / span
    # rel_min_gap of 0.05 → 0.95 score; 0.5 → 0.5 score
    return max(0.0, min(1.0, 1.0 - rel_min_gap * 1.5))


def _section_bonus(section: str | None, question_type: str | None, payload: dict) -> float:
    text = (payload.get("question_text") or "")
    bonus = 0.0
    if section == "DI":
        if question_type == "DI_MSR":
            bonus += 0.15
        if question_type == "DI_TPA":
            bonus += 0.10
    if question_type == "DI_DS":
        bonus += 0.10 + min(0.15, len(_CONDITIONAL_RE.findall(text)) * 0.03)
    if section == "VERBAL" and question_type == "V_RC":
        # RC difficulty correlates with passage length.
        passage_len = len(text)
        bonus += min(0.20, passage_len / 4000.0)
    return bonus


def _score(payload: dict) -> tuple[float, list[str]]:
    reasons: list[str] = []
    explanation = payload.get("explanation") or ""
    steps = _count_steps(explanation)
    text = payload.get("question_text") or ""
    options = payload.get("options") or []

    step_score = min(1.0, steps / 12.0)
    reasons.append(f"reasoning_steps={steps} (score {step_score:.2f})")

    vocab_score = _vocab_complexity(text + " " + explanation)
    reasons.append(f"vocab_complexity={vocab_score:.2f}")

    proximity = _numeric_proximity(options if isinstance(options, list) else [])
    reasons.append(f"numeric_proximity={proximity:.2f}")

    qlen = len(text)
    length_score = min(1.0, qlen / 1200.0)
    reasons.append(f"question_text_chars={qlen} (length_score {length_score:.2f})")

    bonus = _section_bonus(payload.get("section"), payload.get("question_type"), payload)
    reasons.append(f"section_bonus={bonus:.2f}")

    composite = (
        step_score * 0.35
        + vocab_score * 0.20
        + proximity * 0.15
        + length_score * 0.15
        + bonus * 0.15
    )
    return composite, reasons


def _composite_to_level(c: float) -> int:
    # 0..1 → 1..5 with a slight S-curve so the middle band is wider.
    # x = 0.5 → ~3, x = 0.2 → ~2, x = 0.8 → ~4, x = 1.0 → 5.
    shaped = 0.5 + 0.5 * math.tanh((c - 0.5) * 3.0)
    return max(1, min(5, round(1 + shaped * 4)))


def estimate(payload: dict) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"estimate": None, "confidence": 0.0, "reasons": ["payload must be an object"]}
    composite, reasons = _score(payload)
    level = _composite_to_level(composite)
    declared = payload.get("difficulty_level")
    delta = None
    if isinstance(declared, int) and 1 <= declared <= 5:
        delta = abs(declared - level)
    # Confidence is a function of how distinct the inputs were:
    # short explanation + no options → low confidence.
    expl_len = len(payload.get("explanation") or "")
    opts_n = len(payload.get("options") or [])
    confidence = min(1.0, expl_len / 600.0) * (0.5 + 0.5 * (opts_n >= 4))
    out = {
        "estimate": level,
        "composite_score": round(composite, 3),
        "confidence": round(confidence, 2),
        "declared_difficulty": declared,
        "delta_from_declared": delta,
        "reasons": reasons,
    }
    log.info(
        "difficulty estimate=%s composite=%.3f declared=%s delta=%s",
        level, composite, declared, delta,
    )
    return out


INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "payload": {
            "type": "object",
            "description": "Candidate question JSON. Same shape as validate_question_payload accepts.",
            "additionalProperties": True,
        }
    },
    "required": ["payload"],
    "additionalProperties": False,
}

DESCRIPTION = (
    "Heuristically estimate a question's difficulty level (1-5) without an LLM. "
    "Uses reasoning-step count from the explanation, vocabulary complexity, numeric "
    "distractor proximity, question length, and section-specific markers. Returns the "
    "estimated level, a composite score (0-1), confidence (0-1), and the declared-vs-"
    "estimated delta. Use this to sanity-check generated items: if delta_from_declared > 1, "
    "consider regenerating."
)
