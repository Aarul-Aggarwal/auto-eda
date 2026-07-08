"""Plotly charts.html for the top-N ranked findings.

Charts follow the ranking, not the schema — one chart per top finding that has
something visual to show, never one chart per column. Colors come from a
CVD-validated palette; identity is single-hue (no rainbow), and text stays in
ink tokens rather than series colors.
"""

from __future__ import annotations

import html
from pathlib import Path

import plotly.graph_objects as go

from ..config import Config, DEFAULT_CONFIG
from ..findings import Finding
from ..profiling import DatasetProfile
from ..quality import QualityScore

# Validated reference palette (light mode)
SERIES_1 = "#2a78d6"  # primary series hue
SERIES_2 = "#1baf7a"
CRITICAL = "#d03b3b"  # status: outlier marks
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'

_LAYOUT = dict(
    paper_bgcolor=SURFACE,
    plot_bgcolor=SURFACE,
    font=dict(family=FONT, color=INK, size=13),
    margin=dict(l=60, r=30, t=60, b=50),
    height=360,
    xaxis=dict(gridcolor=GRIDLINE, zerolinecolor=GRIDLINE, tickfont=dict(color=INK_MUTED)),
    yaxis=dict(gridcolor=GRIDLINE, zerolinecolor=GRIDLINE, tickfont=dict(color=INK_MUTED)),
    showlegend=False,
)


def _fig_for(finding: Finding, profile: DatasetProfile) -> go.Figure | None:
    cols = [c for c in finding.columns if c in profile.columns]
    col = profile.columns[cols[0]] if cols else None

    if finding.kind in ("outliers", "skewed_distribution") and col and col.parsed is not None:
        s = col.parsed.dropna()
        fig = go.Figure(go.Histogram(x=s, marker_color=SERIES_1, marker_line_width=0))
        if finding.kind == "outliers":
            lo, hi = finding.evidence.get("fences", [None, None])
            for fence in (lo, hi):
                if fence is not None:
                    fig.add_vline(x=fence, line_color=CRITICAL, line_dash="dash", line_width=2)
        fig.update_layout(title=finding.title, **_LAYOUT)
        return fig

    if finding.kind == "class_imbalance":
        counts = finding.evidence.get("class_counts", {})
        fig = go.Figure(
            go.Bar(
                x=list(counts.keys()), y=list(counts.values()),
                marker_color=SERIES_1, marker_line_width=0,
                text=[f"{v:,}" for v in counts.values()], textposition="outside",
                textfont=dict(color=INK),
            )
        )
        fig.update_layout(title=finding.title, **_LAYOUT)
        return fig

    if finding.kind in ("missing_values", "disguised_nulls") and col is not None:
        present = col.n_rows - col.n_missing
        fig = go.Figure(
            go.Bar(
                x=["present", "missing"], y=[present, col.n_missing],
                marker_color=[SERIES_1, CRITICAL], marker_line_width=0,
                text=[f"{present:,}", f"{col.n_missing:,}"], textposition="outside",
                textfont=dict(color=INK),
            )
        )
        fig.update_layout(title=finding.title, **_LAYOUT)
        return fig

    if finding.kind == "case_inconsistency" and col is not None:
        counts = col.raw.dropna().str.strip().value_counts().head(12)
        fig = go.Figure(
            go.Bar(
                y=[str(k) for k in counts.index][::-1], x=list(counts.values)[::-1],
                orientation="h", marker_color=SERIES_1, marker_line_width=0,
            )
        )
        fig.update_layout(title=finding.title, **_LAYOUT)
        return fig

    if finding.kind == "high_correlation" and len(cols) == 2:
        a, b = profile.columns[cols[0]], profile.columns[cols[1]]
        if a.parsed is not None and b.parsed is not None:
            fig = go.Figure(
                go.Scattergl(
                    x=a.parsed, y=b.parsed, mode="markers",
                    marker=dict(color=SERIES_1, size=8, opacity=0.6, line=dict(width=0)),
                )
            )
            layout = dict(_LAYOUT)
            layout["xaxis"] = {**_LAYOUT["xaxis"], "title": dict(text=cols[0], font=dict(color=INK_MUTED))}
            layout["yaxis"] = {**_LAYOUT["yaxis"], "title": dict(text=cols[1], font=dict(color=INK_MUTED))}
            fig.update_layout(title=finding.title, **layout)
            return fig

    return None  # duplicates, whitespace, type casts etc. have nothing useful to plot


def _score_hue(score: float) -> str:
    if score >= 90:
        return SERIES_2  # green
    if score >= 75:
        return "#a8b023"
    if score >= 60:
        return "#c99a1e"
    return CRITICAL


def _quality_badge(quality: QualityScore | None) -> str:
    if quality is None:
        return ""
    hue = _score_hue(quality.overall)
    dims = "".join(
        f'<div class="dim"><span class="dname">{html.escape(d.name)}</span>'
        f'<span class="dbar"><span style="width:{d.score:.0f}%;background:{_score_hue(d.score)}"></span></span>'
        f'<span class="dscore">{d.score:.0f}</span></div>'
        for d in quality.dimensions
    )
    return (
        f'<section class="score" style="border-color:{hue}">'
        f'<div class="grade" style="color:{hue}">{quality.grade}'
        f'<span class="gnum">{quality.overall:.0f}/100</span></div>'
        f'<div class="dims">{dims}</div></section>'
    )


def write_charts(
    findings: list[Finding],
    profile: DatasetProfile,
    out_path: Path,
    quality: QualityScore | None = None,
    config: Config = DEFAULT_CONFIG,
) -> int:
    """Write charts.html for the top-N findings; returns the number of charts."""
    sections: list[str] = []
    n_charts = 0
    include_js = True
    for f in findings:
        if n_charts >= config.top_n_charts:
            break
        fig = _fig_for(f, profile)
        if fig is None:
            continue
        body = fig.to_html(full_html=False, include_plotlyjs="inline" if include_js else False)
        include_js = False
        note = html.escape(f.narrative) if f.narrative else ""
        sections.append(
            f'<section class="chart"><div class="rank">#{n_charts + 1}</div>{body}'
            f'<p class="note">{note}</p></section>'
        )
        n_charts += 1

    doc = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>auto-eda charts</title>
<style>
  body {{ background: #f9f9f7; color: {INK}; font-family: {FONT};
         max-width: 900px; margin: 0 auto; padding: 24px; }}
  h1 {{ font-size: 20px; }} .sub {{ color: #52514e; font-size: 14px; }}
  .chart {{ background: {SURFACE}; border: 1px solid rgba(11,11,11,0.10);
            border-radius: 8px; padding: 8px 16px; margin: 20px 0; position: relative; }}
  .rank {{ position: absolute; top: 12px; left: 16px; color: {INK_MUTED};
           font-size: 13px; font-weight: 600; z-index: 5; }}
  .note {{ color: #52514e; font-size: 14px; margin: 4px 8px 12px; }}
  .score {{ display: flex; align-items: center; gap: 24px; background: {SURFACE};
            border: 2px solid {INK_MUTED}; border-radius: 8px; padding: 16px 20px; margin: 20px 0; }}
  .grade {{ font-size: 44px; font-weight: 700; line-height: 1; }}
  .gnum {{ display: block; font-size: 13px; font-weight: 500; color: {INK_MUTED}; margin-top: 4px; }}
  .dims {{ flex: 1; }}
  .dim {{ display: flex; align-items: center; gap: 10px; font-size: 13px; margin: 3px 0; }}
  .dname {{ width: 110px; color: #52514e; }}
  .dbar {{ flex: 1; height: 8px; background: {GRIDLINE}; border-radius: 4px; overflow: hidden; }}
  .dbar span {{ display: block; height: 100%; }}
  .dscore {{ width: 28px; text-align: right; color: {INK}; font-variant-numeric: tabular-nums; }}
</style></head><body>
<h1>auto-eda — top findings</h1>
<p class="sub">Deterministic data-quality score, then charts for the highest-ranked findings only.
Full list in the terminal output or report.</p>
{_quality_badge(quality)}
{"".join(sections) if sections else "<p>No chartable findings.</p>"}
</body></html>"""
    out_path.write_text(doc, encoding="utf-8")
    return n_charts
