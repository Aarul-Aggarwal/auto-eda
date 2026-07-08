"""Cleaning transforms: preview, apply, and emit a reproducible pandas script.

The original CSV is never modified. Applying fixes produces a new DataFrame
written to <stem>_cleaned.csv, plus cleaning_script.py that reproduces the
cleaned file from the original with plain pandas.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from .config import Config, DEFAULT_CONFIG
from .findings import Finding

# --- transform implementations (df is string-typed as loaded by ingest) -----


def _normalize_nulls(df: pd.DataFrame, column: str, tokens: tuple[str, ...]) -> pd.DataFrame:
    s = df[column].str.strip()
    df[column] = s.mask(s.str.lower().isin(tokens))
    return df


def _drop_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    return df.drop_duplicates(keep="first").reset_index(drop=True)


def _drop_column(df: pd.DataFrame, column: str) -> pd.DataFrame:
    return df.drop(columns=[column])


def _cast_numeric(df: pd.DataFrame, column: str) -> pd.DataFrame:
    # coerce: numeric inference allows up to 5% unparseable values
    df[column] = pd.to_numeric(
        df[column].str.strip().str.replace(",", "", regex=False), errors="coerce"
    )
    return df


def _coerce_numeric(df: pd.DataFrame, column: str) -> pd.DataFrame:
    df[column] = pd.to_numeric(
        df[column].str.strip().str.replace(",", "", regex=False), errors="coerce"
    )
    return df


def _cast_datetime(df: pd.DataFrame, column: str) -> pd.DataFrame:
    df[column] = pd.to_datetime(df[column].str.strip(), errors="coerce", format="mixed")
    return df


def _strip_whitespace(df: pd.DataFrame, column: str) -> pd.DataFrame:
    df[column] = df[column].str.strip()
    return df


def _normalize_case(df: pd.DataFrame, column: str) -> pd.DataFrame:
    s = df[column]
    canon = s.groupby(s.str.lower()).agg(lambda g: g.value_counts().idxmax())
    df[column] = s.str.lower().map(canon).fillna(s)
    return df


@dataclass(frozen=True)
class TransformSpec:
    func: Callable
    needs_column: bool
    # a python expression template applied in the generated script
    code: str


TRANSFORMS: dict[str, TransformSpec] = {
    "drop_duplicates": TransformSpec(
        _drop_duplicates, False,
        'df = df.drop_duplicates(keep="first").reset_index(drop=True)',
    ),
    "normalize_nulls": TransformSpec(
        _normalize_nulls, True,
        'df[{col!r}] = df[{col!r}].str.strip().mask(df[{col!r}].str.strip().str.lower().isin(NULL_TOKENS))',
    ),
    "drop_column": TransformSpec(
        _drop_column, True,
        "df = df.drop(columns=[{col!r}])",
    ),
    "cast_numeric": TransformSpec(
        _cast_numeric, True,
        'df[{col!r}] = pd.to_numeric(df[{col!r}].str.strip().str.replace(",", "", regex=False), errors="coerce")',
    ),
    "coerce_numeric": TransformSpec(
        _coerce_numeric, True,
        'df[{col!r}] = pd.to_numeric(df[{col!r}].str.strip().str.replace(",", "", regex=False), errors="coerce")',
    ),
    "cast_datetime": TransformSpec(
        _cast_datetime, True,
        'df[{col!r}] = pd.to_datetime(df[{col!r}].str.strip(), errors="coerce", format="mixed")',
    ),
    "strip_whitespace": TransformSpec(
        _strip_whitespace, True,
        "df[{col!r}] = df[{col!r}].str.strip()",
    ),
    "normalize_case": TransformSpec(
        _normalize_case, True,
        "df[{col!r}] = normalize_case(df[{col!r}])",
    ),
}

# Order matters: normalize nulls/whitespace before casts, drops last.
_APPLY_ORDER = [
    "drop_duplicates",
    "strip_whitespace",
    "normalize_nulls",
    "normalize_case",
    "cast_numeric",
    "coerce_numeric",
    "cast_datetime",
    "drop_column",
]


@dataclass
class AppliedFix:
    finding: Finding
    transform: str
    column: str | None
    code_line: str


def plan_fixes(findings: list[Finding]) -> list[Finding]:
    """Cleanable findings in safe application order."""
    fixable = [f for f in findings if f.proposed_fix is not None]
    order = {name: i for i, name in enumerate(_APPLY_ORDER)}
    return sorted(fixable, key=lambda f: order.get(f.proposed_fix.transform, 99))


def apply_fixes(
    df: pd.DataFrame,
    fixes: list[Finding],
    config: Config = DEFAULT_CONFIG,
) -> tuple[pd.DataFrame, list[AppliedFix]]:
    cleaned = df.copy()
    applied: list[AppliedFix] = []
    for finding in fixes:
        fix = finding.proposed_fix
        spec = TRANSFORMS.get(fix.transform)
        if spec is None:
            continue
        col = fix.params.get("column")
        if spec.needs_column and (col is None or col not in cleaned.columns):
            continue  # column may have been dropped by an earlier fix
        if fix.transform == "normalize_nulls":
            cleaned = spec.func(cleaned, col, config.disguised_nulls)
        elif spec.needs_column:
            cleaned = spec.func(cleaned, col)
        else:
            cleaned = spec.func(cleaned)
        applied.append(
            AppliedFix(
                finding=finding,
                transform=fix.transform,
                column=col,
                code_line=spec.code.format(col=col),
            )
        )
    return cleaned, applied


_SCRIPT_TEMPLATE = '''\
"""Reproducible cleaning script generated by auto-eda.

Reads the original CSV (read-only) and writes the cleaned copy.
Run: python cleaning_script.py
"""

import pandas as pd

SOURCE = {source!r}
OUTPUT = {output!r}
ENCODING = {encoding!r}
DELIMITER = {delimiter!r}
NULL_TOKENS = {null_tokens!r}


def normalize_case(s: pd.Series) -> pd.Series:
    canon = s.groupby(s.str.lower()).agg(lambda g: g.value_counts().idxmax())
    return s.str.lower().map(canon).fillna(s)


df = pd.read_csv(SOURCE, encoding=ENCODING, sep=DELIMITER, dtype=str,
                 keep_default_na=False, engine="python")
df = df.where(df != "")

{transform_lines}

df.to_csv(OUTPUT, index=False)
print(f"Wrote {{len(df)}} rows to {{OUTPUT}}")
'''


def generate_script(
    applied: list[AppliedFix],
    source: Path,
    output: Path,
    encoding: str,
    delimiter: str,
    config: Config = DEFAULT_CONFIG,
) -> str:
    lines = [
        f"# {a.finding.title}\n{a.code_line}" for a in applied
    ]
    return _SCRIPT_TEMPLATE.format(
        source=str(source),
        output=str(output),
        encoding=encoding,
        delimiter=delimiter,
        null_tokens=tuple(config.disguised_nulls),
        transform_lines="\n\n".join(lines) if lines else "# no fixes applied",
    )
