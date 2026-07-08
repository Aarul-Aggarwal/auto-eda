from auto_eda import detectors, eda
from auto_eda.config import DEFAULT_CONFIG
from auto_eda.findings import score_findings
from auto_eda.llm.provider import LLMProvider
from auto_eda.llm.ranker import rank


class StubProvider(LLMProvider):
    name = "stub"

    def __init__(self, response=None, error=None):
        self._response = response
        self._error = error

    def complete_json(self, prompt, schema):
        if self._error:
            raise self._error
        return self._response


def _findings(dirty_df, profiled):
    return score_findings(detectors.run_all(dirty_df, profiled, DEFAULT_CONFIG))


def test_no_provider_uses_heuristic_order(dirty_df, profiled):
    findings = _findings(dirty_df, profiled)
    result = rank(findings, profiled, provider=None)
    assert not result.used_llm
    assert result.findings == findings


def test_llm_reorders_and_narrates(dirty_df, profiled):
    findings = _findings(dirty_df, profiled)
    reversed_ids = [f.id for f in reversed(findings)]
    provider = StubProvider(response={
        "ranked_ids": reversed_ids,
        "narratives": [{"id": reversed_ids[0], "narrative": "This one matters most."}],
    })
    result = rank(findings, profiled, provider)
    assert result.used_llm
    assert [f.id for f in result.findings] == reversed_ids
    assert result.findings[0].narrative == "This one matters most."


def test_llm_failure_falls_back(dirty_df, profiled):
    findings = _findings(dirty_df, profiled)
    result = rank(findings, profiled, StubProvider(error=RuntimeError("boom")))
    assert not result.used_llm
    assert result.findings == findings
    assert "heuristic" in result.note


def test_invalid_llm_response_falls_back(dirty_df, profiled):
    findings = _findings(dirty_df, profiled)
    result = rank(findings, profiled, StubProvider(response={"wrong": "shape"}))
    assert not result.used_llm


def test_llm_omissions_appended(dirty_df, profiled):
    findings = _findings(dirty_df, profiled)
    provider = StubProvider(response={
        "ranked_ids": [findings[-1].id],  # LLM only returns one id
        "narratives": [],
    })
    result = rank(findings, profiled, provider)
    assert result.used_llm
    assert len(result.findings) == len(findings)
    assert result.findings[0].id == findings[-1].id


def test_eda_class_imbalance(dirty_df):
    from auto_eda.profiling import profile
    from tests.conftest import make_df

    df = make_df({"target": ["no"] * 95 + ["yes"] * 5, "x": list(range(100))})
    prof = profile(df, DEFAULT_CONFIG)
    found = eda.analyze(prof, target="target", config=DEFAULT_CONFIG)
    assert any(f.kind == "class_imbalance" for f in found)
