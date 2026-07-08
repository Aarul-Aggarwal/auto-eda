"""Structural issues: constant columns, ID-like columns, highly correlated pairs."""

from __future__ import annotations

import numpy as np
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
        if col.n_unique <= 1:
            findings.append(
                Finding(
                    id=make_id("constant_column", [name]),
                    kind="constant_column",
                    title=f"'{name}' is constant",
                    columns=[name],
                    affected_rows=n_rows,
                    affected_pct=1.0,
                    evidence={"value": col.sample_values[:1]},
                    proposed_fix=ProposedFix(
                        transform="drop_column",
                        params={"column": name},
                        description=f"Drop constant column '{name}'",
                    ),
                )
            )
        elif (
            col.inferred_type in ("text", "numeric")
            and non_null >= 20
            and col.n_unique / non_null >= config.high_cardinality_ratio
        ):
            findings.append(
                Finding(
                    id=make_id("id_like_column", [name]),
                    kind="id_like_column",
                    title=f"'{name}' looks like an identifier ({col.n_unique} unique values)",
                    columns=[name],
                    affected_rows=0,
                    affected_pct=0.0,
                    evidence={"unique_ratio": round(col.n_unique / non_null, 4)},
                )
            )

    num = profile.numeric_frame()
    if num.shape[1] >= 2:
        corr = num.corr().abs()
        upper = corr.where(np.triu(np.ones(corr.shape, dtype=bool), k=1))
        for a, b in zip(*np.where(upper.values >= config.high_correlation)):
            ca, cb = corr.index[a], corr.columns[b]
            findings.append(
                Finding(
                    id=make_id("high_correlation", [str(ca), str(cb)]),
                    kind="high_correlation",
                    title=f"'{ca}' and '{cb}' are nearly identical (r={corr.iloc[a, b]:.3f})",
                    columns=[str(ca), str(cb)],
                    affected_rows=0,
                    affected_pct=0.0,
                    evidence={"pearson_r": round(float(corr.iloc[a, b]), 4)},
                )
            )
    return findings
