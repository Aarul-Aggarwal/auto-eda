"""EDA checks on the (cleaned) data: skew, class balance. Emits Findings
into the same stream as the detectors."""

from __future__ import annotations

import pandas as pd

from .config import Config, DEFAULT_CONFIG
from .findings import Finding, make_id
from .profiling import DatasetProfile


def analyze(
    profile: DatasetProfile,
    target: str | None = None,
    config: Config = DEFAULT_CONFIG,
) -> list[Finding]:
    findings: list[Finding] = []

    for name, col in profile.columns.items():
        if col.inferred_type != "numeric" or col.parsed is None:
            continue
        s = col.parsed.dropna()
        if len(s) < 20 or s.nunique() < 5:
            continue
        skew = float(s.skew())
        if abs(skew) >= config.skew_threshold:
            findings.append(
                Finding(
                    id=make_id("skewed_distribution", [name]),
                    kind="skewed_distribution",
                    title=f"'{name}' is heavily skewed (skew={skew:.2f})",
                    columns=[name],
                    affected_rows=len(s),
                    affected_pct=len(s) / profile.n_rows,
                    evidence={
                        "skew": round(skew, 3),
                        "mean": round(float(s.mean()), 4),
                        "median": round(float(s.median()), 4),
                    },
                )
            )

    if target is not None and target in profile.columns:
        col = profile.columns[target]
        vals = col.parsed if col.parsed is not None else col.values
        counts = vals.dropna().astype(str).value_counts()
        if 2 <= len(counts) <= config.category_max_unique:
            ratio = counts.iloc[0] / counts.iloc[-1]
            if ratio >= config.class_imbalance_ratio:
                findings.append(
                    Finding(
                        id=make_id("class_imbalance", [target]),
                        kind="class_imbalance",
                        title=(
                            f"Target '{target}' is imbalanced "
                            f"({counts.index[0]}: {counts.iloc[0]} vs {counts.index[-1]}: {counts.iloc[-1]})"
                        ),
                        columns=[target],
                        affected_rows=int(counts.sum()),
                        affected_pct=1.0,
                        evidence={
                            "class_counts": {str(k): int(v) for k, v in counts.head(10).items()},
                            "majority_minority_ratio": round(float(ratio), 2),
                        },
                    )
                )
    return findings
