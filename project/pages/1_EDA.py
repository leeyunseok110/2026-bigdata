import streamlit as st

from src.charts import (
    expensive_car_prices,
    log_price_distribution,
    price_distribution,
    price_range_counts,
    regular_price_distribution,
)
from src.data_loader import load_used_cars
from src.insights import format_currency, format_exchange_rate_caption, format_number


@st.cache_data
def get_data():
    return load_used_cars()


df = get_data()

st.title("EDA")
st.caption("중고차 데이터의 기본 구조, 결측치, 주요 분포를 확인합니다.")
st.caption(format_exchange_rate_caption())

metric_cols = st.columns(4)
metric_cols[0].metric("전체 매물 수", f"{len(df):,}")
metric_cols[1].metric("평균 가격", format_currency(df["price"].mean()))
metric_cols[2].metric("평균 주행거리", format_number(df["milage"].mean()))
metric_cols[3].metric("평균 연식", format_number(df["model_year"].mean()))

st.subheader("데이터 미리보기")
st.dataframe(df.head(20), use_container_width=True, hide_index=True)

left, right = st.columns(2)

with left:
    st.subheader("컬럼별 결측치")
    missing = df.isna().sum().reset_index()
    missing.columns = ["컬럼", "결측치 수"]
    st.dataframe(missing, use_container_width=True, hide_index=True)

with right:
    st.subheader("주요 수치형 통계")
    st.dataframe(
        df[["price", "milage", "model_year", "car_age", "price_per_mile"]].describe(),
        use_container_width=True,
    )

st.subheader("가격 분포 세부 분석")
price_left, price_right = st.columns(2)
price_left.plotly_chart(price_distribution(df, nbins=100, title="전체 가격 분포"), use_container_width=True)
price_right.plotly_chart(regular_price_distribution(df), use_container_width=True)

range_left, range_right = st.columns(2)
range_left.plotly_chart(price_range_counts(df), use_container_width=True)
range_right.plotly_chart(log_price_distribution(df), use_container_width=True)

price_limit = df["price"].quantile(0.99)
expensive_cars = df[df["price"] > price_limit].sort_values("price", ascending=False)

st.subheader("비싼차 모음집")
st.caption(f"{format_currency(price_limit)} 초과 초고가 매물 {len(expensive_cars):,}건을 따로 확인합니다.")
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
