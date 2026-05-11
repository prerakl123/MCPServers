from tools import render_artifact


def test_chart_bar():
    out = render_artifact.render("chart", {
        "type": "bar",
        "title": "Quant accuracy by domain",
        "x_labels": ["Arithmetic", "Algebra"],
        "series": [{"name": "Accuracy", "values": [78, 65]}],
        "ylabel": "%",
    })
    assert out["ok"]
    assert out["format"] == "image/png"
    assert out["bytes"] > 1000


def test_chart_radar_axes_mismatch():
    out = render_artifact.render("chart", {
        "type": "radar",
        "x_labels": ["A", "B", "C", "D"],
        "series": [{"name": "X", "values": [1, 2, 3]}],  # wrong length
    })
    assert not out["ok"]


def test_unknown_kind():
    out = render_artifact.render("video", {})
    assert not out["ok"]


def test_markdown_table():
    out = render_artifact.render("markdown_table", {
        "headers": ["Section", "Accuracy", "Avg Time"],
        "align": ["left", "right", "right"],
        "rows": [
            ["Quant", 72.0, 118],
            ["Verbal", 50.0, 142],
        ],
    })
    assert out["ok"]
    md = out["markdown"]
    assert "Section" in md
    assert "Quant" in md
    assert "| ---: |" in md  # right-aligned column
