"""Central tuning knobs for detection thresholds, severity weights, and sampling."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Config:
    # Ingest
    sample_row_threshold: int = 500_000  # profile a sample above this many rows
    sample_size: int = 200_000
    sample_seed: int = 42

    # Missing values
    disguised_nulls: tuple[str, ...] = (
        "", "n/a", "na", "none", "null", "-", "--", "?", "missing", "unknown", "#n/a",
    )
    high_missing_pct: float = 0.40  # column flagged as mostly-missing above this

    # Types
    numeric_parse_pct: float = 0.95  # object column parses as numeric for >= this share
    date_parse_pct: float = 0.95

    # Formatting
    category_max_unique: int = 50  # only look for near-matches in low-cardinality columns
    whitespace_flag_pct: float = 0.01

    # Outliers
    iqr_multiplier: float = 1.5
    zscore_threshold: float = 3.5  # modified z-score (MAD-based)
    outlier_flag_pct: float = 0.005  # flag only if at least this share of rows

    # Structure
    high_cardinality_ratio: float = 0.95  # unique/count above this on object col -> ID-like
    high_correlation: float = 0.95

    # EDA
    skew_threshold: float = 2.0
    class_imbalance_ratio: float = 5.0  # majority/minority above this -> imbalanced

    # Severity weights per finding kind (multiplied by affected fraction)
    kind_weights: dict[str, float] = field(default_factory=lambda: {
        "duplicate_rows": 0.9,
        "missing_values": 0.8,
        "disguised_nulls": 0.85,
        "type_mismatch": 0.9,
        "mixed_types": 0.9,
        "parseable_dates": 0.6,
        "whitespace": 0.5,
        "case_inconsistency": 0.6,
        "category_near_match": 0.7,
        "outliers": 0.6,
        "constant_column": 0.7,
        "id_like_column": 0.3,
        "high_correlation": 0.5,
        "skewed_distribution": 0.4,
        "class_imbalance": 0.8,
    })

    # LLM
    llm_sample_values: int = 10  # max sample values per column sent to the LLM
    llm_max_findings_ranked: int = 15
    ollama_url: str = "http://localhost:11434"
    anthropic_model: str = "claude-opus-4-8"
    ollama_model: str = ""  # empty = first available model

    # Rendering
    top_n_charts: int = 10


DEFAULT_CONFIG = Config()
