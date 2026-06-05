import pandas as pd
import plotly.express as px
import streamlit as st

from src.data_loader import load_used_cars
from src.insights import format_currency, format_exchange_rate_caption, format_number
from src.recommender import (
    BODY_TYPE_ORDER,
    add_recommendation_features,
    apply_preference_filters,
    score_recommendations,
)


@st.cache_data
def get_data():
    return add_recommendation_features(load_used_cars())


df = get_data()

st.title("가성비 차량 추천")
st.caption("비슷한 차종과 연식 안에서 가격이 합리적인지, 연비·주행거리·사고/리콜 위험까지 함께 평가합니다.")
st.caption(format_exchange_rate_caption())

with st.sidebar:
    st.header("추천 조건")
    max_price = st.slider(
        "최대 예산 (원)",
        min_value=int(df["price"].quantile(0.01)),
        max_value=int(df["price"].quantile(0.99)),
        value=int(df["price"].quantile(0.65)),
        step=1_000_000,
    )
    available_body_types = [body for body in BODY_TYPE_ORDER if body in set(df["body_type"])]
    body_types = st.multiselect(
        "차종",
        options=available_body_types,
        default=[body for body in ["Sedan", "SUV"] if body in available_body_types],
    )
    fuel_types = st.multiselect(
        "연료 종류",
        options=sorted(df["fuel_type"].fillna("Unknown").unique()),
        default=[
            fuel
            for fuel in ["Gasoline", "Hybrid"]
            if fuel in set(df["fuel_type"].fillna("Unknown").unique())
        ],
    )
    seat_groups = st.multiselect(
        "탑승 인원",
        options=["2 seats", "4-5 seats", "6+ seats"],
        default=["4-5 seats", "6+ seats"],
    )
    min_year = st.slider(
        "최소 연식",
        min_value=int(df["model_year"].min()),
        max_value=int(df["model_year"].max()),
        value=max(int(df["model_year"].max()) - 8, int(df["model_year"].min())),
    )
    max_mileage = st.slider(
        "최대 주행거리 (mi)",
        min_value=0,
        max_value=int(df["milage"].quantile(0.99)),
        value=int(df["milage"].quantile(0.70)),
        step=5000,
    )
    accident_label = st.selectbox(
        "사고 이력",
        options=["무사고만", "상관없음"],
        index=0,
    )
    accident_policy = "no_accident" if accident_label == "무사고만" else "any"
    min_mpg = st.slider(
        "최소 EPA 복합 연비 (MPG)",
        min_value=0.0,
        max_value=60.0,
        value=0.0,
        step=1.0,
        help="값을 올리면 EPA 연비가 확인된 차량 중 조건을 만족하는 차량만 남깁니다.",
    )

    st.header("추천 성향")
    value_weight = st.slider("동급 대비 가성비", 0.0, 5.0, 4.0, 0.5)
    mpg_weight = st.slider("연비", 0.0, 5.0, 1.5, 0.5)
    mileage_weight = st.slider("낮은 주행거리", 0.0, 5.0, 2.0, 0.5)
    year_weight = st.slider("최근 연식", 0.0, 5.0, 1.5, 0.5)
    safety_weight = st.slider("사고/리콜 안정성", 0.0, 5.0, 2.5, 0.5)

if not body_types or not fuel_types or not seat_groups:
    st.warning("차종, 연료 종류, 탑승 인원 조건을 하나 이상 선택하세요.")
    st.stop()

filtered = apply_preference_filters(
    df,
    max_price=max_price,
    body_types=body_types,
    fuel_types=fuel_types,
    min_year=min_year,
    max_mileage=max_mileage,
    accident_policy=accident_policy,
    min_mpg=min_mpg,
    seat_groups=seat_groups,
)

if filtered.empty:
    st.warning("조건에 맞는 차량이 없습니다. 예산, 연식, 주행거리, 연비 조건을 조금 넓혀보세요.")
    st.stop()

recommendations = score_recommendations(
    filtered,
    value_weight=value_weight,
    mpg_weight=mpg_weight,
    mileage_weight=mileage_weight,
    year_weight=year_weight,
    safety_weight=safety_weight,
)

top = recommendations.head(20).copy()
best = top.iloc[0]

metric_cols = st.columns(4)
metric_cols[0].metric("후보 차량", f"{len(recommendations):,}")
metric_cols[1].metric("최고 추천 점수", f"{best['recommendation_score']:.1f}")
metric_cols[2].metric("1위 가격", format_currency(best["price"]))
metric_cols[3].metric(
    "동급 중앙값 대비",
    format_currency(best["price_vs_segment_median"]),
)

st.subheader("가장 추천하는 차량")
summary_cols = st.columns(3)
summary_cols[0].write(f"**{best['brand']} {best['model']}**")
summary_cols[0].write(f"{int(best['model_year'])}년식 · {best['body_type']} · {best['seat_group']}")
summary_cols[0].write(f"추천 이유: {best['recommendation_reason']}")
summary_cols[1].metric("가격", format_currency(best["price"]))
summary_cols[1].metric("주행거리", f"{format_number(best['milage'])} mi")
summary_cols[2].metric("추천 점수", f"{best['recommendation_score']:.1f}/100")
summary_cols[2].metric(
    "복합 연비",
    "-" if pd.isna(best.get("epa_combined_mpg")) else f"{best['epa_combined_mpg']:.1f} MPG",
)

st.subheader("추천 TOP 20")
display_columns = [
    "recommendation_score",
    "recommendation_reason",
    "brand",
    "model",
    "model_year",
    "body_type",
    "seat_group",
    "fuel_type",
    "price",
    "segment_median_price",
    "price_vs_segment_median",
    "deal_ratio",
    "milage",
    "epa_combined_mpg",
    "nhtsa_recall_count",
    "accident_flag",
    "data_confidence",
]
st.dataframe(
    top[display_columns],
    use_container_width=True,
    hide_index=True,
    column_config={
        "recommendation_score": st.column_config.ProgressColumn(
            "추천 점수",
            min_value=0,
            max_value=100,
            format="%.1f",
        ),
        "recommendation_reason": "추천 이유",
        "price": st.column_config.NumberColumn("가격 (원)", format="₩%d"),
        "segment_median_price": st.column_config.NumberColumn("동급 중앙값", format="₩%d"),
        "price_vs_segment_median": st.column_config.NumberColumn("중앙값 대비", format="₩%d"),
        "deal_ratio": st.column_config.NumberColumn("할인율", format="%.1%"),
        "milage": st.column_config.NumberColumn("주행거리 (mi)", format="%d"),
        "epa_combined_mpg": st.column_config.NumberColumn("복합 연비 (MPG)", format="%.1f"),
        "nhtsa_recall_count": st.column_config.NumberColumn("리콜 수", format="%d"),
        "data_confidence": st.column_config.ProgressColumn("데이터 신뢰도", min_value=0, max_value=1, format="%.2f"),
    },
)

left, right = st.columns(2)
with left:
    fig = px.scatter(
        recommendations.head(250),
        x="price_vs_segment_median",
        y="recommendation_score",
        color="body_type",
        hover_data=["brand", "model", "model_year", "price", "milage", "epa_combined_mpg"],
        title="동급 중앙값 대비 가격과 추천 점수",
        labels={"price_vs_segment_median": "price vs segment median (KRW)", "recommendation_score": "score"},
    )
    fig.add_vline(x=0, line_dash="dash")
    st.plotly_chart(fig, use_container_width=True)

with right:
    top_for_chart = top.sort_values("recommendation_score").copy()
    top_for_chart["vehicle_name"] = top_for_chart["brand"] + " " + top_for_chart["model"]
    fig = px.bar(
        top_for_chart,
        x="recommendation_score",
        y="vehicle_name",
        color="deal_ratio",
        orientation="h",
        title="추천 TOP 20 점수",
        labels={"recommendation_score": "score", "vehicle_name": "vehicle", "deal_ratio": "deal ratio"},
    )
    st.plotly_chart(fig, use_container_width=True)

st.caption("좌석 수는 EPA 차량 등급 기반 추정값입니다. 정확한 좌석 수는 세부 트림에 따라 다를 수 있습니다.")
