from auto_eda import cleaning, detectors
from auto_eda.config import DEFAULT_CONFIG
from auto_eda.profiling import profile
from auto_eda.quality import band_word, compute_quality, grade_for

DIMENSIONS = {"Completeness", "Validity", "Consistency", "Uniqueness", "Structure"}


def _quality(df):
    prof = profile(df, DEFAULT_CONFIG)
    findings = detectors.run_all(df, prof, DEFAULT_CONFIG)
    return compute_quality(prof, findings, DEFAULT_CONFIG)


def test_grade_bands():
    assert grade_for(100) == "A+"
    assert grade_for(97) == "A+"
    assert grade_for(91) == "A-"
    assert grade_for(60) == "D-"
    assert grade_for(59.9) == "F"
    assert grade_for(0) == "F"


def test_band_word():
    assert band_word(95) == "EXCELLENT"
    assert band_word(80) == "GOOD"
    assert band_word(65) == "FAIR"
    assert band_word(30) == "POOR"


def test_clean_data_scores_high(clean_df):
    q = _quality(clean_df)
    # numeric-stored-as-text and id-like are benign CSV artifacts, excluded from
    # scoring — a structurally clean frame should still land an A.
    assert q.overall >= 95
    assert q.grade in {"A+", "A", "A-"}
    assert {d.name for d in q.dimensions} == DIMENSIONS


def test_dirty_data_scores_lower(dirty_df, clean_df):
    dirty = _quality(dirty_df)
    clean = _quality(clean_df)
    assert dirty.overall < clean.overall
    assert all(0 <= d.score <= 100 for d in dirty.dimensions)


def test_cleaning_improves_score(dirty_df):
    prof = profile(dirty_df, DEFAULT_CONFIG)
    raw = detectors.run_all(dirty_df, prof, DEFAULT_CONFIG)
    before = compute_quality(prof, raw, DEFAULT_CONFIG)

    fixes = cleaning.plan_fixes(raw)
    cleaned, _ = cleaning.apply_fixes(dirty_df, fixes, DEFAULT_CONFIG)
    cprof = profile(cleaned.astype(str).where(cleaned.notna()), DEFAULT_CONFIG)
    after = compute_quality(cprof, detectors.run_all(cleaned, cprof, DEFAULT_CONFIG), DEFAULT_CONFIG)

    assert after.overall > before.overall
    before_scores = {d.name: d.score for d in before.dimensions}
    after_scores = {d.name: d.score for d in after.dimensions}
    # Duplicates are gone, disguised nulls / whitespace / casing resolved.
    assert after_scores["Uniqueness"] == 100.0
    assert after_scores["Consistency"] == 100.0
    assert after_scores["Completeness"] >= before_scores["Completeness"] - 5


def test_empty_dataset_does_not_crash():
    import pandas as pd

    prof = profile(pd.DataFrame(), DEFAULT_CONFIG)
    q = compute_quality(prof, [], DEFAULT_CONFIG)
    assert 0 <= q.overall <= 100
