from pathlib import Path

from auto_eda.config import DEFAULT_CONFIG
from auto_eda.ingest import load_csv


def test_comma_csv(tmp_path: Path):
    p = tmp_path / "a.csv"
    p.write_text("x,y\n1,2\n3,4\n", encoding="utf-8")
    r = load_csv(p, DEFAULT_CONFIG)
    assert r.delimiter == ","
    assert list(r.df.columns) == ["x", "y"]
    assert r.total_rows == 2
    assert not r.sampled


def test_semicolon_csv(tmp_path: Path):
    p = tmp_path / "b.csv"
    p.write_text("x;y\n1;2\n3;4\n", encoding="utf-8")
    r = load_csv(p, DEFAULT_CONFIG)
    assert r.delimiter == ";"
    assert list(r.df.columns) == ["x", "y"]


def test_latin1_encoding(tmp_path: Path):
    p = tmp_path / "c.csv"
    p.write_bytes("name,city\nJosé,Málaga\nRené,Orléans\n".encode("latin-1"))
    r = load_csv(p, DEFAULT_CONFIG)
    assert "José" in r.df["name"].values


def test_values_loaded_as_strings(tmp_path: Path):
    p = tmp_path / "d.csv"
    p.write_text("x\n1\nN/A\n\n", encoding="utf-8")
    r = load_csv(p, DEFAULT_CONFIG)
    assert r.df["x"].tolist() == ["1", "N/A"]
