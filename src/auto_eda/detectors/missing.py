"""Missing values: true nulls, disguised nulls, mostly-missing columns."""

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
        if col.n_disguised > 0:
            tokens = (
                col.raw.str.strip().str.lower()[
                    col.raw.str.strip().str.lower().isin(config.disguised_nulls)
                ]
                .value_counts()
                .head(5)
                .to_dict()
            )
            findings.append(
                Finding(
                    id=make_id("disguised_nulls", [name]),
                    kind="disguised_nulls",
                    title=f"'{name}' has {col.n_disguised} disguised nulls",
                    columns=[name],
                    affected_rows=col.n_disguised,
                    affected_pct=col.n_disguised / n_rows,
                    evidence={"tokens": tokens},
                    proposed_fix=ProposedFix(
                        transform="normalize_nulls",
                        params={"column": name},
                        description=f"Replace placeholder tokens {list(tokens)} in '{name}' with real NaN",
                    ),
                )
            )

        true_missing = col.n_missing - col.n_disguised
        if true_missing > 0:
            pct = col.n_missing / n_rows
            fix = None
            if pct >= config.high_missing_pct:
                fix = ProposedFix(
                    transform="drop_column",
                    params={"column": name},
                    description=f"Drop '{name}' ({pct:.0%} missing)",
                )
            findings.append(
                Finding(
                    id=make_id("missing_values", [name]),
                    kind="missing_values",
                    title=f"'{name}' is {pct:.1%} missing",
                    columns=[name],
                    affected_rows=col.n_missing,
                    affected_pct=pct,
                    evidence={"true_nulls": true_missing, "disguised": col.n_disguised},
                    proposed_fix=fix,
                )
            )
    return findings
