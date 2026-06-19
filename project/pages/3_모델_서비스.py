import streamlit as st

from src.charts import expensive_car_prices
from src.data_loader import load_used_cars
from src.insights import format_currency, format_exchange_rate_caption
from src.model import predict_price, train_price_model


@st.cache_data
def get_data():
    return load_used_cars()


@st.cache_resource
def get_price_model(_data):
    return train_price_model(_data)


df = get_data()
price_model, model_metrics = get_price_model(df)

st.title("모델/서비스")
st.caption("사용자가 입력한 차량 조건을 바탕으로 중고차 예상 가격을 예측합니다.")
st.caption(format_exchange_rate_caption())

metric_left, metric_center, metric_right = st.columns(3)
metric_left.metric("평균 절대 오차", format_currency(model_metrics["mae"]))
metric_center.metric("설명력 R²", f"{model_metrics['r2']:.3f}")
metric_right.metric("학습/검증 데이터", f"{model_metrics['train_rows']:,} / {model_metrics['test_rows']:,}")

with st.expander("모델 선택과 지표 해석", expanded=True):
    st.write(
        "이 페이지는 사용자가 입력한 차량 조건을 머신러닝 모델에 넣고 "
        "예상 가격을 반환하는 MVP 서비스입니다."
    )
    explanation_cols = st.columns(2)
    with explanation_cols[0]:
        st.markdown(
            """
            **왜 RandomForestRegressor인가**

            - 브랜드, 모델, 연료, 변속기처럼 범주형 변수가 많음
            - 연식과 주행거리처럼 비선형 관계가 있는 수치형 변수가 섞여 있음
            - 수업에서 다룬 scikit-learn 회귀 모델로 구현과 설명이 쉬움
            - 하나의 선형식보다 다양한 조건 조합을 더 유연하게 반영 가능
            """
        )
    with explanation_cols[1]:
        st.markdown(
            f"""
            **평가지표 읽는 법**

            - 평균 절대 오차(MAE): 예측 가격이 실제 가격과 평균적으로 {format_currency(model_metrics["mae"])} 정도 차이남
            - R²: 입력 변수들이 가격 변동의 약 {model_metrics["r2"]:.1%}를 설명
            - 상위 1% 초고가 매물 {model_metrics["excluded_rows"]:,}건은 일반 매물 예측을 안정화하기 위해 학습에서 제외
            - 결과는 감정가가 아니라 조건별 참고 가격으로 해석해야 함
            """
        )
    st.markdown(
        """
        **전처리 흐름:** 숫자형 변수(`model_year`, `milage`)는 표준화하고,
        범주형 변수(`brand`, `model`, `fuel_type`, `transmission`, `accident_flag`, `clean_title`)는
        원-핫 인코딩으로 바꾼 뒤 모델에 입력합니다.
        """
    )

st.info(
    "안정적인 일반 매물 예측을 위해 "
    f"{format_currency(model_metrics['price_limit'])} 초과 초고가 매물 "
    f"{model_metrics['excluded_rows']:,}건은 모델 학습에서 제외했습니다."
)

expensive_cars = df[df["price"] > model_metrics["price_limit"]].sort_values("price", ascending=False)

with st.expander("비싼차 모음집: 모델 학습에서 제외한 초고가 매물", expanded=True):
    st.write(
        f"{format_currency(model_metrics['price_limit'])} 초과 매물 "
        f"{len(expensive_cars):,}건을 따로 모았습니다."
    )
    st.plotly_chart(expensive_car_prices(expensive_cars), use_container_width=True)
    st.dataframe(
        expensive_cars[
            [
                "brand",
                "model",
                "model_year",
                "milage",
                "fuel_type",
                "transmission",
                "accident_flag",
                "clean_title",
                "price",
            ]
        ],
        use_container_width=True,
        hide_index=True,
        column_config={
            "brand": "브랜드",
            "model": "모델명",
            "model_year": "연식",
            "milage": st.column_config.NumberColumn("주행거리(mi)", format="%d"),
            "fuel_type": "연료",
            "transmission": "변속기",
            "accident_flag": "사고 이력",
            "clean_title": "클린 타이틀",
            "price": st.column_config.NumberColumn("가격(원)", format="₩%d"),
        },
    )

st.subheader("가격 예측 입력")

form_left, form_right = st.columns(2)
with form_left:
    input_brand = st.selectbox("브랜드", sorted(df["brand"].unique()))
    model_options = sorted(df.loc[df["brand"] == input_brand, "model"].unique())
    input_model = st.selectbox("모델", model_options)
    input_year = st.number_input(
        "연식",
        min_value=int(df["model_year"].min()),
        max_value=int(df["model_year"].max()),
        value=int(df["model_year"].median()),
        step=1,
    )
    input_milage = st.number_input(
        "주행거리(mi)",
        min_value=0,
        max_value=int(df["milage"].max()),
        value=int(df["milage"].median()),
        step=1000,
    )

with form_right:
    input_fuel = st.selectbox("연료 유형", sorted(df["fuel_type"].unique()))
    input_transmission = st.selectbox("변속기", sorted(df["transmission"].unique()))
    input_accident = st.selectbox("사고 이력", sorted(df["accident_flag"].unique()))
    input_clean_title = st.selectbox("클린 타이틀", sorted(df["clean_title"].unique()))

prediction_input = {
    "brand": input_brand,
    "model": input_model,
    "model_year": input_year,
    "milage": input_milage,
    "fuel_type": input_fuel,
    "transmission": input_transmission,
    "accident_flag": input_accident,
    "clean_title": input_clean_title,
}
predicted_price = predict_price(price_model, prediction_input)

st.metric("예상 중고차 가격", format_currency(predicted_price))

similar_cars = df[
    (df["brand"] == input_brand)
    & (df["model"] == input_model)
    & (df["fuel_type"] == input_fuel)
    & (df["model_year"].between(input_year - 2, input_year + 2))
].copy()

if not similar_cars.empty:
    st.subheader("유사 조건 차량 가격 참고")
    compare_cols = st.columns(3)
    compare_cols[0].metric("유사 차량 수", f"{len(similar_cars):,}")
    compare_cols[1].metric("유사 차량 평균 가격", format_currency(similar_cars["price"].mean()))
    compare_cols[2].metric("유사 차량 중앙값", format_currency(similar_cars["price"].median()))
    st.dataframe(
        similar_cars[
            ["brand", "model", "model_year", "milage", "fuel_type", "transmission", "accident_flag", "price"]
        ].sort_values("price"),
        use_container_width=True,
        hide_index=True,
        column_config={
            "price": st.column_config.NumberColumn("가격(원)", format="₩%d"),
            "milage": st.column_config.NumberColumn("주행거리(mi)", format="%d"),
        },
    )
else:
    st.info("같은 브랜드, 모델, 연료 유형, 유사 연식 조건의 비교 차량이 부족합니다.")
