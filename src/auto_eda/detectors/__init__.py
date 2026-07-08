"""Detector registry: each detector takes (df, profile, config) -> list[Finding]."""

from __future__ import annotations

import pandas as pd

from ..config import Config, DEFAULT_CONFIG
from ..findings import Finding
from ..profiling import DatasetProfile
from . import duplicates, formatting, missing, outliers, structure, types

ALL_DETECTORS = [
    duplicates.detect,
    missing.detect,
    types.detect,
    formatting.detect,
    outliers.detect,
    structure.detect,
]


def run_all(
    df: pd.DataFrame, profile: DatasetProfile, config: Config = DEFAULT_CONFIG
) -> list[Finding]:
    findings: list[Finding] = []
    for detect in ALL_DETECTORS:
        findings.extend(detect(df, profile, config))
    return findings
