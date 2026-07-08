"""Deterministic per-column profiling.

Everything downstream (detectors, EDA, the LLM summary) works from these
profiles so parsing happens exactly once.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from .config import Config, DEFAULT_CONFIG


@dataclass
class ColumnProfile:
    name: str
    raw: pd.Series  # original strings, disguised nulls NOT yet removed
    values: pd.Series  # strings with true/disguised nulls as NaN
    inferred_type: str  # numeric | datetime | boolean | categorical | text
    parsed: Optional[pd.Series]  # numeric/datetime parse of `values`, else None
    n_rows: int = 0
    n_missing: int = 0  # true nulls + disguised nulls
    n_disguised: int = 0
    n_unique: int = 0
    numeric_parse_pct: float = 0.0
    date_parse_pct: float = 0.0
    sample_values: list[str] = field(default_factory=list)


@dataclass
class DatasetProfile:
    n_rows: int
    n_cols: int
    columns: dict[str, ColumnProfile]

    def numeric_frame(self) -> pd.DataFrame:
        cols = {
            n: p.parsed
            for n, p in self.columns.items()
            if p.inferred_type == "numeric" and p.parsed is not None
        }
        return pd.DataFrame(cols)


_BOOL_SETS = (
    {"true", "false"}, {"yes", "no"}, {"y", "n"}, {"0", "1"}, {"t", "f"},
)


def _profile_column(name: str, raw: pd.Series, n_rows: int, config: Config) -> ColumnProfile:
    stripped = raw.str.strip()
    disguised_mask = stripped.str.lower().isin(config.disguised_nulls)
    values = stripped.mask(disguised_mask)
    non_null = values.dropna()
    n_missing = int(values.isna().sum())
    n_disguised = int(disguised_mask.sum())

    numeric_parsed = pd.to_numeric(non_null.str.replace(",", "", regex=False), errors="coerce")
    numeric_pct = float(numeric_parsed.notna().mean()) if len(non_null) else 0.0

    date_parsed = None
    date_pct = 0.0
    # Only try dates on columns that aren't overwhelmingly numeric (avoids
    # to_datetime treating plain integers as epoch timestamps).
    if len(non_null) and numeric_pct < config.numeric_parse_pct:
        with pd.option_context("mode.chained_assignment", None):
            date_parsed = pd.to_datetime(non_null, errors="coerce", format="mixed")
        date_pct = float(date_parsed.notna().mean())

    n_unique = int(non_null.nunique())
    lowered_unique = set(non_null.str.lower().unique()[:10])

    if len(non_null) == 0:
        inferred, parsed = "text", None
    elif any(lowered_unique <= s for s in _BOOL_SETS) and n_unique <= 2:
        inferred, parsed = "boolean", None
    elif numeric_pct >= config.numeric_parse_pct:
        inferred = "numeric"
        parsed = numeric_parsed.reindex(values.index)
    elif date_pct >= config.date_parse_pct:
        inferred = "datetime"
        parsed = date_parsed.reindex(values.index) if date_parsed is not None else None
    elif n_unique <= config.category_max_unique:
        inferred, parsed = "categorical", None
    else:
        inferred, parsed = "text", None

    return ColumnProfile(
        name=name,
        raw=raw,
        values=values,
        inferred_type=inferred,
        parsed=parsed,
        n_rows=n_rows,
        n_missing=n_missing,
        n_disguised=n_disguised,
        n_unique=n_unique,
        numeric_parse_pct=numeric_pct,
        date_parse_pct=date_pct,
        sample_values=[str(v) for v in non_null.unique()[: config.llm_sample_values]],
    )


def profile(df: pd.DataFrame, config: Config = DEFAULT_CONFIG) -> DatasetProfile:
    n_rows = len(df)
    columns = {
        col: _profile_column(col, df[col].astype(str).where(df[col].notna()), n_rows, config)
        for col in df.columns
    }
    return DatasetProfile(n_rows=n_rows, n_cols=len(df.columns), columns=columns)
