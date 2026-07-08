from auto_eda import detectors
from auto_eda.config import DEFAULT_CONFIG
from auto_eda.findings import score_findings
from auto_eda.profiling import profile


def kinds(findings):
    return {f.kind for f in findings}


def test_dirty_dataset_fires_expected_detectors(dirty_df, profiled):
    found = detectors.run_all(dirty_df, profiled, DEFAULT_CONFIG)
    ks = kinds(found)
    assert "duplicate_rows" in ks
    assert "disguised_nulls" in ks       # N/A, -, "", ? in amount
    assert "case_inconsistency" in ks    # NY vs ny
    assert "whitespace" in ks            # " Boston "
    assert "constant_column" in ks       # const
    assert "parseable_dates" in ks       # joined
    assert "mixed_types" in ks           # amount: mostly numeric + "oops"


def test_clean_dataset_is_quiet(clean_df):
    prof = profile(clean_df, DEFAULT_CONFIG)
    found = detectors.run_all(clean_df, prof, DEFAULT_CONFIG)
    ks = kinds(found)
    # numeric-stored-as-text is expected (CSV input is always text); nothing else
    assert ks <= {"type_mismatch", "id_like_column"}


def test_severity_scoring_orders_findings(dirty_df, profiled):
    found = score_findings(detectors.run_all(dirty_df, profiled, DEFAULT_CONFIG))
    scores = [f.severity for f in found]
    assert scores == sorted(scores, reverse=True)
    assert all(0 < s <= 1 for s in scores)


def test_outlier_detector():
    from tests.conftest import make_df

    values = [100 + (i % 10) for i in range(200)] + [99999] * 3
    df = make_df({"x": values})
    prof = profile(df, DEFAULT_CONFIG)
    found = detectors.run_all(df, prof, DEFAULT_CONFIG)
    outlier_findings = [f for f in found if f.kind == "outliers"]
    assert len(outlier_findings) == 1
    assert outlier_findings[0].affected_rows == 3
