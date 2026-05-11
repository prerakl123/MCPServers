from tools import parse_flt


def test_json_envelope():
    raw = '{"total":615,"quant":84,"verbal":82,"di":75}'
    out = parse_flt.parse(raw)
    assert out["ok"]
    assert out["matched_pattern"] == "json_envelope"
    assert out["scores"]["total_score"] == 615
    assert out["scores"]["di_score"] == 75


def test_mba_com_text():
    raw = """
    Your GMAT Focus Edition Score Report
    Total: 615
    Quant: 84
    Verbal: 82
    Data Insights: 75
    Quant 81 percentile
    Verbal 74 percentile
    DI 50 percentile
    """
    out = parse_flt.parse(raw)
    assert out["ok"]
    assert out["scores"]["total_score"] == 615
    assert out["scores"]["quant_score"] == 84
    assert out["percentiles"].get("quant") == 81
    assert out["percentiles"].get("verbal") == 74
    assert out["percentiles"].get("di") == 50


def test_ttp_summary():
    raw = "Score 645 | Q86 | V82 | DI80"
    out = parse_flt.parse(raw)
    assert out["ok"]
    assert out["scores"]["total_score"] == 645
    assert out["scores"]["quant_score"] == 86


def test_no_match():
    out = parse_flt.parse("nothing useful here")
    assert not out["ok"]
    assert "tried_patterns" in out
