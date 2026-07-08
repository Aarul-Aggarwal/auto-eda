"""auto-eda CLI: analyze a CSV end-to-end.

Pipeline: ingest -> profile -> detect -> propose/apply fixes -> re-profile ->
EDA -> rank (LLM or heuristic) -> render (terminal + charts.html [+ report.md]).
The input CSV is never modified.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.prompt import Confirm

from . import cleaning, detectors, eda, profiling
from .config import DEFAULT_CONFIG
from .findings import score_findings
from .ingest import load_csv
from .llm.provider import resolve_provider
from .llm.ranker import RankResult, rank
from .render import charts, report, terminal

app = typer.Typer(help="Automated data cleaning + EDA with LLM-prioritized findings.")


@app.callback()
def _main() -> None:
    """auto-eda: point it at a CSV, get a ranked list of what matters."""


@app.command()
def analyze(
    csv_path: Path = typer.Argument(..., help="Path to the raw CSV (opened read-only)"),
    target: Optional[str] = typer.Option(None, "--target", "-t", help="Target column for class-balance analysis"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Apply all proposed cleaning fixes without prompting"),
    no_clean: bool = typer.Option(False, "--no-clean", help="Report only; never apply fixes"),
    report_flag: bool = typer.Option(False, "--report", help="Also write a markdown report"),
    no_llm: bool = typer.Option(False, "--no-llm", help="Skip LLM ranking, use heuristic order"),
    out_dir: Path = typer.Option(Path("auto_eda_out"), "--out", "-o", help="Output directory for all artifacts"),
) -> None:
    """Analyze a CSV: detect issues, propose/apply fixes, run EDA, rank what matters."""
    config = DEFAULT_CONFIG
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Ingest (read-only) + profile
    ingest = load_csv(csv_path, config)
    terminal.show_banner(ingest.path, ingest.total_rows, len(ingest.df.columns), ingest.sampled)

    prof = profiling.profile(ingest.df, config)
    if target is not None and target not in prof.columns:
        terminal.console.print(f"[red]Target column '{target}' not found; ignoring.[/red]")
        target = None

    # 2. Detect issues on the raw data
    raw_findings = score_findings(detectors.run_all(ingest.df, prof, config), config)

    # 3. Propose + optionally apply cleaning fixes
    fixes = cleaning.plan_fixes(raw_findings)
    terminal.show_proposed_fixes(fixes)
    applied: list[cleaning.AppliedFix] = []
    df = ingest.df
    artifacts: list[Path] = []

    do_apply = bool(fixes) and not no_clean and (yes or Confirm.ask("Apply these fixes?", default=True))
    if do_apply:
        df, applied = cleaning.apply_fixes(ingest.df, fixes, config)
        cleaned_path = out_dir / f"{csv_path.stem}_cleaned.csv"
        script_path = out_dir / "cleaning_script.py"
        df.to_csv(cleaned_path, index=False)
        script_path.write_text(
            cleaning.generate_script(
                applied, ingest.path, cleaned_path, ingest.encoding, ingest.delimiter, config
            ),
            encoding="utf-8",
        )
        terminal.show_applied(applied, cleaned_path, script_path)
        artifacts += [cleaned_path, script_path]
        prof = profiling.profile(df.astype(str).where(df.notna()), config)

    # 4. EDA on the (possibly cleaned) data
    all_findings = raw_findings + score_findings(eda.analyze(prof, target, config), config)
    all_findings = sorted(all_findings, key=lambda f: f.severity, reverse=True)

    # 5. Rank: LLM if available, heuristic otherwise
    provider = None if no_llm else resolve_provider(config)
    if not no_llm:
        terminal.show_llm_status(provider.name if provider else None)
    result: RankResult = rank(all_findings, prof, provider, target, config)

    # 6. Render
    charts_path = out_dir / "charts.html"
    n_charts = charts.write_charts(result.findings, prof, charts_path, config)
    artifacts.append(charts_path)

    if report_flag:
        report_path = out_dir / "report.md"
        report.write_report(result, prof, applied, ingest.path, report_path, target)
        artifacts.append(report_path)

    terminal.show_ranked_findings(result)
    terminal.console.print(f"[dim]{n_charts} charts written for top findings[/dim]")
    terminal.show_artifacts(artifacts)


if __name__ == "__main__":
    app()
