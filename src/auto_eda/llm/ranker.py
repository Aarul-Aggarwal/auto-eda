"""Ranks findings via the resolved LLM provider, with heuristic fallback."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ValidationError

from ..config import Config, DEFAULT_CONFIG
from ..findings import Finding
from ..profiling import DatasetProfile
from .prompts import RANKING_SCHEMA, build_prompt, build_summary
from .provider import LLMProvider


class _Narrative(BaseModel):
    id: str
    narrative: str


class _RankingResponse(BaseModel):
    ranked_ids: list[str]
    narratives: list[_Narrative]


@dataclass
class RankResult:
    findings: list[Finding]  # in final display order
    used_llm: bool
    provider_name: str | None
    note: str | None = None  # shown to the user when something degraded


def rank(
    findings: list[Finding],
    profile: DatasetProfile,
    provider: LLMProvider | None,
    target: str | None = None,
    config: Config = DEFAULT_CONFIG,
) -> RankResult:
    """LLM re-ranking on top of heuristic order; falls back on any failure.

    `findings` must already be heuristic-sorted (score_findings), which is
    both the fallback order and the order the LLM sees.
    """
    if provider is None or not findings:
        return RankResult(findings=findings, used_llm=False, provider_name=None)

    try:
        summary = build_summary(profile, findings, target, config)
        raw = provider.complete_json(build_prompt(summary, config), RANKING_SCHEMA)
        parsed = _RankingResponse.model_validate(raw)
    except (ValidationError, Exception) as exc:  # noqa: BLE001 - any failure degrades gracefully
        return RankResult(
            findings=findings,
            used_llm=False,
            provider_name=provider.name,
            note=f"LLM ranking failed ({type(exc).__name__}); using heuristic order",
        )

    by_id = {f.id: f for f in findings}
    ordered = [by_id[i] for i in parsed.ranked_ids if i in by_id]
    # Anything the LLM dropped keeps its heuristic position at the end
    missing = [f for f in findings if f.id not in set(parsed.ranked_ids)]
    ordered.extend(missing)

    for n in parsed.narratives:
        if n.id in by_id:
            by_id[n.id].narrative = n.narrative

    note = None
    if missing:
        note = f"LLM omitted {len(missing)} finding(s); appended in heuristic order"
    return RankResult(findings=ordered, used_llm=True, provider_name=provider.name, note=note)
