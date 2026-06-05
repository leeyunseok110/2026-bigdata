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
lower_price = max(predicted_price - mae, 0)
upper_price = predicted_price + mae

st.subheader("예측 결과")
result_cols = st.columns(4)
result_cols[0].metric("예상 중고가", format_currency(predicted_price))
result_cols[1].metric("예상 범위 하한", format_currency(lower_price))
result_cols[2].metric("예상 범위 상한", format_currency(upper_price))
result_cols[3].metric("모델 설명력 R²", f"{model_metrics['r2']:.3f}")

st.caption(f"예상 범위는 현재 모델의 평균 절대 오차(MAE) {format_currency(mae)}를 기준으로 단순 산정했습니다.")

similar = df[
    (df["brand"] == brand)
    & (df["model_year"].between(int(model_year) - 2, int(model_year) + 2))
    & (df["fuel_type"] == fuel_type)
].copy()

if model_mode == "목록에서 선택":
    same_model = similar[similar["model"] == model].copy()
    if len(same_model) >= 3:
        similar = same_model

if not similar.empty:
    st.subheader("비슷한 차량 참고")
    compare_cols = st.columns(3)
    compare_cols[0].metric("비교 매물 수", f"{len(similar):,}")
    compare_cols[1].metric("평균 가격", format_currency(similar["price"].mean()))
    compare_cols[2].metric("중앙값", format_currency(similar["price"].median()))
    st.dataframe(
        similar[
            [
                "brand",
                "model",
                "model_year",
                "milage",
                "fuel_type",
                "transmission",
                "accident_flag",
                "price",
            ]
        ]
        .sort_values("price")
        .head(30),
        use_container_width=True,
        hide_index=True,
        column_config={
            "milage": st.column_config.NumberColumn("주행거리(mi)", format="%d"),
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
