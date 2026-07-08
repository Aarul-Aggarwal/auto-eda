"""Deterministic data-quality score — no LLM required.

Collapses the findings + profile into a single 0-100 score and letter grade,
broken down across five interpretable dimensions. This is intentionally
transparent: every number is a plain ratio of cells/columns/rows, so a user
can reproduce it by hand. When cleaning is applied, the CLI computes the score
twice (before and after) to show the payoff of the fixes.

Deliberately excluded from scoring:
  * `type_mismatch` / `parseable_dates` — every CSV stores numbers and dates as
    text, so these fire on healthy data and are trivially cast. Penalizing them
    would drag every dataset down for a non-defect.
  * `id_like_column`, `outliers`, `skewed_distribution`, `class_imbalance` —
    analytical *characteristics*, not cleanliness defects. They matter for
    modeling (and the ranker surfaces them), but they don't make the data dirty.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import Config, DEFAULT_CONFIG
from .findings import Finding
from .profiling import DatasetProfile

# Column-level dimensions: dimension name -> the finding kinds that dock it.
# Completeness and Uniqueness are computed directly from counts, not kinds.
_COLUMN_DIMENSIONS: dict[str, set[str]] = {
    "Validity": {"mixed_types"},
    "Consistency": {"whitespace", "case_inconsistency", "category_near_match"},
    "Structure": {"constant_column", "high_correlation"},
}

_DISPLAY_ORDER = ["Completeness", "Validity", "Consistency", "Uniqueness", "Structure"]

# score >= threshold -> grade
_GRADE_BANDS: list[tuple[float, str]] = [
    (97, "A+"), (93, "A"), (90, "A-"),
    (87, "B+"), (83, "B"), (80, "B-"),
    (77, "C+"), (73, "C"), (70, "C-"),
    (67, "D+"), (63, "D"), (60, "D-"),
    (0, "F"),
]


def grade_for(score: float) -> str:
    for threshold, grade in _GRADE_BANDS:
        if score >= threshold:
            return grade
    return "F"


def band_word(score: float) -> str:
    """A one-word verdict used by the renderers."""
    if score >= 90:
        return "EXCELLENT"
    if score >= 75:
        return "GOOD"
    if score >= 60:
        return "FAIR"
    return "POOR"


@dataclass
class DimensionScore:
    name: str
    score: float  # 0-100
    detail: str   # human-readable basis for the number


@dataclass
class QualityScore:
    overall: float  # 0-100
    grade: str
    dimensions: list[DimensionScore]


def compute_quality(
    profile: DatasetProfile,
    findings: list[Finding],
    config: Config = DEFAULT_CONFIG,
) -> QualityScore:
    """Score the dataset from its profile and detector findings (no EDA needed)."""
    n_rows, n_cols = profile.n_rows, profile.n_cols
    dims: list[DimensionScore] = []

    # Completeness: fraction of cells that hold a real value.
    total_cells = n_rows * n_cols
    missing_cells = sum(c.n_missing for c in profile.columns.values())
    if total_cells:
        completeness = 100.0 * (1 - missing_cells / total_cells)
        detail = f"{missing_cells:,} / {total_cells:,} cells missing ({missing_cells / total_cells:.1%})"
    else:
        completeness, detail = 100.0, "no cells"
    dims.append(DimensionScore("Completeness", completeness, detail))

    # Column-level dimensions: share of columns untouched by their finding kinds.
    for name, kinds in _COLUMN_DIMENSIONS.items():
        flagged = {c for f in findings if f.kind in kinds for c in f.columns}
        score = 100.0 if n_cols == 0 else 100.0 * (1 - len(flagged) / n_cols)
        noun = {
            "Validity": "type-violating",
            "Consistency": "inconsistently formatted",
            "Structure": "constant / redundant",
        }[name]
        dims.append(DimensionScore(name, score, f"{len(flagged)} / {n_cols} columns {noun}"))

    # Uniqueness: fraction of rows that aren't exact duplicates.
    dup = next((f for f in findings if f.kind == "duplicate_rows"), None)
    dup_pct = min(dup.affected_pct, 1.0) if dup else 0.0
    uniqueness = 100.0 * (1 - dup_pct)
    detail = f"{dup.affected_rows:,} duplicate rows ({dup_pct:.1%})" if dup else "no duplicate rows"
    dims.append(DimensionScore("Uniqueness", uniqueness, detail))

    dims.sort(key=lambda d: _DISPLAY_ORDER.index(d.name))

    weights = config.quality_weights
    total_w = sum(weights.get(d.name, 0.0) for d in dims) or 1.0
    overall = round(sum(d.score * weights.get(d.name, 0.0) for d in dims) / total_w, 1)
    return QualityScore(overall=overall, grade=grade_for(overall), dimensions=dims)
