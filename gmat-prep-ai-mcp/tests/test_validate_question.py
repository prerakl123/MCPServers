from tools import validate_question


def _good_quant_question() -> dict:
    return {
        "section": "QUANT",
        "content_domain": "Q_ARITHMETIC",
        "question_type": "Q_REAL_CONTEXT",
        "fundamental_skill": "Q_RATES_RATIOS_PERCENT",
        "difficulty_level": 3,
        "answer_format": "single_choice",
        "question_text": "A train travels 60 miles in 1 hour. How many miles does it travel in 90 minutes at the same rate?",
        "options": [
            {"label": "A", "text": "70"},
            {"label": "B", "text": "80"},
            {"label": "C", "text": "90"},
            {"label": "D", "text": "100"},
            {"label": "E", "text": "120"},
        ],
        "correct_answer": "C",
        "explanation": "60 mph × 1.5 hours = 90 miles.",
        "topic_tags": ["rate", "unit-conversion"],
    }


def test_valid_quant_passes():
    out = validate_question.validate(_good_quant_question())
    assert out["valid"], out["errors"]


def test_section_qt_mismatch():
    q = _good_quant_question()
    q["question_type"] = "V_CR"
    out = validate_question.validate(q)
    assert not out["valid"]
    assert any("mismatch" in e for e in out["errors"])


def test_correct_answer_not_in_options():
    q = _good_quant_question()
    q["correct_answer"] = "F"
    out = validate_question.validate(q)
    assert not out["valid"]


def test_di_with_skill_rejected():
    q = _good_quant_question()
    q["section"] = "DI"
    q["question_type"] = "DI_DS"
    q["content_domain"] = None
    out = validate_question.validate(q)
    # Should fail because DI requires fundamental_skill = null
    assert not out["valid"]
    assert any("DI questions must have fundamental_skill" in e for e in out["errors"])


def test_two_part_correct_answer_format():
    q = {
        "section": "DI",
        "content_domain": None,
        "question_type": "DI_TPA",
        "fundamental_skill": None,
        "difficulty_level": 4,
        "answer_format": "two_part",
        "question_text": "Select one value from each column that satisfies the constraints described in the prompt for two-part analysis.",
        "answer_payload": {
            "columns": ["Min value", "Max value"],
            "rows": [
                {"label": "10", "value": "10"},
                {"label": "20", "value": "20"},
                {"label": "30", "value": "30"},
            ],
        },
        "correct_answer": "10|30",
        "explanation": "Pick smallest for min, largest for max.",
        "topic_tags": ["min-max"],
    }
    out = validate_question.validate(q)
    assert out["valid"], out["errors"]


def test_inline_dropdown_invalid_slot():
    q = {
        "section": "DI",
        "content_domain": "DI_NON_MATH",
        "question_type": "DI_GT",
        "fundamental_skill": None,
        "difficulty_level": 3,
        "answer_format": "inline_dropdown",
        "question_text": "Sales rose by {{slot1}} from {{slot2}} to 2023, sample sentence with two dropdowns.",
        "answer_payload": {
            "template": "Sales rose by {{slot1}} from {{slot2}} to 2023.",
            "slots": {"slot1": ["10%", "20%"], "slot2": ["2020", "2021"]},
        },
        "correct_answer": '{"slot1":"99%","slot2":"2020"}',  # 99% not in slot1 options
        "explanation": "Choose the matching values from the table.",
        "topic_tags": ["growth", "table"],
    }
    out = validate_question.validate(q)
    assert not out["valid"]
    assert any("not in declared options" in e for e in out["errors"])
