# auto-eda

**Automated data cleaning + EDA that tells you what actually matters.**

Point it at a raw CSV. `auto-eda` detects data-quality issues deterministically,
scores the dataset's health, proposes (and, on confirmation, applies) cleaning
fixes to a *new* file, runs standard EDA, and turns the results into a short,
**ranked** list of findings — instead of the wall-of-stats dump that tools like
ydata-profiling produce.

```
auto-eda analyze data.csv --target churn --report
```

```
╭───────────────────────────── Data Quality Score ─────────────────────────────╮
│  99/100   A+   EXCELLENT      was 90 A-   ▲ 9                                 │
│                                                                              │
│  Completeness  █████████████████████░  97 +9   104 / 4,000 cells missing     │
│  Validity      ██████████████████████ 100      0 / 8 columns type-violating  │
│  Consistency   ██████████████████████ 100 +22  0 / 8 columns inconsistent    │
│  Uniqueness    ██████████████████████ 100 +3   no duplicate rows             │
│  Structure     ██████████████████████ 100 +11  0 / 8 columns redundant       │
╰─────────────────────────── deterministic · no LLM ───────────────────────────╯
```

## What makes it different

- **A quality score, before and after.** A deterministic 0–100 health grade
  (A+…F) across five dimensions — Completeness, Validity, Consistency,
  Uniqueness, Structure. Every number is a plain ratio you can reproduce by
  hand; no LLM involved. Apply fixes and the score is recomputed so you see the
  payoff (e.g. `90 A- → 99 A+`).
- **Ranked, not exhaustive.** Every check emits a structured `Finding`; a
  deterministic severity heuristic orders them, and an LLM (if available)
  re-ranks and writes a one-line "why it matters" for each. Charts are generated
  only for the top findings.
- **The LLM never computes anything.** All statistics, detection, scoring, and
  transforms are plain pandas/numpy. The LLM sees only a JSON summary — schema,
  aggregates, ≤10 sample values per column — never your data. Remove the LLM and
  everything except the re-ranking narratives still works.
- **Your original file is never touched.** Fixes write `<name>_cleaned.csv` plus
  a standalone, reproducible `cleaning_script.py` (plain pandas) that regenerates
  the cleaned file from the original.

## Install

```
pip install -e .
```

Requires Python ≥ 3.10.

## Usage

```
auto-eda analyze data.csv                 # detect, score, propose fixes, rank, chart
auto-eda analyze data.csv --yes           # apply all proposed fixes without prompting
auto-eda analyze data.csv --no-clean      # diagnostic only, never apply fixes
auto-eda analyze data.csv --target churn  # adds class-balance analysis
auto-eda analyze data.csv --report        # also writes report.md
auto-eda analyze data.csv --no-llm        # force heuristic ranking
auto-eda analyze data.csv -o results/     # output directory (default auto_eda_out/)
```

| Option | Effect |
|---|---|
| `--target`, `-t` | Target column; enables class-imbalance analysis. |
| `--yes`, `-y` | Apply all proposed fixes without the confirmation prompt. |
| `--no-clean` | Report only — never write a cleaned file. |
| `--report` | Also write `report.md`. |
| `--no-llm` | Skip LLM ranking; use the deterministic heuristic order. |
| `--out`, `-o` | Output directory (default `auto_eda_out/`). |

### Outputs

All artifacts land in the output directory:

| Artifact | When |
|---|---|
| `charts.html` | always — quality badge + plotly charts for the top-ranked findings |
| `<name>_cleaned.csv` | when fixes are applied |
| `cleaning_script.py` | when fixes are applied — reproduces the cleaned CSV from the original |
| `report.md` | with `--report` |

## The quality score

The score is the deterministic headline: a single 0–100 grade computed straight
from the profile and findings, no model required. It is a **weighted average**
of five dimensions:

| Dimension | Weight | How it's scored |
|---|---:|---|
| **Completeness** | 30% | share of cells that hold a real value (true + disguised nulls counted as missing) |
| **Validity** | 25% | share of columns free of type violations (e.g. a numeric column polluted with text) |
| **Consistency** | 20% | share of columns free of formatting issues (stray whitespace, casing variants) |
| **Uniqueness** | 15% | share of rows that aren't exact duplicates |
| **Structure** | 10% | share of columns that aren't constant or redundantly correlated |

Grades follow the usual bands (`≥97 A+`, `≥93 A`, `≥90 A-`, … `<60 F`). Weights
live in `Config.quality_weights` and can be tuned.

**Deliberately excluded from the score**, because they fire on healthy data or
are analytical characteristics rather than defects:

- *numeric/date stored as text* — every CSV stores these as strings; trivially
  cast, so penalizing them would drag every dataset down.
- *ID-like columns, outliers, skew, class imbalance* — these matter for
  modeling (and the ranker still surfaces them), but they don't make the data
  dirty.

## What it detects

Duplicates, true and disguised nulls (`"N/A"`, `"-"`, `"?"`, …), numeric/date
values stored as text, mixed-type columns, stray whitespace, casing variants of
the same category (`NY`/`ny`/`New York`), outliers (IQR ∩ modified z-score),
constant columns, ID-like columns, near-duplicate correlated pairs, heavy skew,
and class imbalance (with `--target`).

Each issue becomes a `Finding` carrying the affected rows, evidence, a heuristic
severity, and — where safe — a proposed fix.

## How it works

```
ingest → profile → detect → score → propose/apply fixes → re-score
       → EDA → rank (LLM or heuristic) → render (terminal + charts.html [+ report.md])
```

1. **Ingest** — encoding and delimiter are sniffed; the CSV is read entirely as
   text (so disguised-null and type detection see the raw values). The original
   is opened read-only and never modified.
2. **Profile** — per-column stats (inferred type, missingness, cardinality,
   sample values) computed once and reused everywhere downstream.
3. **Detect + score** — independent detectors emit findings; the quality score
   is computed from them and the profile.
4. **Clean** — cleanable findings are applied in a safe order to a copy, writing
   `<name>_cleaned.csv` and a reproducible `cleaning_script.py`. The score is
   recomputed on the cleaned data.
5. **EDA** — distributions, correlations, and (with `--target`) class balance,
   emitted as more findings.
6. **Rank** — the LLM re-orders findings by real-world impact and writes a
   one-line rationale each; falls back to heuristic order on any failure.
7. **Render** — a ranked table + quality gauge in the terminal, an HTML chart
   deck for the top findings, and an optional markdown report.

## LLM setup (optional)

Provider resolution is a fallback chain — the first available tier wins:

```
# Tier 1: Anthropic API
export ANTHROPIC_API_KEY=sk-ant-...

# Tier 2: local model, no key needed
ollama pull llama3.2 && ollama serve

# Tier 3: nothing — heuristic ranking, everything else still works
```

The LLM is used **only** to re-rank findings and write their one-line
narratives. It never sees raw rows and never computes a statistic.

## Try the demo

```
python examples/make_messy.py
auto-eda analyze examples/messy.csv --target churn --yes --report
```

`make_messy.py` generates a deliberately dirty CSV (duplicates, disguised nulls,
casing variants, a numeric column stored as text, a constant column) so you can
watch the score climb after cleaning.

## Development

```
pip install -e ".[dev]"
pytest                          # run the suite
pytest tests/test_quality.py    # a single file
```

All detection, cleaning, and scoring are pure functions over
`(df, profile, config)` with no I/O, which is what lets the tests build small
in-memory frames and assert on findings and scores directly.

## License

MIT — see [LICENSE](LICENSE).
