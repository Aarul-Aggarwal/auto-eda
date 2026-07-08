"""Type issues: numeric-stored-as-string, mixed types, parseable dates."""

from __future__ import annotations

import pandas as pd

from ..config import Config
from ..findings import Finding, ProposedFix, make_id
from ..profiling import DatasetProfile


def detect(df: pd.DataFrame, profile: DatasetProfile, config: Config) -> list[Finding]:
    findings: list[Finding] = []
    n_rows = profile.n_rows
    if n_rows == 0:
        return findings

    for name, col in profile.columns.items():
        non_null = int(col.values.notna().sum())
        if non_null == 0:
            continue

        if col.inferred_type == "numeric":
            findings.append(
                Finding(
                    id=make_id("type_mismatch", [name]),
                    kind="type_mismatch",
                    title=f"'{name}' is numeric stored as text",
                    columns=[name],
                    affected_rows=non_null,
                    affected_pct=non_null / n_rows,
                    evidence={"numeric_parse_pct": round(col.numeric_parse_pct, 4)},
                    proposed_fix=ProposedFix(
                        transform="cast_numeric",
                        params={"column": name},
                        description=f"Cast '{name}' to a numeric dtype",
                    ),
                )
            )
        elif col.inferred_type == "datetime":
            findings.append(
                Finding(
                    id=make_id("parseable_dates", [name]),
                    kind="parseable_dates",
                    title=f"'{name}' contains parseable dates stored as text",
                    columns=[name],
                    affected_rows=non_null,
                    affected_pct=non_null / n_rows,
                    evidence={"date_parse_pct": round(col.date_parse_pct, 4)},
                    proposed_fix=ProposedFix(
                        transform="cast_datetime",
                        params={"column": name},
                        description=f"Parse '{name}' as datetime",
                    ),
                )
            )
        # Mixed types: mostly numeric but a stray minority of non-numeric values
        elif 0.5 <= col.numeric_parse_pct < config.numeric_parse_pct:
            n_bad = round((1 - col.numeric_parse_pct) * non_null)
            bad_values = (
                col.values.dropna()[
                    pd.to_numeric(
                        col.values.dropna().str.replace(",", "", regex=False), errors="coerce"
                    ).isna()
                ]
                .unique()[:5]
                .tolist()
            )
            findings.append(
                Finding(
                    id=make_id("mixed_types", [name]),
                    kind="mixed_types",
                    title=f"'{name}' is mostly numeric but has {n_bad} non-numeric values",
                    columns=[name],
                    affected_rows=n_bad,
                    affected_pct=n_bad / n_rows,
                    evidence={
                        "numeric_parse_pct": round(col.numeric_parse_pct, 4),
                        "non_numeric_examples": bad_values,
                    },
                    proposed_fix=ProposedFix(
                        transform="coerce_numeric",
                        params={"column": name},
                        description=f"Coerce '{name}' to numeric, turning non-numeric values into NaN",
                    ),
                )
            )
    return findings
