import subprocess
import sys
from pathlib import Path

import pandas as pd

from auto_eda import cleaning, detectors
from auto_eda.config import DEFAULT_CONFIG
from auto_eda.findings import score_findings
from auto_eda.ingest import load_csv
from auto_eda.profiling import profile


def test_apply_fixes_resolves_issues(dirty_df, profiled):
    found = score_findings(detectors.run_all(dirty_df, profiled, DEFAULT_CONFIG))
    fixes = cleaning.plan_fixes(found)
    cleaned, applied = cleaning.apply_fixes(dirty_df, fixes, DEFAULT_CONFIG)

    assert applied, "expected at least one fix to apply"
    assert not cleaned.duplicated().any()
    assert "const" not in cleaned.columns  # constant column dropped
    assert not (cleaned["city"].dropna() != cleaned["city"].dropna().str.strip()).any()
    # original untouched
    assert dirty_df.duplicated().any()
    assert "const" in dirty_df.columns


def test_generated_script_reproduces_cleaned_csv(tmp_path: Path):
    source = tmp_path / "raw.csv"
    source.write_text(
        "a,b,plan\n1,x,basic\n2,y,Basic\n2,y,Basic\n3,N/A, premium \n4,?,basic\n"
        "5,z,basic\n6,w,premium\n7,v,PREMIUM\n8,u,basic\n9,t,premium\n",
        encoding="utf-8",
    )
    original_bytes = source.read_bytes()

    ingest = load_csv(source, DEFAULT_CONFIG)
    prof = profile(ingest.df, DEFAULT_CONFIG)
    found = score_findings(detectors.run_all(ingest.df, prof, DEFAULT_CONFIG))
    fixes = cleaning.plan_fixes(found)
    cleaned, applied = cleaning.apply_fixes(ingest.df, fixes, DEFAULT_CONFIG)

    cleaned_path = tmp_path / "raw_cleaned.csv"
    cleaned.to_csv(cleaned_path, index=False)

    script_path = tmp_path / "cleaning_script.py"
    script_out = tmp_path / "raw_cleaned_from_script.csv"
    script = cleaning.generate_script(
        applied, source, script_out, ingest.encoding, ingest.delimiter, DEFAULT_CONFIG
    )
    script_path.write_text(script, encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(script_path)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr

    ours = pd.read_csv(cleaned_path, dtype=str, keep_default_na=False)
    theirs = pd.read_csv(script_out, dtype=str, keep_default_na=False)
    pd.testing.assert_frame_equal(ours, theirs)

    # original CSV byte-identical
    assert source.read_bytes() == original_bytes
