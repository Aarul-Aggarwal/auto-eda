"""Formatting inconsistencies: stray whitespace, casing variants of the same category."""

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
        raw_non_null = col.raw.dropna()
        if raw_non_null.empty:
            continue

        # Leading/trailing whitespace in the raw values
        ws_mask = raw_non_null != raw_non_null.str.strip()
        n_ws = int(ws_mask.sum())
        if n_ws / n_rows >= config.whitespace_flag_pct:
            findings.append(
                Finding(
                    id=make_id("whitespace", [name]),
                    kind="whitespace",
                    title=f"'{name}' has {n_ws} values with stray whitespace",
                    columns=[name],
                    affected_rows=n_ws,
                    affected_pct=n_ws / n_rows,
                    evidence={"examples": raw_non_null[ws_mask].unique()[:5].tolist()},
                    proposed_fix=ProposedFix(
                        transform="strip_whitespace",
                        params={"column": name},
                        description=f"Strip leading/trailing whitespace in '{name}'",
                    ),
                )
            )

        # Casing variants: values identical after lowercasing ("NY" vs "ny")
        if col.inferred_type in ("categorical", "boolean") and col.n_unique <= config.category_max_unique:
            vals = col.values.dropna()
            if vals.empty:
                continue
            groups = vals.groupby(vals.str.lower()).unique()
            variant_groups = {k: list(v) for k, v in groups.items() if len(v) > 1}
            if variant_groups:
                affected = int(vals.str.lower().isin(variant_groups).sum())
                findings.append(
                    Finding(
                        id=make_id("case_inconsistency", [name]),
                        kind="case_inconsistency",
                        title=f"'{name}' has casing variants of the same category",
                        columns=[name],
                        affected_rows=affected,
                        affected_pct=affected / n_rows,
                        evidence={"variants": dict(list(variant_groups.items())[:5])},
                        proposed_fix=ProposedFix(
                            transform="normalize_case",
                            params={"column": name},
                            description=f"Normalize casing variants in '{name}' to the most frequent form",
                        ),
                    )
                )
    return findings
