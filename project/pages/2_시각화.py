import streamlit as st

from src.charts import (
    accident_price_box,
    brand_average_price,
    mileage_price_scatter,
    price_distribution,
    price_range_counts,
    regular_price_distribution,
    year_average_price,
)
from src.data_loader import filter_cars, load_used_cars
from src.insights import build_insights, format_currency, format_exchange_rate_caption, format_number


@st.cache_data
def get_data():
    return load_used_cars()


df = get_data()

st.title("시각화")
st.caption("필터를 적용해 브랜드, 연식, 주행거리, 사고 이력별 가격 패턴을 분석합니다.")
st.caption(format_exchange_rate_caption())

with st.sidebar:
    st.header("필터")
    brands = st.multiselect(
        "브랜드",
        options=sorted(df["brand"].unique()),
        default=sorted(df["brand"].value_counts().head(10).index),
    )
    fuel_types = st.multiselect(
        "연료 유형",
        options=sorted(df["fuel_type"].unique()),
        default=sorted(df["fuel_type"].unique()),
    )
    accident_flags = st.multiselect(
        "사고 이력",
        options=sorted(df["accident_flag"].unique()),
        default=sorted(df["accident_flag"].unique()),
    )
    year_range = st.slider(
        "연식",
        min_value=int(df["model_year"].min()),
        max_value=int(df["model_year"].max()),
        value=(int(df["model_year"].min()), int(df["model_year"].max())),
    )
    price_range = st.slider(
        "가격(원)",
        min_value=int(df["price"].min()),
        max_value=int(df["price"].max()),
        value=(int(df["price"].quantile(0.01)), int(df["price"].quantile(0.99))),
        step=1_000_000,
    )
    milage_range = st.slider(
        "주행거리(mi)",
        min_value=int(df["milage"].min()),
        max_value=int(df["milage"].max()),
        value=(int(df["milage"].min()), int(df["milage"].quantile(0.99))),
        step=1000,
    )

filtered_df = filter_cars(
    df,
    brands=brands,
    fuel_types=fuel_types,
    accident_flags=accident_flags,
    year_range=year_range,
    price_range=price_range,
    milage_range=milage_range,
)

if filtered_df.empty:
    st.warning("선택한 조건에 맞는 데이터가 없습니다. 필터를 조정하세요.")
    st.stop()

metric_cols = st.columns(4)
metric_cols[0].metric("매물 수", f"{len(filtered_df):,}")
metric_cols[1].metric("평균 가격", format_currency(filtered_df["price"].mean()))
metric_cols[2].metric("평균 주행거리", format_number(filtered_df["milage"].mean()))
metric_cols[3].metric("평균 연식", format_number(filtered_df["model_year"].mean()))

overview_left, overview_right = st.columns(2)
overview_left.plotly_chart(price_distribution(filtered_df, nbins=80, title="필터 결과 가격 분포"), use_container_width=True)
overview_right.plotly_chart(accident_price_box(filtered_df), use_container_width=True)

price_left, price_right = st.columns(2)
price_left.plotly_chart(regular_price_distribution(filtered_df), use_container_width=True)
price_right.plotly_chart(price_range_counts(filtered_df), use_container_width=True)

st.plotly_chart(brand_average_price(filtered_df), use_container_width=True)

trend_left, trend_right = st.columns(2)
trend_left.plotly_chart(year_average_price(filtered_df), use_container_width=True)
trend_right.plotly_chart(mileage_price_scatter(filtered_df), use_container_width=True)

st.subheader("분석 인사이트")
for insight in build_insights(df, filtered_df):
    st.write(f"- {insight}")

st.subheader("필터링된 데이터")
display_columns = [
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
st.dataframe(
    filtered_df[display_columns].sort_values("price", ascending=False),
    use_container_width=True,
    hide_index=True,
)
