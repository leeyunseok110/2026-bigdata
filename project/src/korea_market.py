from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.external_data import make_model_key, normalize_make


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
KOREA_REFERENCE_PATH = DATA_DIR / "korea_market_reference.csv"
KOREA_TEMPLATE_PATH = DATA_DIR / "korea_market_reference_template.csv"

KOREA_REFERENCE_COLUMNS = [
    "brand",
    "model",
    "model_year",
    "reference_price_krw",
    "reference_source",
    "reference_date",
    "note",
]


def normalize_reference(df: pd.DataFrame) -> pd.DataFrame:
    ref = df.copy()
    for column in KOREA_REFERENCE_COLUMNS:
        if column not in ref.columns:
            ref[column] = pd.NA

    ref["brand"] = ref["brand"].astype(str).str.strip()
    ref["model"] = ref["model"].astype(str).str.strip()
    ref["model_year"] = pd.to_numeric(ref["model_year"], errors="coerce")
    ref["reference_price_krw"] = pd.to_numeric(ref["reference_price_krw"], errors="coerce")
    ref = ref.dropna(subset=["brand", "model", "model_year", "reference_price_krw"]).copy()
    ref["model_year"] = ref["model_year"].astype(int)
    ref["make_norm"] = ref["brand"].map(normalize_make)
    ref["model_key"] = [make_model_key(model, brand) for model, brand in zip(ref["model"], ref["brand"])]
    ref = ref.sort_values(["reference_date", "reference_source"], na_position="first")
    return ref.drop_duplicates(["make_norm", "model_key", "model_year"], keep="last")


def load_korea_reference(path: Path = KOREA_REFERENCE_PATH) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame(columns=KOREA_REFERENCE_COLUMNS + ["make_norm", "model_key"])
    return normalize_reference(pd.read_csv(path))


def save_korea_reference(df: pd.DataFrame, path: Path = KOREA_REFERENCE_PATH) -> pd.DataFrame:
    normalized = normalize_reference(df)
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized[KOREA_REFERENCE_COLUMNS].to_csv(path, index=False, encoding="utf-8-sig")
    return normalized


def find_korea_reference(reference: pd.DataFrame, brand: str, model: str, model_year: int) -> pd.Series | None:
    if reference.empty:
        return None

    make_norm = normalize_make(brand)
    model_key = make_model_key(model, brand)
    exact = reference[
        (reference["make_norm"] == make_norm)
        & (reference["model_key"] == model_key)
        & (reference["model_year"] == int(model_year))
    ]
    if not exact.empty:
        return exact.iloc[-1]

    nearby = reference[
        (reference["make_norm"] == make_norm)
        & (reference["model_key"] == model_key)
        & reference["model_year"].between(int(model_year) - 1, int(model_year) + 1)
    ].copy()
    if nearby.empty:
        return None
    nearby["year_gap"] = (nearby["model_year"] - int(model_year)).abs()
    return nearby.sort_values(["year_gap", "model_year"]).iloc[0]


def create_reference_template(used_cars: pd.DataFrame, path: Path = KOREA_TEMPLATE_PATH) -> pd.DataFrame:
    template = (
        used_cars[["brand", "model", "model_year"]]
        .drop_duplicates()
        .sort_values(["brand", "model", "model_year"])
        .head(200)
        .copy()
    )
    template["reference_price_krw"] = ""
    template["reference_source"] = "보험개발원/자동차365"
    template["reference_date"] = ""
    template["note"] = ""
    path.parent.mkdir(parents=True, exist_ok=True)
    template[KOREA_REFERENCE_COLUMNS].to_csv(path, index=False, encoding="utf-8-sig")
    return template[KOREA_REFERENCE_COLUMNS]
