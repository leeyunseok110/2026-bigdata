from pathlib import Path

import numpy as np
import pandas as pd

from src.currency import usd_to_krw


DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "used_cars.csv"
ENRICHED_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "enriched_used_cars.csv"
CURRENT_YEAR = 2026


def _to_number(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype(str).str.replace(r"[^0-9.]", "", regex=True), errors="coerce")


def normalize_transmission(value: object) -> str:
    text = "" if pd.isna(value) else str(value).strip().lower()
    if not text or text in {"unknown", "nan", "–", "-"}:
        return "기타"
    if "manual" in text or "m/t" in text or " mt" in text or text.endswith("mt"):
        return "수동"
    automatic_keywords = [
        "automatic",
        "a/t",
        " at",
        "auto",
        "cvt",
        "dual",
        "dct",
        "shift",
        "fixed gear",
        "variable",
    ]
    if any(keyword in text for keyword in automatic_keywords):
        return "자동"
    return "기타"


def load_used_cars(path: Path | None = None) -> pd.DataFrame:
    if path is None:
        path = ENRICHED_DATA_PATH if ENRICHED_DATA_PATH.exists() else DATA_PATH

    df = pd.read_csv(path)

    df["price"] = _to_number(df["price"])
    df["price_usd"] = df["price"]
    df["price"] = usd_to_krw(df["price_usd"])
    df["milage"] = _to_number(df["milage"])
    df["model_year"] = pd.to_numeric(df["model_year"], errors="coerce")

    if "epa_annual_fuel_cost" in df.columns:
        df["epa_annual_fuel_cost_krw"] = usd_to_krw(pd.to_numeric(df["epa_annual_fuel_cost"], errors="coerce"))

    for column in ["fuel_type", "accident", "clean_title", "transmission", "ext_col", "int_col"]:
        df[column] = df[column].fillna("Unknown")

    df["transmission_original"] = df["transmission"]
    df["transmission"] = df["transmission"].map(normalize_transmission)

    df = df.dropna(subset=["price", "milage", "model_year"])
    df["model_year"] = df["model_year"].astype(int)
    df["car_age"] = (CURRENT_YEAR - df["model_year"]).clip(lower=0)
    df["price_per_mile"] = np.where(df["milage"] > 0, df["price"] / df["milage"], np.nan)
    df["accident_flag"] = np.where(
        df["accident"].str.contains("accident|damage", case=False, na=False),
        "사고/손상 이력 있음",
        "사고 이력 없음",
    )
    df["brand_model"] = df["brand"].astype(str) + " " + df["model"].astype(str)

    if "external_epa_matched" in df.columns:
        df["external_epa_matched"] = df["external_epa_matched"].fillna(False).astype(bool)
    if "external_nhtsa_matched" in df.columns:
        df["external_nhtsa_matched"] = df["external_nhtsa_matched"].fillna(False).astype(bool)

    return df


def filter_cars(
    df: pd.DataFrame,
    brands: list[str],
    fuel_types: list[str],
    accident_flags: list[str],
    year_range: tuple[int, int],
    price_range: tuple[int, int],
    milage_range: tuple[int, int],
) -> pd.DataFrame:
    filtered = df[
        df["brand"].isin(brands)
        & df["fuel_type"].isin(fuel_types)
        & df["accident_flag"].isin(accident_flags)
        & df["model_year"].between(*year_range)
        & df["price"].between(*price_range)
        & df["milage"].between(*milage_range)
    ]
    return filtered.copy()
