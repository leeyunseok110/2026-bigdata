from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.external_data import enrich_used_cars  # noqa: E402


DATA_DIR = PROJECT_ROOT / "data"
EXTERNAL_DIR = DATA_DIR / "external" / "carfax_latest"
RAW_DIR = EXTERNAL_DIR / "raw"
LATEST_NORMALIZED_PATH = EXTERNAL_DIR / "carfax_latest_2024_2026.csv"
LATEST_SPECS_PATH = EXTERNAL_DIR / "carfax_latest_2024_2026_specs_without_price.csv"
AUGMENTED_PATH = DATA_DIR / "used_cars_augmented.csv"
ENRICHED_PATH = DATA_DIR / "enriched_used_cars.csv"

GITHUB_API_URL = "https://api.github.com/repos/rebrowser/carfax-dataset/contents/car-listings/data"


def _format_price(value) -> str:
    if pd.isna(value):
        return ""
    return f"${float(value):,.0f}"


def _format_mileage(value) -> str:
    if pd.isna(value):
        return ""
    return f"{float(value):,.0f} mi."


def _clean_text(value, fallback: str = "Unknown") -> str:
    if pd.isna(value):
        return fallback
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "unspecified", "[premium]"}:
        return fallback
    return text


def _combine_model(row: pd.Series) -> str:
    model = _clean_text(row.get("model"), "")
    trim = _clean_text(row.get("trim"), "")
    if trim and trim.lower() not in model.lower():
        return f"{model} {trim}".strip()
    return model or "Unknown"


def list_csv_files() -> list[dict]:
    response = requests.get(GITHUB_API_URL, timeout=30)
    response.raise_for_status()
    files = response.json()
    return sorted(
        [file for file in files if file["name"].endswith(".csv")],
        key=lambda item: item["name"],
    )


def download_files(files: list[dict]) -> list[Path]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    downloaded = []
    for file in files:
        path = RAW_DIR / file["name"]
        if not path.exists() or path.stat().st_size != file["size"]:
            response = requests.get(file["download_url"], timeout=60)
            response.raise_for_status()
            path.write_bytes(response.content)
        downloaded.append(path)
    return downloaded


def _normalize_rows(raw: pd.DataFrame, source_name: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "brand": raw["make"].map(_clean_text),
            "model": raw.apply(_combine_model, axis=1),
            "model_year": raw["year"].astype(int),
            "milage": raw["mileage"].map(_format_mileage),
            "fuel_type": raw["fuelType"].map(_clean_text),
            "engine": raw["engine"].map(_clean_text),
            "transmission": raw["transmission"].map(_clean_text),
            "ext_col": raw["exteriorColor"].map(_clean_text),
            "int_col": raw["interiorColor"].map(_clean_text),
            "accident": raw["noAccidents"].map(
                lambda value: "None reported" if bool(value) else "At least 1 accident or damage reported"
            ),
            "clean_title": "Yes",
            "price": raw["market_price_usd"].map(_format_price) if "market_price_usd" in raw else "",
            "data_source": source_name,
            "listing_date": raw["snapshot_date"],
            "body_style_source": raw.get("bodyStyle"),
            "mpg_combined_source": raw.get("mpgCombined"),
        }
    )


def normalize_carfax(paths: list[Path]) -> tuple[pd.DataFrame, pd.DataFrame]:
    frames = []
    usecols = [
        "year",
        "make",
        "model",
        "trim",
        "mileage",
        "fuelType",
        "engine",
        "transmission",
        "exteriorColor",
        "interiorColor",
        "noAccidents",
        "listPrice",
        "currentPrice",
        "onePrice",
        "vehicleCondition",
        "bodyStyle",
        "mpgCombined",
        "firstSeen",
        "listingId",
    ]
    for path in paths:
        frame = pd.read_csv(path, usecols=lambda column: column in usecols, low_memory=False)
        frame["snapshot_date"] = path.stem
        frames.append(frame)

    raw = pd.concat(frames, ignore_index=True)
    raw["year"] = pd.to_numeric(raw["year"], errors="coerce")
    raw["currentPrice"] = pd.to_numeric(raw["currentPrice"], errors="coerce")
    raw["listPrice"] = pd.to_numeric(raw.get("listPrice"), errors="coerce")
    raw["onePrice"] = pd.to_numeric(raw.get("onePrice"), errors="coerce")
    raw["market_price_usd"] = raw["currentPrice"].fillna(raw["onePrice"]).fillna(raw["listPrice"])
    raw["mileage"] = pd.to_numeric(raw["mileage"], errors="coerce")
    latest_specs = raw[
        raw["year"].between(2024, 2026)
        & raw["mileage"].notna()
        & raw["vehicleCondition"].astype(str).str.contains("Used|Certified", case=False, na=False)
    ].copy()
    specs_key = (
        latest_specs["make"].astype(str)
        + "|"
        + latest_specs["model"].astype(str)
        + "|"
        + latest_specs["trim"].astype(str)
        + "|"
        + latest_specs["year"].astype(str)
        + "|"
        + latest_specs["mileage"].astype(str)
        + "|"
        + latest_specs["snapshot_date"].astype(str)
    )
    latest_specs = latest_specs.loc[~specs_key.duplicated()].copy()

    raw = raw[
        raw["year"].between(2024, 2026)
        & raw["market_price_usd"].notna()
        & raw["mileage"].notna()
        & raw["vehicleCondition"].astype(str).str.contains("Used|Certified", case=False, na=False)
    ].copy()

    price_key = (
        raw["make"].astype(str)
        + "|"
        + raw["model"].astype(str)
        + "|"
        + raw["trim"].astype(str)
        + "|"
        + raw["year"].astype(str)
        + "|"
        + raw["mileage"].astype(str)
        + "|"
        + raw["market_price_usd"].astype(str)
        + "|"
        + raw["snapshot_date"].astype(str)
    )
    raw = raw.loc[~price_key.duplicated()].copy()
    return (
        _normalize_rows(raw, "carfax_rebrowser_sample_oneprice"),
        _normalize_rows(latest_specs, "carfax_rebrowser_sample_specs_only"),
    )


def build_augmented_dataset(latest: pd.DataFrame) -> pd.DataFrame:
    base = pd.read_csv(DATA_DIR / "used_cars.csv")
    base["data_source"] = base.get("data_source", "original_used_cars")
    base["listing_date"] = base.get("listing_date", "")
    base["body_style_source"] = base.get("body_style_source", "")
    base["mpg_combined_source"] = base.get("mpg_combined_source", "")

    combined = pd.concat([base, latest], ignore_index=True, sort=False)
    dedupe_key = (
        combined["brand"].astype(str).str.upper()
        + "|"
        + combined["model"].astype(str).str.upper()
        + "|"
        + combined["model_year"].astype(str)
        + "|"
        + combined["milage"].astype(str)
        + "|"
        + combined["price"].astype(str)
    )
    combined = combined.loc[~dedupe_key.duplicated()].copy()
    return combined


def main() -> None:
    files = list_csv_files()
    paths = download_files(files)
    latest, latest_specs = normalize_carfax(paths)
    LATEST_NORMALIZED_PATH.parent.mkdir(parents=True, exist_ok=True)
    latest.to_csv(LATEST_NORMALIZED_PATH, index=False, encoding="utf-8-sig")
    latest_specs.to_csv(LATEST_SPECS_PATH, index=False, encoding="utf-8-sig")

    augmented = build_augmented_dataset(latest)
    augmented.to_csv(AUGMENTED_PATH, index=False, encoding="utf-8-sig")
    enriched = enrich_used_cars(used_cars_path=AUGMENTED_PATH, output_path=ENRICHED_PATH)

    year_counts = enriched["model_year"].value_counts().sort_index()
    print(f"Downloaded daily files: {len(paths):,}")
    print(f"Latest 2024-2026 specs rows: {len(latest_specs):,}")
    print(f"Latest 2024-2026 rows: {len(latest):,}")
    print(f"Augmented rows: {len(augmented):,}")
    print(f"Enriched rows: {len(enriched):,}")
    print("2024-2026 row counts:")
    print(year_counts[year_counts.index.to_series().between(2024, 2026)].to_string())
    print(f"Saved: {LATEST_NORMALIZED_PATH}")
    print(f"Saved: {LATEST_SPECS_PATH}")
    print(f"Saved: {AUGMENTED_PATH}")
    print(f"Saved: {ENRICHED_PATH}")


if __name__ == "__main__":
    main()
