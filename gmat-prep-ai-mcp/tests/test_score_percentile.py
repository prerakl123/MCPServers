from tools import score_percentile


def test_total_known_anchor():
    out = score_percentile.lookup(615, "total")
    assert out["ok"]
    assert out["percentile"] == 61


def test_total_interpolation():
    # 620 is between 615 (61) and 625 (66) → expect ~63-64
    out = score_percentile.lookup(620, "total")
    assert out["ok"]
    assert 62 <= out["percentile"] <= 65


def test_section_lookup():
    out = score_percentile.lookup(84, "QUANT")
    assert out["ok"]
    assert out["percentile"] == 90


def test_out_of_range():
    out = score_percentile.lookup(50, "QUANT")
    assert out["ok"]
    assert out["out_of_range"]
    assert out["percentile"] is None


def test_unknown_section():
    out = score_percentile.lookup(700, "XYZ")
    assert not out["ok"]
