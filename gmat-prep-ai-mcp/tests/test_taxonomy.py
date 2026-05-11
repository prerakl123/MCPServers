from tools import taxonomy


def test_lookup_all():
    out = taxonomy.lookup("all")
    assert "sections" in out
    assert "question_types" in out
    assert any(s["code"] == "QUANT" for s in out["sections"])


def test_filter_by_section():
    out = taxonomy.lookup("question_types", section="QUANT")
    codes = [it["code"] for it in out["items"]]
    assert "Q_PURE_CONTEXT" in codes
    assert "V_CR" not in codes


def test_exact_code():
    out = taxonomy.lookup("Q_RATES_RATIOS_PERCENT")
    assert out["bucket"] == "fundamental_skills"
    assert out["item"]["code"] == "Q_RATES_RATIOS_PERCENT"


def test_unknown_query():
    out = taxonomy.lookup("nonsense")
    assert "error" in out
    assert "supported" in out
