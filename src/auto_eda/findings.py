"""The Finding schema — the spine of the tool.

Every detector and EDA check emits Finding objects. The ranker (LLM or
heuristic) orders them; the renderers consume the ordered list.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from .config import Config, DEFAULT_CONFIG


class ProposedFix(BaseModel):
    transform: str  # name in the cleaning.TRANSFORMS registry
    params: dict[str, Any] = Field(default_factory=dict)
    description: str


class Finding(BaseModel):
    id: str
    kind: str
    title: str
    columns: list[str] = Field(default_factory=list)
    affected_rows: int = 0
    affected_pct: float = 0.0  # fraction of rows (0..1)
    evidence: dict[str, Any] = Field(default_factory=dict)
    proposed_fix: Optional[ProposedFix] = None
    severity: float = 0.0  # heuristic score, filled by score_findings
    narrative: Optional[str] = None  # filled by the LLM ranker, if available

    @property
    def is_cleanable(self) -> bool:
        return self.proposed_fix is not None


def score_findings(findings: list[Finding], config: Config = DEFAULT_CONFIG) -> list[Finding]:
    """Deterministic severity: kind weight x (0.3 + 0.7 x affected fraction).

    The floor keeps low-volume but categorically-important issues (e.g. a
    constant column affects "0 rows") from scoring zero.
    """
    for f in findings:
        weight = config.kind_weights.get(f.kind, 0.5)
        f.severity = round(weight * (0.3 + 0.7 * min(f.affected_pct, 1.0)), 4)
    return sorted(findings, key=lambda f: f.severity, reverse=True)


def make_id(kind: str, columns: list[str]) -> str:
    suffix = "-".join(columns) if columns else "dataset"
    return f"{kind}:{suffix}"
