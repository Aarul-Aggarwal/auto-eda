"""Builds the summary payload and prompt for the LLM ranker.

The LLM never sees raw data — only schema, aggregates, up to a handful of
sample values per column, and the deterministic findings with evidence.
"""

from __future__ import annotations

import json
from typing import Any

from ..config import Config, DEFAULT_CONFIG
from ..findings import Finding
from ..profiling import DatasetProfile

RANKING_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "ranked_ids": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Finding ids ordered from most to least important",
        },
        "narratives": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "narrative": {"type": "string"},
                },
                "required": ["id", "narrative"],
                "additionalProperties": False,
            },
            "description": "One-sentence plain-language takeaway per top finding",
        },
    },
    "required": ["ranked_ids", "narratives"],
    "additionalProperties": False,
}


def build_summary(
    profile: DatasetProfile,
    findings: list[Finding],
    target: str | None,
    config: Config = DEFAULT_CONFIG,
) -> dict[str, Any]:
    return {
        "shape": {"rows": profile.n_rows, "columns": profile.n_cols},
        "target_column": target,
        "columns": {
            name: {
                "inferred_type": col.inferred_type,
                "missing_pct": round(col.n_missing / max(profile.n_rows, 1), 4),
                "n_unique": col.n_unique,
                "sample_values": col.sample_values[: config.llm_sample_values],
            }
            for name, col in profile.columns.items()
        },
        "findings": [
            {
                "id": f.id,
                "kind": f.kind,
                "title": f.title,
                "columns": f.columns,
                "affected_pct": round(f.affected_pct, 4),
                "heuristic_severity": f.severity,
                "evidence": f.evidence,
            }
            for f in findings
        ],
    }


def build_prompt(summary: dict[str, Any], config: Config = DEFAULT_CONFIG) -> str:
    return f"""You are a senior data scientist reviewing an automated data-quality \
and EDA scan of a dataset you have never seen. Below is a JSON summary: dataset \
shape, per-column aggregates with a few sample values, and a list of findings \
produced by deterministic checks, each with a heuristic severity score.

Re-rank the findings by what actually matters for someone about to analyze or \
model this dataset. Judge by impact, not by category: an issue corrupting a key \
column outranks a cosmetic issue affecting more rows. Consider interactions the \
heuristics can't see (e.g. missingness concentrated in the target column, an \
outlier pattern that suggests a unit error, near-duplicate categories that would \
split a group-by). Demote findings that are noise for this particular dataset \
(e.g. an "ID-like column" finding on an obvious primary key).

Return every finding id exactly once in `ranked_ids` (most important first), and \
a one-sentence, plain-language `narrative` for each of the top \
{config.llm_max_findings_ranked} explaining why it matters and what to do.

Dataset summary:
{json.dumps(summary, default=str)}"""
