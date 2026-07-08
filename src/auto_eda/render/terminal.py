"""Rich terminal rendering: ranked findings, cleaning summary, artifact list."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..cleaning import AppliedFix
from ..findings import Finding
from ..llm.ranker import RankResult

console = Console()


def show_banner(path: Path, n_rows: int, n_cols: int, sampled: bool) -> None:
    note = " (profiling a sample)" if sampled else ""
    console.print(
        Panel(
            f"[bold]{path.name}[/bold] — {n_rows:,} rows x {n_cols} columns{note}",
            title="auto-eda",
            border_style="cyan",
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
        table.add_row(str(i), f.title, f.proposed_fix.description, f"{f.affected_rows:,}")
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
