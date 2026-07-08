# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`auto-eda` is a CLI (`typer` + `rich`) that points at a raw CSV, detects data-quality
issues deterministically, proposes (and optionally applies) cleaning fixes to a
*new* file, runs standard EDA, and uses an LLM to turn the results into a short,
ranked list of findings. The original input file is never modified.

## Commands

```
pip install -e ".[dev]"      # install package + pytest, editable
pytest                        # run all tests
pytest tests/test_ranker.py   # run one test file
pytest tests/test_ranker.py::test_name -v   # run one test

auto-eda analyze examples/messy.csv --target churn --yes --report   # demo end-to-end
python examples/make_messy.py                                        # regenerate examples/messy.csv
```

There is no separate lint/build step configured; `pyproject.toml` (hatchling) only
defines the package build and pytest's `testpaths = ["tests"]`.

## Architecture

The whole tool is one linear pipeline, driven by `cli.py:analyze`, over a single
shared data structure — a list of `Finding` objects (`findings.py`):

```
ingest -> profile -> detect -> score -> plan/apply fixes -> re-profile/re-score ->
eda -> rank (LLM or heuristic) -> render (terminal + charts.html [+ report.md])
```

- **`ingest.py`** — reads the CSV read-only with sniffed encoding/delimiter, always
  as `dtype=str` with `keep_default_na=False`. This is deliberate: disguised-null
  and type-mismatch detection need to see the raw string values, not pandas'
  pre-parsed types. Type inference is itself something the tool reports on, not
  something it does silently at load time.
- **`profiling.py`** — builds a `DatasetProfile` (per-column stats) from the raw
  string frame; this profile is threaded through detectors, EDA, and the LLM
  summary rather than re-deriving stats in each place.
- **`detectors/`** — a registry (`detectors/__init__.py:ALL_DETECTORS`) of
  independent modules (`duplicates`, `missing`, `types`, `formatting`, `outliers`,
  `structure`), each a pure function `(df, profile, config) -> list[Finding]`. To
  add a new check, add a module with a `detect()` function and register it here.
- **`findings.py`** — the `Finding` schema is the spine everything else consumes.
  `score_findings` computes deterministic severity as
  `kind_weight × (0.3 + 0.7 × affected_fraction)`, using per-kind weights from
  `config.py`. A finding optionally carries a `ProposedFix` (a transform name +
  params referencing the `cleaning.TRANSFORMS` registry).
- **`cleaning.py`** — `TRANSFORMS` maps fix names to `(func, needs_column, code
  template)`. `_APPLY_ORDER` matters: nulls/whitespace normalize before type
  casts, drops happen last (columns dropped by earlier fixes are skipped safely
  by later ones — see `apply_fixes`). Applying fixes both produces a cleaned
  DataFrame *and* renders a standalone `cleaning_script.py` via
  `_SCRIPT_TEMPLATE`, using the same code templates, so the cleaning is
  independently reproducible without importing this package.
- **`quality.py`** — a fully deterministic 0–100 data-quality score + letter
  grade (no LLM), a weighted average over five dimensions (Completeness,
  Validity, Consistency, Uniqueness, Structure). Consumes only the profile +
  findings. The CLI computes it twice — once on raw findings, once after
  re-running detectors on the cleaned frame — to show a before→after delta.
  Some finding kinds are intentionally *not* scored (`type_mismatch`,
  `parseable_dates`, `id_like_column`, `outliers`, `skewed_distribution`,
  `class_imbalance`) because they fire on healthy CSVs or are analytical
  characteristics, not cleanliness defects — see the docstring. Dimension
  weights live in `config.quality_weights`.
- **`eda.py`** — runs on the (possibly cleaned) profile: distributions,
  correlations, class balance if `--target` is given. Emits `Finding`s the same
  way detectors do, so they merge into one ranked list.
- **`llm/`** — three-tier provider resolution in `provider.py:resolve_provider`:
  `ANTHROPIC_API_KEY` env var → local Ollama server (probed via HTTP) → `None`.
  Every `LLMProvider` implements `complete_json(prompt, schema) -> dict`; any
  exception from a provider is treated as "fall back to heuristic ranking" by
  `ranker.py:rank` (never propagated). The LLM only ever sees a JSON summary
  (`prompts.py:build_summary`) — schema, aggregates, up to `config.llm_sample_values`
  sample values per column — never raw row data, and it never computes anything
  itself; it only reorders findings and writes short narratives via a
  JSON-schema-constrained response (`RANKING_SCHEMA`). If the LLM omits or
  hallucinates finding ids, `rank()` reconciles: known ids get the LLM's
  narrative, omitted findings keep their heuristic-sorted position appended at
  the end (never dropped).
- **`render/`** — `terminal.py` (rich console output), `charts.py` (plotly
  `charts.html`, generated only for the top-`N` ranked findings), `report.py`
  (optional `report.md`).
- **`config.py`** — a single frozen `Config` dataclass holds every threshold,
  weight, and tuning knob (missing-value tokens, IQR/z-score thresholds,
  cardinality/correlation cutoffs, severity weights, LLM sampling limits). New
  detection thresholds should be added here rather than hardcoded in a detector.

## Conventions specific to this codebase

- Every detector and EDA check is a pure function over `(df, profile, config)` —
  no shared mutable state, no I/O. This is what lets `findings.py` treat
  detector output and EDA output identically.
- Cleaning transforms exist in two parallel forms that must stay in sync: the
  pandas function in `cleaning.py` (applied in-process) and the `code` string
  template on the same `TransformSpec` (emitted into `cleaning_script.py`).
  Changing one without the other will make the generated script diverge from
  what the tool actually did.
- Tests build string-typed DataFrames by hand (see `tests/conftest.py:make_df`)
  to match exactly what `ingest.load_csv` produces, rather than relying on
  pandas' default type inference.
- `render/terminal.py` reconfigures stdout/stderr to UTF-8 and builds its rich
  `Console` with `legacy_windows=False` at import. This is required, not
  cosmetic: the score gauge uses block-drawing glyphs (`█ ░`) that crash a
  cp1252 Windows console via rich's legacy win32 writer. Keep any new
  non-ASCII terminal output behind this same console.
