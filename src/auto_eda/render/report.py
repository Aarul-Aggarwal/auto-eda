"""Markdown report (--report flag)."""

from __future__ import annotations

from pathlib import Path

from ..cleaning import AppliedFix
from ..findings import Finding
from ..llm.ranker import RankResult
from ..profiling import DatasetProfile
from ..quality import QualityScore, band_word


def _bar(score: float, width: int = 20) -> str:
    filled = max(0, min(width, int(round(score / 100 * width))))
    return "█" * filled + "░" * (width - filled)


def _quality_section(before: QualityScore, after: QualityScore | None) -> list[str]:
    current = after or before
    headline = f"**{current.overall:.0f} / 100 — {current.grade}** ({band_word(current.overall)})"
    if after is not None:
        delta = after.overall - before.overall
        headline += f"  ·  was {before.overall:.0f} ({before.grade}), {'+' if delta >= 0 else ''}{delta:.0f} after cleaning"

    lines = ["## Data quality score", "", headline, "", "_Deterministic — computed without an LLM._", ""]
    lines += ["| Dimension | Score | | Basis |", "|---|---:|---|---|"]
    for d in current.dimensions:
        lines.append(f"| {d.name} | {d.score:.0f} | `{_bar(d.score)}` | {d.detail} |")
    lines.append("")
    return lines


def write_report(
    result: RankResult,
    profile: DatasetProfile,
    applied: list[AppliedFix],
    source: Path,
    out_path: Path,
    target: str | None,
    quality_before: QualityScore,
    quality_after: QualityScore | None = None,
) -> None:
    lines = [
        f"# auto-eda report — {source.name}",
        "",
        f"- **Rows:** {profile.n_rows:,}  |  **Columns:** {profile.n_cols}",
        f"- **Target column:** {target or 'not specified'}",
        f"- **Ranking:** {'LLM (' + (result.provider_name or '') + ')' if result.used_llm else 'heuristic'}",
        "",
    ]
    lines += _quality_section(quality_before, quality_after)
    lines += [
        "## Ranked findings",
        "",
    ]
    for i, f in enumerate(result.findings, 1):
        lines.append(f"### {i}. {f.title}")
        if f.narrative:
            lines.append(f"> {f.narrative}")
        lines.append(
            f"- kind: `{f.kind}` | severity: {f.severity:.2f} | "
            f"affected: {f.affected_rows:,} rows ({f.affected_pct:.1%})"
        )
        if f.evidence:
            lines.append(f"- evidence: `{f.evidence}`")
        lines.append("")

    lines += ["## Cleaning fixes applied", ""]
    if applied:
        for a in applied:
            lines.append(f"- **{a.transform}**: {a.finding.proposed_fix.description}")
    else:
        lines.append("_None applied._")

    lines += [
        "",
        "## Column overview",
        "",
        "| Column | Type | Missing | Unique |",
        "|---|---|---:|---:|",
    ]
    for name, col in profile.columns.items():
        pct = col.n_missing / max(profile.n_rows, 1)
        lines.append(f"| {name} | {col.inferred_type} | {pct:.1%} | {col.n_unique:,} |")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
