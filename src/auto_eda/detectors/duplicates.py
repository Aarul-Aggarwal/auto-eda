"""Exact duplicate row detection."""

from __future__ import annotations

import pandas as pd

from ..config import Config
from ..findings import Finding, ProposedFix, make_id
from ..profiling import DatasetProfile


def detect(df: pd.DataFrame, profile: DatasetProfile, config: Config) -> list[Finding]:
    if df.empty:
        return []
    dup_mask = df.duplicated(keep="first")
    n_dupes = int(dup_mask.sum())
    if n_dupes == 0:
        return []

    return [
        Finding(
            id=make_id("duplicate_rows", []),
            kind="duplicate_rows",
            title=f"{n_dupes} exact duplicate rows",
            affected_rows=n_dupes,
            affected_pct=n_dupes / len(df),
            evidence={"first_duplicate_index": int(df.index[dup_mask][0])},
            proposed_fix=ProposedFix(
                transform="drop_duplicates",
                description=f"Drop {n_dupes} duplicate rows, keeping the first occurrence",
            ),
        )
    ]
