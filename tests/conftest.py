import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from auto_eda.config import DEFAULT_CONFIG  # noqa: E402
from auto_eda.profiling import profile  # noqa: E402


def make_df(rows: dict[str, list]) -> pd.DataFrame:
    """Build a string-typed frame the way ingest.load_csv would."""
    return pd.DataFrame({k: [str(v) for v in vals] for k, vals in rows.items()})


@pytest.fixture
def clean_df() -> pd.DataFrame:
    n = 100
    return make_df({
        "id": list(range(n)),
        "value": [50 + (i % 25) for i in range(n)],
        "group": [["a", "b", "c"][i % 3] for i in range(n)],
    })


@pytest.fixture
def dirty_df() -> pd.DataFrame:
    n = 100
    rows = {
        "id": list(range(n)),
        "amount": [str(100 + i) for i in range(n - 10)] + ["N/A", "-", "", "?"] + ["oops"] * 6,
        "city": [["NY", "ny", "Boston", " Boston "][i % 4] for i in range(n)],
        "joined": [f"2023-{(i % 12) + 1:02d}-15" for i in range(n)],
        "const": ["same"] * n,
    }
    df = make_df(rows)
    return pd.concat([df, df.iloc[:10]], ignore_index=True)  # 10 duplicate rows


@pytest.fixture
def profiled(dirty_df):
    return profile(dirty_df, DEFAULT_CONFIG)
