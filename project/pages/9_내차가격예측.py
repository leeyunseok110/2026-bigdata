import numpy as np
import pandas as pd
import streamlit as st

from src.data_loader import load_used_cars
from src.insights import format_currency, format_exchange_rate_caption, format_number
from src.model import predict_price, train_price_model
from src.recommender import BODY_TYPE_ORDER


@st.cache_data
def get_data():
    return load_used_cars()


@st.cache_resource
def get_price_model(_data):
    return train_price_model(_data)


df = get_data()
price_model, model_metrics = get_price_model(df)


def find_comparable_cars(
    data: pd.DataFrame,
    brand: str,
    model: str,
    model_year: int,
    mileage: float,
    fuel_type: str,
) -> tuple[pd.DataFrame, str]:
    brand_pool = data[data["brand"] == brand].copy()
    if brand_pool.empty:
        return data[data["model_year"].between(model_year - 3, model_year + 3)].copy(), "전체 유사 연식"

    exact_model = brand_pool[
        (brand_pool["model"] == model)
        & brand_pool["model_year"].between(model_year - 3, model_year + 3)
    ].copy()
    if len(exact_model) >= 3:
        return exact_model, "동일 모델"

    model_token = str(model).split()[0].casefold() if str(model).strip() else ""
    if model_token:
        token_model = brand_pool[
            brand_pool["model"].str.casefold().str.contains(model_token, na=False, regex=False)
            & brand_pool["model_year"].between(model_year - 3, model_year + 3)
        ].copy()
        if len(token_model) >= 5:
            return token_model, "유사 모델명"

    brand_fuel = brand_pool[
        brand_pool["fuel_type"].eq(fuel_type)
        & brand_pool["model_year"].between(model_year - 2, model_year + 2)
    ].copy()
    if len(brand_fuel) >= 8:
        return brand_fuel, "동일 브랜드·연료·연식"

    brand_year = brand_pool[brand_pool["model_year"].between(model_year - 3, model_year + 3)].copy()
    if len(brand_year) >= 8:
        return brand_year, "동일 브랜드·유사 연식"

    return brand_pool, "동일 브랜드"


def comparable_market_estimate(comparable: pd.DataFrame, model_year: int, mileage: float) -> dict:
    if comparable.empty:
        return {
            "estimate": np.nan,
            "low": np.nan,
            "high": np.nan,
            "confidence": "낮음",
            "count": 0,
        }

    comp = comparable.copy()
    comp["year_gap"] = (comp["model_year"] - model_year).abs()
    comp["mileage_gap"] = (comp["milage"] - mileage).abs()
    mileage_scale = max(float(comp["milage"].median()), 50_000.0)
    comp["similarity_weight"] = (
        np.exp(-comp["year_gap"] / 2.0)
        * np.exp(-comp["mileage_gap"] / mileage_scale)
    ).clip(lower=0.05)

    price_q1 = comp["price"].quantile(0.25)
    price_q3 = comp["price"].quantile(0.75)
    weighted_estimate = np.average(comp["price"], weights=comp["similarity_weight"])
    median_estimate = comp["price"].median()
    estimate = weighted_estimate * 0.6 + median_estimate * 0.4

    if len(comp) >= 12:
        confidence = "높음"
    elif len(comp) >= 5:
        confidence = "보통"
    else:
        confidence = "낮음"

    return {
        "estimate": float(estimate),
        "low": float(price_q1),
        "high": float(price_q3),
        "confidence": confidence,
        "count": len(comp),
    }


def blend_prediction(model_price: float, market_price: float, comparable_count: int) -> tuple[float, str]:
    if not np.isfinite(market_price):
        return model_price, "모델 예측 중심"
    if comparable_count >= 12:
        return model_price * 0.3 + market_price * 0.7, "유사 매물 70% + 모델 30%"
    if comparable_count >= 5:
        return model_price * 0.45 + market_price * 0.55, "유사 매물 55% + 모델 45%"
    if comparable_count >= 3:
        return model_price * 0.65 + market_price * 0.35, "모델 65% + 유사 매물 35%"
    return model_price, "모델 예측 중심"

st.title("내 차 중고가 예측")
st.caption("차량 종류, 연식, 주행거리, 연료, 변속기, 사고 이력을 입력하면 예상 중고차 가격을 예측합니다.")
st.caption(format_exchange_rate_caption())

st.subheader("브랜드/모델 선택")
brand_cols = st.columns(2)
with brand_cols[0]:
    brand = st.selectbox("브랜드", sorted(df["brand"].dropna().unique()))
brand_df = df[df["brand"] == brand].copy()
model_options = sorted(brand_df["model"].dropna().unique())
with brand_cols[1]:
    model_mode = st.radio("모델 입력 방식", ["목록에서 선택", "직접 입력"], horizontal=True)

if model_mode == "목록에서 선택":
    model = st.selectbox(f"{brand} 모델", model_options)
else:
    model = st.text_input("모델명", value=model_options[0] if model_options else "")

with st.form("my_car_prediction_form"):
    left, right = st.columns(2)

    with left:
        model_year = st.number_input(
            "연식",
            min_value=int(df["model_year"].min()),
            max_value=int(df["model_year"].max()) + 1,
            value=int(df["model_year"].median()),
            step=1,
        )
        mileage = st.number_input(
            "주행거리(mi)",
            min_value=0,
            max_value=int(df["milage"].max()),
            value=int(df["milage"].median()),
            step=1000,
        )

    with right:
        body_type = st.selectbox("차량 종류", ["자동 추정"] + BODY_TYPE_ORDER)
        fuel_type = st.selectbox("연료 종류", sorted(brand_df["fuel_type"].dropna().unique()))
        transmission = st.selectbox("변속기", ["자동", "수동", "기타"])
        accident_label = st.selectbox("사고/손상 이력", ["없음", "있음"])
        clean_title = st.selectbox("클린 타이틀", sorted(df["clean_title"].dropna().unique()))

    submitted = st.form_submit_button("예상 가격 계산", type="primary")

if not submitted:
    st.info("차량 정보를 입력하고 `예상 가격 계산`을 누르세요.")
    st.stop()

accident_options = sorted(df["accident_flag"].dropna().unique())
no_accident_flag = next((value for value in accident_options if "없" in value), accident_options[0])
accident_flag = no_accident_flag if accident_label == "없음" else next(
    (value for value in accident_options if value != no_accident_flag),
    accident_options[-1],
)

prediction_input = {
    "brand": brand,
    "model": model,
    "model_year": int(model_year),
    "milage": float(mileage),
    "fuel_type": fuel_type,
    "transmission": transmission,
    "accident_flag": accident_flag,
    "clean_title": clean_title,
}

predicted_price = predict_price(price_model, prediction_input)
mae = model_metrics["mae"]
comparable, comparable_basis = find_comparable_cars(df, brand, model, int(model_year), float(mileage), fuel_type)
market = comparable_market_estimate(comparable, int(model_year), float(mileage))
final_price, blend_label = blend_prediction(predicted_price, market["estimate"], market["count"])

if np.isfinite(market["low"]) and np.isfinite(market["high"]):
    lower_price = max(min(final_price - mae * 0.45, market["low"]), 0)
    upper_price = max(final_price + mae * 0.45, market["high"])
else:
    lower_price = max(final_price - mae, 0)
    upper_price = final_price + mae

st.subheader("예측 결과")
result_cols = st.columns(4)
result_cols[0].metric("최종 예상 중고가", format_currency(final_price))
result_cols[1].metric("예상 범위 하한", format_currency(lower_price))
result_cols[2].metric("예상 범위 상한", format_currency(upper_price))
result_cols[3].metric("비교 신뢰도", market["confidence"])

detail_cols = st.columns(3)
detail_cols[0].metric("모델 단독 예측", format_currency(predicted_price))
detail_cols[1].metric(
    f"유사 매물 시세 ({comparable_basis})",
    "-" if not np.isfinite(market["estimate"]) else format_currency(market["estimate"]),
)
detail_cols[2].metric("비교 매물 수", f"{market['count']:,}")

st.caption(
    f"최종 예상가는 `{blend_label}` 방식으로 계산했습니다. "
    "중고차는 옵션, 지역, 정비 이력에 따라 차이가 커서 유사 매물이 충분할수록 실제 시세에 더 가깝게 보정합니다."
)

if not comparable.empty:
    st.subheader("비슷한 차량 참고")
    compare_cols = st.columns(3)
    compare_cols[0].metric("비교 기준", comparable_basis)
    compare_cols[1].metric("평균 가격", format_currency(comparable["price"].mean()))
    compare_cols[2].metric("중앙값", format_currency(comparable["price"].median()))
    comparable_display = comparable.copy()
    comparable_display["year_gap"] = (comparable_display["model_year"] - int(model_year)).abs()
    comparable_display["mileage_gap"] = (comparable_display["milage"] - float(mileage)).abs()
    st.dataframe(
        comparable_display[
            [
                "brand",
                "model",
                "model_year",
                "milage",
                "year_gap",
                "mileage_gap",
                "fuel_type",
                "transmission",
                "accident_flag",
                "price",
            ]
        ]
        .sort_values(["year_gap", "mileage_gap", "price"])
        .head(30),
        use_container_width=True,
        hide_index=True,
        column_config={
            "milage": st.column_config.NumberColumn("주행거리(mi)", format="%d"),
            "year_gap": st.column_config.NumberColumn("연식 차이", format="%d"),
            "mileage_gap": st.column_config.NumberColumn("주행거리 차이(mi)", format="%d"),
            "price": st.column_config.NumberColumn("가격(원)", format="₩%d"),
        },
    )
else:
    st.info("비슷한 비교 매물이 부족합니다. 예측 가격을 참고하되 실제 플랫폼 시세와 함께 확인하세요.")

st.subheader("입력 요약")
st.write(
    f"{brand} {model} · {int(model_year)}년식 · {format_number(mileage)} mi · "
    f"{fuel_type} · {transmission} · 사고 이력 {accident_label}"
)
if body_type != "자동 추정":
    st.write(f"차량 종류: {body_type}")

st.caption("예측 결과는 데이터 기반 참고용입니다. 실제 판매가는 지역, 옵션, 소모품 상태, 보험 이력, 정비 이력에 따라 달라질 수 있습니다.")
