"""Robust CSV loading: encoding detection, delimiter sniffing, optional sampling."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from charset_normalizer import from_path

from .config import Config, DEFAULT_CONFIG


@dataclass
class IngestResult:
    df: pd.DataFrame
    path: Path
    encoding: str
    delimiter: str
    total_rows: int
    sampled: bool


def detect_encoding(path: Path) -> str:
    best = from_path(path).best()
    return best.encoding if best else "utf-8"


def detect_delimiter(path: Path, encoding: str) -> str:
    with open(path, encoding=encoding, errors="replace", newline="") as f:
        head = f.read(64 * 1024)
    try:
        return csv.Sniffer().sniff(head, delimiters=",;\t|").delimiter
    except csv.Error:
        return ","


def load_csv(path: str | Path, config: Config = DEFAULT_CONFIG) -> IngestResult:
    """Load a CSV read-only with sniffed encoding/delimiter.

    All columns are read as object dtype so detectors see the raw values;
    type inference is itself one of the things we report on.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"No such file: {path}")

    encoding = detect_encoding(path)
    delimiter = detect_delimiter(path, encoding)

    df = pd.read_csv(
        path,
        encoding=encoding,
        sep=delimiter,
        dtype=str,
        keep_default_na=False,  # disguised-null detection needs the raw strings
        skipinitialspace=False,
        on_bad_lines="warn",
        engine="python",
    )
    total_rows = len(df)

    sampled = total_rows > config.sample_row_threshold
    if sampled:
        df = df.sample(n=config.sample_size, random_state=config.sample_seed)
        df = df.reset_index(drop=True)

    return IngestResult(
        df=df,
        path=path,
        encoding=encoding,
        delimiter=delimiter,
        total_rows=total_rows,
        sampled=sampled,
    )
