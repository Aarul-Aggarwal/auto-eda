"""Outlier detection on numeric columns: IQR fences + modified z-score (MAD)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import Config
from ..findings import Finding, make_id
from ..profiling import DatasetProfile


def detect(df: pd.DataFrame, profile: DatasetProfile, config: Config) -> list[Finding]:
    findings: list[Finding] = []
    n_rows = profile.n_rows
    if n_rows == 0:
        return findings

    for name, col in profile.columns.items():
        if col.inferred_type != "numeric" or col.parsed is None:
            continue
        s = col.parsed.dropna()
        if len(s) < 20 or s.nunique() < 5:
            continue

        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            continue
        lo, hi = q1 - config.iqr_multiplier * iqr, q3 + config.iqr_multiplier * iqr
        iqr_mask = (s < lo) | (s > hi)

        median = s.median()
        mad = (s - median).abs().median()
        if mad > 0:
            mod_z = 0.6745 * (s - median) / mad
            z_mask = mod_z.abs() > config.zscore_threshold
        else:
            z_mask = pd.Series(False, index=s.index)

        # Require both tests to agree, to avoid flagging ordinary skew
        mask = iqr_mask & z_mask
        n_out = int(mask.sum())
        if n_out == 0 or n_out / n_rows < config.outlier_flag_pct:
            continue

        extremes = s[mask]
        findings.append(
            Finding(
                id=make_id("outliers", [name]),
                kind="outliers",
                title=f"'{name}' has {n_out} outliers",
                columns=[name],
                affected_rows=n_out,
                affected_pct=n_out / n_rows,
                evidence={
                    "fences": [round(float(lo), 4), round(float(hi), 4)],
                    "min_outlier": float(extremes.min()),
                    "max_outlier": float(extremes.max()),
                    "median": float(median),
                },
                # No proposed fix: dropping/capping outliers is an analysis
                # decision, not a data-quality repair.
            )
        )
    return findings
