from __future__ import annotations

import numpy as np
import pandas as pd


BODY_TYPE_ORDER = ["Sedan", "SUV", "Truck", "Van", "Wagon", "Sports", "Other"]


def classify_body_type(vehicle_class: object, model: object = "") -> str:
    text = f"{vehicle_class if pd.notna(vehicle_class) else ''} {model if pd.notna(model) else ''}".upper()
    if any(word in text for word in ["SPORT UTILITY", "SUV", "CROSSOVER"]):
        return "SUV"
    if "PICKUP" in text or "TRUCK" in text or "F-150" in text or "RAM 1500" in text:
        return "Truck"
    if "VAN" in text or "MINIVAN" in text:
        return "Van"
    if "WAGON" in text:
        return "Wagon"
    if "TWO SEATERS" in text or "COUPE" in text or "CONVERTIBLE" in text:
        return "Sports"
    if any(word in text for word in ["COMPACT CARS", "MIDSIZE CARS", "LARGE CARS", "SUBCOMPACT", "MINICOMPACT"]):
        return "Sedan"
    return "Other"


def estimate_seat_group(body_type: str, vehicle_class: object) -> str:
    text = "" if pd.isna(vehicle_class) else str(vehicle_class).upper()
    if "TWO SEATERS" in text or body_type == "Sports":
        return "2 seats"
    if body_type == "Van" or "STANDARD SPORT UTILITY" in text:
        return "6+ seats"
    if body_type in {"SUV", "Truck", "Wagon"}:
        return "4-5 seats"
    return "4-5 seats"


def add_recommendation_features(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    result["body_type"] = [
        classify_body_type(vehicle_class, model)
        for vehicle_class, model in zip(result.get("epa_vehicle_class", ""), result["model"])
    ]
    result["seat_group"] = [
        estimate_seat_group(body_type, vehicle_class)
        for body_type, vehicle_class in zip(result["body_type"], result.get("epa_vehicle_class", ""))
    ]
    mpg = pd.to_numeric(result.get("epa_combined_mpg"), errors="coerce")
    # EV MPGe can dominate ordinary MPG. Cap it so efficient EVs help, but do not swamp value.
    result["combined_mpg_for_score"] = mpg.clip(upper=60)
    result["recall_count_for_score"] = pd.to_numeric(result.get("nhtsa_recall_count"), errors="coerce").fillna(0)
    result["has_epa_data"] = result.get("external_epa_matched", False).fillna(False).astype(bool)
    result["has_nhtsa_data"] = result.get("external_nhtsa_matched", False).fillna(False).astype(bool)
    return result


def _normalize_high(series: pd.Series) -> pd.Series:
    series = pd.to_numeric(series, errors="coerce")
    if series.notna().sum() == 0:
        return pd.Series(0.5, index=series.index)
    low = series.quantile(0.05)
    high = series.quantile(0.95)
    if np.isclose(low, high):
        return pd.Series(0.5, index=series.index)
    return ((series - low) / (high - low)).clip(0, 1).fillna(0.5)


def _normalize_low(series: pd.Series) -> pd.Series:
    return 1 - _normalize_high(series)


def apply_preference_filters(
    df: pd.DataFrame,
    max_price: int,
    body_types: list[str],
    fuel_types: list[str],
    min_year: int,
    max_mileage: int,
    accident_policy: str,
    min_mpg: float,
    seat_groups: list[str],
) -> pd.DataFrame:
    filtered = df[
        df["price"].le(max_price)
        & df["model_year"].ge(min_year)
        & df["milage"].le(max_mileage)
        & df["body_type"].isin(body_types)
        & df["fuel_type"].fillna("Unknown").isin(fuel_types)
        & df["seat_group"].isin(seat_groups)
    ].copy()

    if accident_policy == "no_accident":
        filtered = filtered[~filtered["accident"].str.contains("accident|damage", case=False, na=False)].copy()

    if min_mpg > 0:
        filtered = filtered[
            filtered["epa_combined_mpg"].notna() & filtered["epa_combined_mpg"].ge(min_mpg)
        ].copy()

    return filtered


def _add_segment_value(scored: pd.DataFrame) -> pd.DataFrame:
    scored = scored.copy()
    class_key = scored.get("epa_vehicle_class", pd.Series(index=scored.index, dtype=object)).fillna(scored["body_type"])
    scored["_segment_class"] = class_key
    fine_median = scored.groupby(["_segment_class", "model_year"])["price"].transform("median")
    fine_count = scored.groupby(["_segment_class", "model_year"])["price"].transform("size")
    broad_median = scored.groupby(["body_type", "model_year"])["price"].transform("median")
    body_median = scored.groupby("body_type")["price"].transform("median")
    scored["segment_median_price"] = fine_median.where(fine_count >= 5, broad_median)
    scored["segment_median_price"] = scored["segment_median_price"].fillna(body_median).fillna(scored["price"].median())
    scored["price_vs_segment_median"] = scored["price"] - scored["segment_median_price"]
    scored["deal_ratio"] = 1 - (scored["price"] / scored["segment_median_price"]).replace([np.inf, -np.inf], np.nan)
    return scored.drop(columns=["_segment_class"])


def score_recommendations(
    df: pd.DataFrame,
    value_weight: float,
    mpg_weight: float,
    mileage_weight: float,
    year_weight: float,
    safety_weight: float,
) -> pd.DataFrame:
    scored = _add_segment_value(df)
    weights = {
        "value_score": value_weight,
        "mpg_score": mpg_weight,
        "mileage_score": mileage_weight,
        "year_score": year_weight,
        "safety_score": safety_weight,
    }
    total_weight = sum(weights.values()) or 1

    scored["value_score"] = _normalize_high(scored["deal_ratio"])
    # Keep absolute affordability as a secondary nudge, but do not let cheapness alone win.
    scored["value_score"] = (scored["value_score"] * 0.75 + _normalize_low(scored["price"]) * 0.25).clip(0, 1)
    scored["mpg_score"] = _normalize_high(scored["combined_mpg_for_score"])
    scored["mileage_score"] = _normalize_low(scored["milage"])
    scored["year_score"] = _normalize_high(scored["model_year"])

    recall_score = _normalize_low(scored["recall_count_for_score"])
    accident_score = np.where(scored["accident"].str.contains("accident|damage", case=False, na=False), 0.15, 1.0)
    advisory_score = np.where(
        scored.get("nhtsa_do_not_drive", False).astype(bool) | scored.get("nhtsa_park_outside", False).astype(bool),
        0.1,
        1.0,
    )
    scored["safety_score"] = (recall_score * 0.35 + accident_score * 0.45 + advisory_score * 0.2).clip(0, 1)

    scored["data_confidence"] = (
        0.5
        + scored["has_epa_data"].astype(float) * 0.25
        + scored["has_nhtsa_data"].astype(float) * 0.25
    )
    raw_score = (
        scored["value_score"] * weights["value_score"]
        + scored["mpg_score"] * weights["mpg_score"]
        + scored["mileage_score"] * weights["mileage_score"]
        + scored["year_score"] * weights["year_score"]
        + scored["safety_score"] * weights["safety_score"]
    ) / total_weight
    # Low-confidence rows can still rank, but should not beat well-supported rows too easily.
    scored["recommendation_score"] = (raw_score * (0.9 + scored["data_confidence"] * 0.1) * 100).round(1)

    scored["recommendation_reason"] = scored.apply(build_recommendation_reason, axis=1)
    return scored.sort_values(
        ["recommendation_score", "deal_ratio", "milage"],
        ascending=[False, False, True],
    )


def build_recommendation_reason(row: pd.Series) -> str:
    reasons = []
    if pd.notna(row.get("deal_ratio")):
        if row["deal_ratio"] >= 0.1:
            reasons.append("동급 대비 저렴")
        elif row["deal_ratio"] <= -0.1:
            reasons.append("동급 대비 비싼 편")
    if pd.notna(row.get("epa_combined_mpg")) and row["epa_combined_mpg"] >= 30:
        reasons.append("연비 우수")
    if row.get("milage", 0) <= 50_000:
        reasons.append("주행거리 낮음")
    accident_text = str(row.get("accident", "")).lower()
    if "accident" not in accident_text and "damage" not in accident_text:
        reasons.append("사고 이력 낮음")
    if row.get("nhtsa_recall_count", 0) <= 1:
        reasons.append("리콜 부담 낮음")
    if not reasons:
        reasons.append("조건 균형 양호")
    return ", ".join(reasons[:3])
