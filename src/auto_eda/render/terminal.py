"""Rich terminal rendering: ranked findings, cleaning summary, artifact list."""

from __future__ import annotations

import sys
from pathlib import Path

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table

from ..cleaning import AppliedFix
from ..findings import Finding
from ..llm.ranker import RankResult
from ..quality import QualityScore, band_word

# The score gauge uses block-drawing glyphs (█ ░). Force UTF-8 so they never
# crash a cp1252 console, and stay off rich's legacy win32 writer (which encodes
# via the console code page) — ANSI works on every Windows 10+ terminal.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

console = Console(legacy_windows=False)


def show_banner(path: Path, n_rows: int, n_cols: int, sampled: bool) -> None:
    note = "  [yellow](profiling a sample)[/yellow]" if sampled else ""
    console.print()
    console.rule("[bold cyan]▁▂▃ auto-eda ▃▂▁[/bold cyan]", style="cyan")
    console.print(
        f"  [bold]{path.name}[/bold]  [dim]·[/dim]  "
        f"[cyan]{n_rows:,}[/cyan] rows [dim]×[/dim] [cyan]{n_cols}[/cyan] columns{note}\n"
    )


def _score_color(score: float) -> str:
    if score >= 90:
        return "green"
    if score >= 75:
        return "green_yellow"
    if score >= 60:
        return "yellow"
    if score >= 40:
        return "dark_orange"
    return "red"


def _bar(score: float, width: int = 22) -> str:
    filled = max(0, min(width, int(round(score / 100 * width))))
    color = _score_color(score)
    return f"[{color}]{'█' * filled}[/{color}][grey37]{'░' * (width - filled)}[/grey37]"


def show_quality_score(before: QualityScore, after: QualityScore | None = None) -> None:
    """Funky gauge for the deterministic data-quality score (before -> after)."""
    current = after or before
    color = _score_color(current.overall)

    header = (
        f"[bold {color}]{current.overall:.0f}[/bold {color}][{color}]/100[/{color}]"
        f"   [bold {color}]{current.grade}[/bold {color}]"
        f"   [dim]{band_word(current.overall)}[/dim]"
    )
    if after is not None:
        delta = after.overall - before.overall
        dcol = "green" if delta >= 0 else "red"
        arrow = "▲" if delta >= 0 else "▼"
        header += (
            f"      [dim]was {before.overall:.0f} {before.grade}[/dim]"
            f"   [{dcol}]{arrow} {abs(delta):.0f}[/{dcol}]"
        )

    before_scores = {d.name: d.score for d in before.dimensions}
    grid = Table.grid(padding=(0, 2))
    grid.add_column(justify="left")   # dimension
    grid.add_column()                 # bar
    grid.add_column(justify="right")  # score (+delta)
    grid.add_column(style="dim")      # detail
    for d in current.dimensions:
        score_cell = f"[{_score_color(d.score)}]{d.score:>3.0f}[/{_score_color(d.score)}]"
        if after is not None:
            diff = d.score - before_scores.get(d.name, d.score)
            if abs(diff) >= 0.5:
                dc = "green" if diff > 0 else "red"
                score_cell += f" [{dc}]{'+' if diff > 0 else ''}{diff:.0f}[/{dc}]"
        grid.add_row(f"[bold]{d.name}[/bold]", _bar(d.score), score_cell, d.detail)

    console.print(
        Panel(
            Group(header, "", grid),
            title="[bold]Data Quality Score[/bold]",
            subtitle="[dim]deterministic · no LLM[/dim]",
            border_style=color,
            padding=(1, 2),
        )
    )


def show_llm_status(provider_name: str | None) -> None:
    if provider_name == "anthropic":
        console.print("[green]LLM ranking: Anthropic API[/green]")
    elif provider_name == "ollama":
        console.print("[green]LLM ranking: local Ollama server[/green]")
    else:
        console.print(
            "[yellow]No LLM detected[/yellow] — set ANTHROPIC_API_KEY or run Ollama "
            "for LLM-prioritized results. Using heuristic ranking."
        )


def show_proposed_fixes(fixes: list[Finding]) -> None:
    if not fixes:
        console.print("[green]No cleaning fixes proposed — data looks structurally clean.[/green]")
        return
    table = Table(title="Proposed cleaning fixes", show_lines=False)
    table.add_column("#", justify="right", style="dim")
    table.add_column("Issue")
    table.add_column("Fix")
    table.add_column("Rows", justify="right")
    for i, f in enumerate(fixes, 1):
        table.add_row(str(i), f.title, f.proposed_fix.description, f"{f.affected_rows:,}") #type:ignore
    console.print(table)


def show_applied(applied: list[AppliedFix], cleaned_path: Path, script_path: Path) -> None:
    console.print(
        f"[green]Applied {len(applied)} fixes[/green] -> [bold]{cleaned_path}[/bold] "
        f"(original untouched)\nReproducible script: [bold]{script_path}[/bold]"
    )


def show_ranked_findings(result: RankResult, top_n: int = 15) -> None:
    title = "Ranked findings"
    title += " (LLM-prioritized)" if result.used_llm else " (heuristic order)"
    table = Table(title=title, show_lines=True)
    table.add_column("#", justify="right", style="dim", width=3)
    table.add_column("Finding", max_width=45)
    table.add_column("Why it matters", max_width=60)
    table.add_column("Severity", justify="right", width=8)

    for i, f in enumerate(result.findings[:top_n], 1):
        why = f.narrative or _default_why(f)
        table.add_row(str(i), f.title, why, f"{f.severity:.2f}")
    console.print(table)
    if len(result.findings) > top_n:
        console.print(f"[dim]... and {len(result.findings) - top_n} lower-priority findings[/dim]")
    if result.note:
        console.print(f"[yellow]{result.note}[/yellow]")


def _default_why(f: Finding) -> str:
    if f.affected_pct > 0:
        return f"Affects {f.affected_pct:.1%} of rows ({f.affected_rows:,})."
    return "Structural property of the dataset."


def show_artifacts(paths: list[Path]) -> None:
    lines = "\n".join(f"  - {p}" for p in paths)
    console.print(Panel(f"Artifacts written:\n{lines}", border_style="green"))
