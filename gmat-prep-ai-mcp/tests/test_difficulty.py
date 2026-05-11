from tools import difficulty


def _easy() -> dict:
    return {
        "section": "QUANT",
        "question_type": "Q_PURE_CONTEXT",
        "difficulty_level": 1,
        "question_text": "What is 2 + 2?",
        "options": [
            {"label": "A", "text": "3"},
            {"label": "B", "text": "4"},
            {"label": "C", "text": "5"},
            {"label": "D", "text": "6"},
            {"label": "E", "text": "7"},
        ],
        "correct_answer": "B",
        "explanation": "Add. The answer is 4.",
    }


def _hard() -> dict:
    return {
        "section": "QUANT",
        "question_type": "Q_REAL_CONTEXT",
        "difficulty_level": 5,
        "question_text": (
            "A merchant marks an article 50% above cost. After offering a successive discount of 10% "
            "and 20%, the merchant still profits by what percentage? Carefully consider every step "
            "and any compounding effects between successive discounts and the original markup."
        ),
        "options": [
            {"label": "A", "text": "8"},
            {"label": "B", "text": "8.5"},
            {"label": "C", "text": "9"},
            {"label": "D", "text": "9.5"},
            {"label": "E", "text": "10"},
        ],
        "correct_answer": "A",
        "explanation": (
            "Step 1: Let cost = 100. Step 2: Marked price = 150. Step 3: After 10% discount = 135. "
            "Step 4: After further 20% discount = 108. Step 5: Therefore profit = 8%. Notice that "
            "successive discounts compound multiplicatively. Hence the answer is A."
        ),
    }


def test_easy_estimates_low():
    out = difficulty.estimate(_easy())
    assert out["estimate"] <= 3, out


def test_hard_estimates_high():
    out = difficulty.estimate(_hard())
    assert out["estimate"] >= 3, out


def test_relative_ordering():
    e = difficulty.estimate(_easy())["composite_score"]
    h = difficulty.estimate(_hard())["composite_score"]
    assert h > e
