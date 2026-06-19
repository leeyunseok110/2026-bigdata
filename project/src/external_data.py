from __future__ import annotations

from pathlib import Path
import re

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
EXTERNAL_DIR = DATA_DIR / "external"
USED_CARS_PATH = DATA_DIR / "used_cars.csv"
ENRICHED_CARS_PATH = DATA_DIR / "enriched_used_cars.csv"
EPA_SUMMARY_PATH = EXTERNAL_DIR / "epa_vehicle_summary.csv"
NHTSA_SUMMARY_PATH = EXTERNAL_DIR / "nhtsa_recall_summary.csv"

TRIM_WORDS = {
    "BASE",
    "LIMITED",
    "PREMIUM",
    "PLATINUM",
    "SPORT",
    "SE",
    "SEL",
    "SL",
    "SLE",
    "SLT",
    "SR",
    "SR5",
    "SV",
    "EX",
    "LX",
    "LE",
    "XLE",
    "XLT",
    "LT",
    "LS",
    "LARIAT",
    "TOURING",
    "LUXURY",
    "STANDARD",
    "EDITION",
}


def normalize_text(value: object) -> str:
    text = "" if pd.isna(value) else str(value).upper()
    text = text.replace("&", " AND ")
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_make(value: object) -> str:
    text = normalize_text(value)
    replacements = {
        "ASTON": "ASTON MARTIN",
        "MERCEDES": "MERCEDES BENZ",
        "MERCEDES BENZ": "MERCEDES BENZ",
        "LAND": "LAND ROVER",
        "LANDROVER": "LAND ROVER",
        "VW": "VOLKSWAGEN",
    }
    return replacements.get(text, text)


def _strip_make_prefix(tokens: list[str], make: object | None) -> list[str]:
    if make is None:
        return tokens
    make_tokens = normalize_make(make).split()
    for prefix_length in range(min(len(make_tokens), len(tokens)), 0, -1):
        if tokens[:prefix_length] == make_tokens[-prefix_length:]:
            return tokens[prefix_length:]
    return tokens


def _dedupe_repeated_tokens(tokens: list[str]) -> list[str]:
    if len(tokens) % 2:
        return tokens
    midpoint = len(tokens) // 2
    if tokens[:midpoint] == tokens[midpoint:]:
        return tokens[:midpoint]
    return tokens


def make_model_key(value: object, make: object | None = None) -> str:
    text = normalize_text(value)
    if not text:
        return ""
    tokens = _dedupe_repeated_tokens(_strip_make_prefix(text.split(), make))
    if not tokens:
        return ""
    if tokens[0] == "MODEL" and len(tokens) >= 2:
        return " ".join(tokens[:2])
    lexus_style = {"ES", "GS", "GX", "IS", "LC", "LS", "LX", "NX", "RC", "RX", "UX"}
    if tokens[0] in lexus_style and len(tokens) >= 2 and tokens[1].isdigit():
        return " ".join(tokens[:2])

    key_tokens: list[str] = []
    for token in tokens:
        if key_tokens and token in TRIM_WORDS:
            break
        if key_tokens and re.fullmatch(r"\d+[A-Z]*", token):
            break
        key_tokens.append(token)
        if len(key_tokens) >= 3:
            break
        if len(key_tokens) >= 2 and token in {"SERIES", "CLASS"}:
            break
    return " ".join(key_tokens)


def enrich_used_cars(
    used_cars_path: Path = USED_CARS_PATH,
    output_path: Path = ENRICHED_CARS_PATH,
    rebuild_external: bool = False,
) -> pd.DataFrame:
    if rebuild_external:
        raise NotImplementedError("External raw rebuild is not needed for the current import workflow.")

    used = pd.read_csv(used_cars_path)
    used["make_norm"] = used["brand"].map(normalize_make)
    used["model_key"] = [make_model_key(model, make) for model, make in zip(used["model"], used["brand"])]
    used["model_year"] = pd.to_numeric(used["model_year"], errors="coerce")

    epa = pd.read_csv(EPA_SUMMARY_PATH)
    recalls = pd.read_csv(NHTSA_SUMMARY_PATH)

    merged = used.merge(epa, on=["make_norm", "model_key", "model_year"], how="left")
    merged = merged.merge(recalls, on=["make_norm", "model_key", "model_year"], how="left")

    for column in ["nhtsa_recall_count", "nhtsa_affected_units"]:
        merged[column] = pd.to_numeric(merged[column], errors="coerce").fillna(0).astype(int)
    for column in ["nhtsa_do_not_drive", "nhtsa_park_outside"]:
        merged[column] = merged[column].astype("boolean").fillna(False).astype(bool)

    merged["external_epa_matched"] = merged["epa_combined_mpg"].notna()
    merged["external_nhtsa_matched"] = merged["nhtsa_recall_count"].gt(0)
    merged.to_csv(output_path, index=False, encoding="utf-8-sig")
    return merged
