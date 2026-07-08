# auto-eda

**Automated data cleaning + EDA that tells you what actually matters.**

Point it at a raw CSV. It detects data-quality issues deterministically, proposes
(and, on confirmation, applies) cleaning fixes to a *new* file, runs standard EDA,
and uses an LLM to turn the results into a short, **ranked** list of findings —
instead of the wall-of-stats dump that tools like ydata-profiling produce.

```
auto-eda analyze data.csv --target churn --report
```

## What makes it different

- **Ranked, not exhaustive.** Every check emits a structured `Finding`; a
  deterministic severity heuristic orders them, and an LLM (if available)
  re-ranks and writes a one-line "why it matters" for each. Charts are generated
  only for the top findings.
- **The LLM never computes anything.** All statistics, detection, and transforms
  are plain pandas/numpy. The LLM sees only a JSON summary — schema, aggregates,
  ≤10 sample values per column — never your data.
- **Fully functional without an LLM.** Provider resolution:
  `ANTHROPIC_API_KEY` → local [Ollama](https://ollama.com) server → heuristic
  ranking with a clear "no LLM detected" notice.
- **Your original file is never touched.** Fixes write `<name>_cleaned.csv` plus
  a standalone, reproducible `cleaning_script.py` (plain pandas) that regenerates
  the cleaned file from the original.

## Install

```
pip install -e .
```

## Usage

```
auto-eda analyze data.csv                 # detect, propose fixes, rank, chart
auto-eda analyze data.csv --yes           # apply all proposed fixes
auto-eda analyze data.csv --no-clean      # diagnostic only
auto-eda analyze data.csv --target churn  # adds class-balance analysis
auto-eda analyze data.csv --report        # also writes report.md
auto-eda analyze data.csv --no-llm        # force heuristic ranking
auto-eda analyze data.csv -o results/     # output directory (default auto_eda_out/)
```

Outputs (all in the output directory):

| Artifact | When |
|---|---|
| `charts.html` | always — plotly charts for the top-ranked findings |
| `<name>_cleaned.csv` | when fixes are applied |
| `cleaning_script.py` | when fixes are applied — reproduces the cleaned CSV |
| `report.md` | with `--report` |

## What it detects

Duplicates, true and disguised nulls (`"N/A"`, `"-"`, `"?"`, …), numeric/date
values stored as text, mixed-type columns, stray whitespace, casing variants of
the same category (`NY`/`ny`/`New York`), outliers (IQR ∩ modified z-score),
constant columns, ID-like columns, near-duplicate correlated pairs, heavy skew,
and class imbalance (with `--target`).

## LLM setup (optional)

```
# Tier 1: Anthropic API
export ANTHROPIC_API_KEY=sk-ant-...

# Tier 2: local model, no key needed
ollama pull llama3.2 && ollama serve

# Tier 3: nothing — heuristic ranking, everything still works
```

## Try the demo

```
python examples/make_messy.py
auto-eda analyze examples/messy.csv --target churn --yes --report
```

## Development

```
pip install -e ".[dev]"
pytest
```
