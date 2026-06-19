import pandas as pd
import plotly.express as px
import streamlit as st

from src.data_loader import load_used_cars
from src.insights import format_currency, format_exchange_rate_caption


@st.cache_data
def get_data():
    return load_used_cars()


df = get_data()

st.title("외부 데이터 결합")
st.caption("EPA 연비 데이터와 NHTSA 리콜 데이터를 중고차 매물 데이터에 결합한 결과입니다.")
st.caption(format_exchange_rate_caption())

if "external_epa_matched" not in df.columns or "external_nhtsa_matched" not in df.columns:
    st.warning("결합 데이터가 아직 생성되지 않았습니다. scripts/build_enriched_data.py를 먼저 실행하세요.")
    st.stop()

epa_matched = int(df["external_epa_matched"].sum())
nhtsa_matched = int(df["external_nhtsa_matched"].sum())
latest_df = df[df["model_year"].between(2024, 2026)].copy()

metric_cols = st.columns(4)
metric_cols[0].metric("전체 매물", f"{len(df):,}")
metric_cols[1].metric("EPA 연비 매칭", f"{epa_matched:,}", f"{epa_matched / len(df):.1%}")
metric_cols[2].metric("NHTSA 리콜 매칭", f"{nhtsa_matched:,}", f"{nhtsa_matched / len(df):.1%}")
metric_cols[3].metric("평균 리콜 수", f"{df['nhtsa_recall_count'].mean():.2f}")

with st.expander("데이터 출처와 라이선스 정리", expanded=True):
    st.write(
        "루브릭의 데이터 출처·라이선스 항목을 명확히 하기 위해, "
        "앱에서 사용하는 데이터의 역할과 주의사항을 함께 정리했습니다."
    )
    source_rows = [
        {
            "데이터": "원본 중고차 매물",
            "파일/위치": "data/used_cars.csv",
            "앱에서의 역할": "기본 EDA, 가격 예측, 시각화의 출발 데이터",
            "출처/라이선스 메모": "수업/프로젝트 폴더 제공 CSV. 외부 공개 전 원본 URL과 라이선스 최종 확인 필요",
        },
        {
            "데이터": "CARFAX 최신 샘플",
            "파일/위치": "data/external/carfax_latest/carfax_latest_2024_2026.csv",
            "앱에서의 역할": "2024~2026년 최신 연식 매물 보강",
            "출처/라이선스 메모": "reBrowser CARFAX sample dataset 기반. 실시간 시세가 아니라 공개 샘플 데이터",
        },
        {
            "데이터": "EPA 차량 연비",
            "파일/위치": "data/external/epa_vehicle_summary.csv",
            "앱에서의 역할": "연비, 연료비, 차급 정보를 추천 점수와 판독 근거에 활용",
            "출처/라이선스 메모": "미국 EPA 공개 차량 연비 데이터 요약본",
        },
        {
            "데이터": "NHTSA 리콜 요약",
            "파일/위치": "data/external/nhtsa_recall_summary.csv",
            "앱에서의 역할": "리콜 수, 영향 대수, 주요 부품 정보를 안전성 지표로 활용",
            "출처/라이선스 메모": "미국 NHTSA 공개 리콜 데이터 요약본",
        },
        {
            "데이터": "한국 기준가액",
            "파일/위치": "data/korea_market_reference.csv",
            "앱에서의 역할": "자동차365/보험개발원 기준가액을 직접 입력해 한국 시세 보정",
            "출처/라이선스 메모": "사용자가 조회 후 CSV로 입력하는 보조 자료",
        },
    ]
    st.dataframe(pd.DataFrame(source_rows), use_container_width=True, hide_index=True)

    latest_cols = st.columns(4)
    latest_cols[0].metric("최신 연식 매물", f"{len(latest_df):,}", "2024~2026")
    for year, col in zip([2024, 2025, 2026], latest_cols[1:]):
        col.metric(f"{year}년식", f"{int((df['model_year'] == year).sum()):,}")
    st.warning(
        "발표 시에는 '실시간 최신 시세'가 아니라 "
        "'2024~2026년 최신 연식 샘플 매물을 추가 보강했다'고 설명하는 것이 정확합니다."
    )

st.subheader("결합된 주요 컬럼")
display_columns = [
    "brand",
    "model",
    "model_year",
    "price",
    "epa_combined_mpg",
    "epa_annual_fuel_cost_krw",
    "epa_vehicle_class",
    "nhtsa_recall_count",
    "nhtsa_affected_units",
    "nhtsa_top_component",
]
existing_columns = [column for column in display_columns if column in df.columns]
st.dataframe(
    df[existing_columns].head(30),
    use_container_width=True,
    hide_index=True,
    column_config={
        "price": st.column_config.NumberColumn("price (KRW)", format="₩%d"),
        "epa_combined_mpg": st.column_config.NumberColumn("EPA combined MPG", format="%.1f"),
        "epa_annual_fuel_cost_krw": st.column_config.NumberColumn("EPA annual fuel cost (KRW)", format="₩%d"),
        "nhtsa_recall_count": st.column_config.NumberColumn("NHTSA recall count", format="%d"),
        "nhtsa_affected_units": st.column_config.NumberColumn("NHTSA affected units", format="%d"),
    },
)

matched_epa_df = df[df["external_epa_matched"]].copy()
matched_nhtsa_df = df[df["external_nhtsa_matched"]].copy()

left, right = st.columns(2)

with left:
    st.subheader("연비와 가격")
    if matched_epa_df.empty:
        st.info("EPA와 매칭된 차량이 없습니다.")
    else:
        sample = matched_epa_df.sample(min(len(matched_epa_df), 2500), random_state=42)
        fig = px.scatter(
            sample,
            x="epa_combined_mpg",
            y="price",
            color="fuel_type",
            hover_data=["brand", "model", "model_year", "milage"],
            title="EPA 복합 연비와 중고차 가격",
            labels={
                "epa_combined_mpg": "EPA combined MPG",
                "price": "price (KRW)",
                "fuel_type": "fuel type",
            },
        )
        st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("리콜 수와 가격")
    if matched_nhtsa_df.empty:
        st.info("NHTSA와 매칭된 차량이 없습니다.")
    else:
        sample = matched_nhtsa_df.sample(min(len(matched_nhtsa_df), 2500), random_state=42)
        recall_groups = pd.cut(
            sample["nhtsa_recall_count"],
            bins=[0, 1, 3, 6, 100],
            labels=["1", "2-3", "4-6", "7+"],
        )
        fig = px.box(
            sample,
            x=recall_groups,
            y="price",
            title="NHTSA 리콜 수 구간별 가격 분포",
            labels={"x": "recall count group", "price": "price (KRW)"},
        )
        st.plotly_chart(fig, use_container_width=True)

st.subheader("브랜드별 외부 데이터 매칭률")
brand_match = (
    df.groupby("brand", as_index=False)
    .agg(
        rows=("brand", "size"),
        epa_match_rate=("external_epa_matched", "mean"),
        nhtsa_match_rate=("external_nhtsa_matched", "mean"),
        avg_price=("price", "mean"),
    )
    .query("rows >= 10")
    .sort_values("rows", ascending=False)
)

fig = px.bar(
    brand_match.head(20),
    x="brand",
    y=["epa_match_rate", "nhtsa_match_rate"],
    barmode="group",
    title="상위 브랜드 매칭률",
    labels={"value": "match rate", "variable": "dataset", "brand": "brand"},
)
fig.update_yaxes(tickformat=".0%")
st.plotly_chart(fig, use_container_width=True)

st.subheader("활용 아이디어")
st.write(f"- EPA 연비가 붙은 차량의 평균 가격은 {format_currency(matched_epa_df['price'].mean())}입니다.")
st.write("- `epa_combined_mpg`, `epa_annual_fuel_cost_krw`를 가격 예측 모델의 추가 변수로 사용할 수 있습니다.")
st.write("- `nhtsa_recall_count`, `nhtsa_top_component`를 안전성/리스크 지표로 만들어 차량 추천 점수에 반영할 수 있습니다.")
