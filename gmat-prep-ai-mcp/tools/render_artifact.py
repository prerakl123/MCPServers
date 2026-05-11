"""render_artifact MCP tool.

Single tool, two ``kind``s: ``chart`` (matplotlib → PNG) and
``markdown_table`` (deterministic markdown rendering). Used inside FLT
analysis text and Phase 6 insights.

The ``chart`` spec is intentionally a small DSL — the model picks a chart
type and supplies series, no custom matplotlib code. This makes the output
deterministic and avoids round-tripping through ``code_interpreter`` for
the common cases.
"""
from __future__ import annotations

import base64
import io
import uuid
from pathlib import Path
from typing import Any

from ._logging import get_logger

log = get_logger("render_artifact")

_OUT_DIR = Path(__file__).resolve().parents[1] / "logs" / "artifacts"
_OUT_DIR.mkdir(parents=True, exist_ok=True)

# Chart kinds are limited to the ones we actually need. New kinds can be added
# without expanding the tool surface to the model.
_SUPPORTED_CHARTS = {"bar", "horizontal_bar", "line", "scatter", "stacked_bar", "radar"}


def _render_chart(spec: dict) -> dict[str, Any]:
    import matplotlib  # type: ignore
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # type: ignore
    import numpy as np  # type: ignore

    chart_type = spec.get("type")
    if chart_type not in _SUPPORTED_CHARTS:
        return {
            "ok": False,
            "error": f"unsupported chart type {chart_type!r}; supported: {sorted(_SUPPORTED_CHARTS)}",
        }

    title = spec.get("title") or ""
    x_labels = spec.get("x_labels") or []
    series = spec.get("series") or []
    if not isinstance(series, list) or not series:
        return {"ok": False, "error": "series must be a non-empty list"}

    fig, ax = plt.subplots(figsize=tuple(spec.get("figsize") or (8, 5)), dpi=120)

    try:
        if chart_type == "bar":
            x = np.arange(len(x_labels))
            width = 0.8 / max(1, len(series))
            for i, s in enumerate(series):
                ax.bar(x + i * width, s.get("values", []), width=width, label=s.get("name", f"Series {i+1}"))
            ax.set_xticks(x + width * (len(series) - 1) / 2)
            ax.set_xticklabels(x_labels, rotation=15, ha="right")
        elif chart_type == "horizontal_bar":
            y = np.arange(len(x_labels))
            for s in series[:1]:  # horizontal_bar uses first series only
                ax.barh(y, s.get("values", []), color=s.get("color"))
            ax.set_yticks(y)
            ax.set_yticklabels(x_labels)
            ax.invert_yaxis()
        elif chart_type == "line":
            for s in series:
                ax.plot(x_labels or range(len(s.get("values", []))), s.get("values", []), marker="o", label=s.get("name", ""))
        elif chart_type == "scatter":
            for s in series:
                ax.scatter(s.get("x", []), s.get("y", []), label=s.get("name", ""))
        elif chart_type == "stacked_bar":
            x = np.arange(len(x_labels))
            bottom = np.zeros(len(x_labels))
            for s in series:
                vals = np.array(s.get("values", []), dtype=float)
                ax.bar(x, vals, bottom=bottom, label=s.get("name", ""))
                bottom += vals
            ax.set_xticks(x)
            ax.set_xticklabels(x_labels, rotation=15, ha="right")
        elif chart_type == "radar":
            n = len(x_labels)
            if n < 3:
                return {"ok": False, "error": "radar requires >= 3 axes"}
            angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
            angles += angles[:1]
            ax.remove()
            ax = fig.add_subplot(111, polar=True)
            for s in series:
                vals = list(s.get("values", []))
                if len(vals) != n:
                    return {"ok": False, "error": f"radar series length {len(vals)} != axes {n}"}
                vals += vals[:1]
                ax.plot(angles, vals, label=s.get("name", ""))
                ax.fill(angles, vals, alpha=0.1)
            ax.set_xticks(angles[:-1])
            ax.set_xticklabels(x_labels)
        ax.set_title(title)
        if any(s.get("name") for s in series) and chart_type != "horizontal_bar":
            ax.legend(loc="best", fontsize=8)

        if chart_type != "radar":
            ax.set_xlabel(spec.get("xlabel") or "")
            ax.set_ylabel(spec.get("ylabel") or "")
            ax.grid(True, axis="y", alpha=0.25)

        png_bytes = io.BytesIO()
        fig.savefig(png_bytes, format="png", bbox_inches="tight")
        plt.close(fig)
        data = png_bytes.getvalue()
    except Exception as exc:  # noqa: BLE001
        plt.close(fig)
        log.exception("chart render failed: %s", exc)
        return {"ok": False, "error": f"render failed: {exc}"}

    out_path = _OUT_DIR / f"chart_{uuid.uuid4().hex[:12]}.png"
    out_path.write_bytes(data)
    encoded = base64.b64encode(data).decode("ascii")
    log.info("chart rendered type=%s bytes=%d path=%s", chart_type, len(data), out_path)
    return {
        "ok": True,
        "kind": "chart",
        "format": "image/png",
        "path": str(out_path),
        "base64": encoded,
        "bytes": len(data),
    }


def _render_table(spec: dict) -> dict[str, Any]:
    headers = spec.get("headers") or []
    rows = spec.get("rows") or []
    if not isinstance(headers, list) or not isinstance(rows, list):
        return {"ok": False, "error": "headers and rows must be lists"}
    align = spec.get("align") or ["left"] * len(headers)

    def _align(a: str) -> str:
        return {"left": ":---", "right": "---:", "center": ":---:"}.get(a, ":---")

    lines: list[str] = []
    if headers:
        lines.append("| " + " | ".join(str(h) for h in headers) + " |")
        lines.append("| " + " | ".join(_align(a) for a in align) + " |")
    for row in rows:
        if not isinstance(row, list):
            return {"ok": False, "error": "each row must be a list"}
        lines.append("| " + " | ".join(_to_cell(c) for c in row) + " |")

    md = "\n".join(lines)
    log.info("table rendered headers=%d rows=%d", len(headers), len(rows))
    return {"ok": True, "kind": "markdown_table", "format": "text/markdown", "markdown": md}


def _to_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value).replace("|", "\\|").replace("\n", " ")


def render(kind: str, spec: dict) -> dict[str, Any]:
    if not isinstance(spec, dict):
        return {"ok": False, "error": "spec must be an object"}
    if kind == "chart":
        return _render_chart(spec)
    if kind == "markdown_table":
        return _render_table(spec)
    return {"ok": False, "error": f"unknown kind {kind!r}; supported: chart, markdown_table"}


INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {
            "type": "string",
            "enum": ["chart", "markdown_table"],
            "description": "Artifact kind. 'chart' renders a PNG via matplotlib. 'markdown_table' produces a markdown-formatted table.",
        },
        "spec": {
            "type": "object",
            "description": (
                "For kind='chart': {type: 'bar'|'horizontal_bar'|'line'|'scatter'|'stacked_bar'|'radar', "
                "title?, x_labels?: [string], series: [{name?, values: [number], color?, x?, y?}], "
                "xlabel?, ylabel?, figsize?: [w, h]}. "
                "For kind='markdown_table': {headers: [string], rows: [[any]], align?: ['left'|'right'|'center']}."
            ),
            "additionalProperties": True,
        },
    },
    "required": ["kind", "spec"],
    "additionalProperties": False,
}

DESCRIPTION = (
    "Render a deterministic visualization artifact. kind='chart' returns a PNG (path on disk + base64) "
    "from a structured chart spec; supports bar/horizontal_bar/line/scatter/stacked_bar/radar. "
    "kind='markdown_table' returns a markdown table string. Use this when generating analysis text "
    "or insights that should embed real data visualizations rather than ASCII art."
)
