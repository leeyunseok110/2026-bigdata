from __future__ import annotations

import pandas as pd

from src.model import predict_price
from src.korea_market import find_korea_reference, load_korea_reference
from src.recommender import (
    add_recommendation_features,
    classify_body_type,
    estimate_seat_group,
    score_recommendations,
)


def _closest_external_profile(df: pd.DataFrame, brand: str, model: str, model_year: int) -> dict:
    brand_matches = df[df["brand"].str.casefold() == brand.casefold()].copy()
    if brand_matches.empty:
        return {}

    model_text = model.casefold()
    model_matches = brand_matches[
        brand_matches["model"].str.casefold().str.contains(model_text.split()[0], na=False, regex=False)
    ].copy()
    pool = model_matches if not model_matches.empty else brand_matches
    pool["year_gap"] = (pool["model_year"] - model_year).abs()
    pool = pool.sort_values(["year_gap", "milage"])

    profile = {}
    for column in [
        "epa_combined_mpg",
        "epa_vehicle_class",
        "epa_drive",
        "nhtsa_recall_count",
        "nhtsa_affected_units",
        "nhtsa_top_component",
        "nhtsa_do_not_drive",
        "nhtsa_park_outside",
        "external_epa_matched",
        "external_nhtsa_matched",
    ]:
        if column in pool.columns and pool[column].notna().any():
            profile[column] = pool[column].dropna().iloc[0]
    return profile


def _make_subject_row(df: pd.DataFrame, input_data: dict, predicted_price: float) -> pd.DataFrame:
    profile = _closest_external_profile(
        df,
        input_data["brand"],
        input_data["model"],
        int(input_data["model_year"]),
    )
    row = {
        "brand": input_data["brand"],
        "model": input_data["model"],
        "model_year": int(input_data["model_year"]),
        "milage": float(input_data["milage"]),
        "fuel_type": input_data["fuel_type"],
        "transmission": input_data["transmission"],
        "accident": input_data["accident_raw"],
        "accident_flag": input_data["accident_flag"],
        "clean_title": input_data["clean_title"],
        "price": float(input_data["asking_price"]),
        "predicted_price": predicted_price,
        **profile,
    }
    row["epa_vehicle_class"] = row.get("epa_vehicle_class", input_data.get("body_type", "Other"))
    row["body_type"] = classify_body_type(row.get("epa_vehicle_class"), row["model"])
    if input_data.get("body_type") and input_data["body_type"] != "자동 추정":
        row["body_type"] = input_data["body_type"]
    row["seat_group"] = estimate_seat_group(row["body_type"], row.get("epa_vehicle_class"))
    if input_data.get("seat_group") and input_data["seat_group"] != "자동 추정":
        row["seat_group"] = input_data["seat_group"]
    row["external_epa_matched"] = bool(row.get("external_epa_matched", pd.notna(row.get("epa_combined_mpg"))))
    row["external_nhtsa_matched"] = bool(row.get("external_nhtsa_matched", pd.notna(row.get("nhtsa_recall_count"))))
    row["nhtsa_recall_count"] = int(row.get("nhtsa_recall_count", 0) or 0)
    row["nhtsa_affected_units"] = int(row.get("nhtsa_affected_units", 0) or 0)
    row["nhtsa_do_not_drive"] = bool(row.get("nhtsa_do_not_drive", False))
    row["nhtsa_park_outside"] = bool(row.get("nhtsa_park_outside", False))
    return pd.DataFrame([row])


def _comparison_pool(df: pd.DataFrame, subject: pd.Series) -> pd.DataFrame:
    brand_pool = df[df["brand"].str.casefold() == str(subject["brand"]).casefold()].copy()
    body_pool = df[
        (df["brand"].str.casefold() == str(subject["brand"]).casefold())
        & (df["body_type"] == subject["body_type"])
        & df["model_year"].between(subject["model_year"] - 2, subject["model_year"] + 2)
    ].copy()
    brand_model_pool = df[
        (df["brand"].str.casefold() == str(subject["brand"]).casefold())
        & df["model"].str.casefold().str.contains(str(subject["model"]).split()[0].casefold(), na=False, regex=False)
        & df["model_year"].between(subject["model_year"] - 3, subject["model_year"] + 3)
    ].copy()
    if len(brand_model_pool) >= 5:
        return brand_model_pool
    if len(body_pool) >= 20:
        return body_pool
    if len(brand_pool) >= 10:
        return brand_pool
    return df[df["model_year"].between(subject["model_year"] - 3, subject["model_year"] + 3)].copy()


def _verdict(row: pd.Series, model_gap_ratio: float) -> tuple[str, str]:
    safety_bad = (
        "accident" in str(row.get("accident", "")).lower()
        or "damage" in str(row.get("accident", "")).lower()
        or bool(row.get("nhtsa_do_not_drive", False))
        or bool(row.get("nhtsa_park_outside", False))
    )
    score = float(row.get("recommendation_score", 0))
    deal_ratio = float(row.get("deal_ratio", 0))

    if safety_bad and model_gap_ratio > -0.08:
        return "주의 필요", "사고/리콜 위험 신호가 있어 가격이 충분히 싸지 않으면 신중해야 합니다."
    if score >= 78 and model_gap_ratio <= -0.05 and deal_ratio >= 0.05:
        return "구입 후보로 좋음", "예측가와 동급 시세보다 낮은 편이고 조건 균형도 좋습니다."
    if score >= 65 and model_gap_ratio <= 0.05:
        return "적정 가격권", "크게 비싸지는 않지만 추가 협상이나 정비 이력 확인이 좋습니다."
    if model_gap_ratio > 0.12 or deal_ratio < -0.08:
        return "비싼 편", "예측가나 동급 시세 대비 가격 부담이 큽니다."
    return "조건부 검토", "가격만으로는 나쁘지 않지만 일부 조건이 애매해 비교 매물을 더 확인하는 편이 좋습니다."


def evaluate_vehicle(df: pd.DataFrame, price_model, input_data: dict) -> dict:
    feature_input = {
        "brand": input_data["brand"],
        "model": input_data["model"],
        "model_year": input_data["model_year"],
        "milage": input_data["milage"],
        "fuel_type": input_data["fuel_type"],
        "transmission": input_data["transmission"],
        "accident_flag": input_data["accident_flag"],
        "clean_title": input_data["clean_title"],
    }
    predicted_price = predict_price(price_model, feature_input)
    enriched_df = add_recommendation_features(df)
    subject = add_recommendation_features(_make_subject_row(enriched_df, input_data, predicted_price))
    pool = _comparison_pool(enriched_df, subject.iloc[0])
    scoring_pool = pd.concat([pool, subject], ignore_index=True, sort=False)
    scored = score_recommendations(
        scoring_pool,
        value_weight=4.0,
        mpg_weight=1.5,
        mileage_weight=2.0,
        year_weight=1.5,
        safety_weight=2.5,
    )
    subject_scored = scored[scored["predicted_price"].notna()].iloc[0]
    similar = pool.sort_values("price").head(12)
    model_gap = subject_scored["price"] - predicted_price
    model_gap_ratio = model_gap / predicted_price if predicted_price else 0
    verdict, verdict_detail = _verdict(subject_scored, model_gap_ratio)
    korea_reference = find_korea_reference(
        load_korea_reference(),
        input_data["brand"],
        input_data["model"],
        int(input_data["model_year"]),
    )
    korea_gap = None
    korea_gap_ratio = None
    if korea_reference is not None:
        korea_gap = subject_scored["price"] - float(korea_reference["reference_price_krw"])
        korea_gap_ratio = korea_gap / float(korea_reference["reference_price_krw"])
        if korea_gap_ratio > 0.15:
            verdict = "한국 기준 비싼 편"
            verdict_detail = "입력가가 등록된 한국 기준가액보다 높아 추가 협상이나 다른 매물 비교가 필요합니다."
        elif korea_gap_ratio < -0.10 and verdict not in {"주의 필요"}:
            verdict = "한국 기준 구입 후보"
            verdict_detail = "입력가가 등록된 한국 기준가액보다 낮고, 다른 조건도 함께 검토할 만합니다."

    return {
        "subject": subject_scored,
        "predicted_price": predicted_price,
        "model_gap": model_gap,
        "model_gap_ratio": model_gap_ratio,
        "verdict": verdict,
        "verdict_detail": verdict_detail,
        "korea_reference": korea_reference,
        "korea_gap": korea_gap,
        "korea_gap_ratio": korea_gap_ratio,
        "similar": similar,
    }
