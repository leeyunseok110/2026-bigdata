import pandas as pd
import streamlit as st

from src.data_loader import load_used_cars
from src.insights import format_currency
from src.external_data import make_model_key, normalize_make
from src.korea_market import (
    KOREA_REFERENCE_COLUMNS,
    KOREA_REFERENCE_PATH,
    KOREA_TEMPLATE_PATH,
    create_reference_template,
    load_korea_reference,
    save_korea_reference,
)


@st.cache_data
def get_data():
    return load_used_cars()


df = get_data()
reference = load_korea_reference()


def create_demo_reference(data: pd.DataFrame, limit: int = 8) -> pd.DataFrame:
    demo_pool = (
        data[data["model_year"].between(2018, 2025)]
        .groupby(["brand", "model", "model_year"], as_index=False)
        .agg(rows=("price", "size"), median_price=("price", "median"))
        .query("rows >= 3")
        .sort_values(["rows", "model_year"], ascending=[False, False])
        .head(limit)
        .copy()
    )
    demo_pool["reference_price_krw"] = (demo_pool["median_price"] * 0.92).round(-5).astype(int)
    demo_pool["reference_source"] = "데모용 샘플(앱 중앙값 기반)"
    demo_pool["reference_date"] = "발표 데모"
    demo_pool["note"] = "실제 자동차365/보험개발원 조회값으로 교체 필요"
    return demo_pool[KOREA_REFERENCE_COLUMNS]


def build_korea_comparison(data: pd.DataFrame, ref: pd.DataFrame) -> pd.DataFrame:
    if ref.empty:
        return pd.DataFrame()

    cars = data.copy()
    cars["make_norm"] = cars["brand"].map(normalize_make)
    cars["model_key"] = [make_model_key(model, brand) for model, brand in zip(cars["model"], cars["brand"])]

    rows = []
    for _, item in ref.iterrows():
        matched = cars[
            (cars["make_norm"] == item["make_norm"])
            & (cars["model_key"] == item["model_key"])
            & cars["model_year"].between(int(item["model_year"]) - 1, int(item["model_year"]) + 1)
        ].copy()
        if matched.empty:
            rows.append(
                {
                    "brand": item["brand"],
                    "model": item["model"],
                    "model_year": item["model_year"],
                    "reference_price_krw": item["reference_price_krw"],
                    "matched_rows": 0,
                    "us_market_median_krw": pd.NA,
                    "gap_krw": pd.NA,
                    "gap_ratio": pd.NA,
                    "reference_source": item.get("reference_source", "-"),
                }
            )
            continue

        us_median = matched["price"].median()
        gap = us_median - float(item["reference_price_krw"])
        rows.append(
            {
                "brand": item["brand"],
                "model": item["model"],
                "model_year": item["model_year"],
                "reference_price_krw": item["reference_price_krw"],
                "matched_rows": len(matched),
                "us_market_median_krw": us_median,
                "gap_krw": gap,
                "gap_ratio": gap / float(item["reference_price_krw"]),
                "reference_source": item.get("reference_source", "-"),
            }
        )
    return pd.DataFrame(rows)

st.title("한국 기준 시세 보정")
st.caption("미국 매물 기반 예측가와 한국에서 조회한 기준가액의 차이를 비교해 구입 판독 AI에 보조 근거로 반영합니다.")

metric_cols = st.columns(3)
metric_cols[0].metric("등록된 기준가액", f"{len(reference):,}건")
metric_cols[1].metric("기준가액 파일", "있음" if KOREA_REFERENCE_PATH.exists() else "없음")
metric_cols[2].metric("앱 매물 수", f"{len(df):,}건")

st.info(
    "이 페이지는 한국 시세를 자동 수집하는 기능이 아니라, "
    "사용자가 자동차365/보험개발원/카히스토리에서 조회한 기준가액을 CSV로 넣어 "
    "미국 매물 기반 예측 결과를 한국 기준과 비교하는 보조 기능입니다."
)

st.subheader("CSV 형식")
st.write("아래 컬럼명 그대로 CSV를 만들면 됩니다.")
st.code(",".join(KOREA_REFERENCE_COLUMNS), language="text")

template_col, demo_col = st.columns(2)
with template_col:
    if st.button("빈 템플릿 CSV 생성"):
        template = create_reference_template(df)
        st.success(f"템플릿을 생성했습니다: {KOREA_TEMPLATE_PATH}")
        st.dataframe(template.head(20), use_container_width=True, hide_index=True)

with demo_col:
    if st.button("데모용 샘플 기준가액 저장"):
        demo_reference = create_demo_reference(df)
        normalized = save_korea_reference(demo_reference)
        st.success(f"데모용 기준가액 {len(normalized):,}건을 저장했습니다.")
        st.warning("데모용 값은 실제 한국 기준가액이 아닙니다. 제출/실사용 전 실제 조회값으로 교체하세요.")
        reference = normalized

uploaded = st.file_uploader("한국 기준가액 CSV 업로드", type=["csv"])
if uploaded is not None:
    uploaded_df = pd.read_csv(uploaded)
    missing = [column for column in KOREA_REFERENCE_COLUMNS if column not in uploaded_df.columns]
    if missing:
        st.error(f"필수 컬럼이 없습니다: {', '.join(missing)}")
    else:
        normalized = save_korea_reference(uploaded_df)
        st.success(f"한국 기준가액 {len(normalized):,}건을 저장했습니다.")
        reference = normalized

st.subheader("현재 등록된 기준가액")
if reference.empty:
    st.info("아직 등록된 한국 기준가액이 없습니다. 자동차365/보험개발원에서 조회한 값을 CSV로 업로드하세요.")
else:
    display = reference[KOREA_REFERENCE_COLUMNS].copy()
    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "reference_price_krw": st.column_config.NumberColumn("한국 기준가액", format="₩%d"),
        },
    )
    st.write(f"평균 기준가액: {format_currency(reference['reference_price_krw'].mean())}")

st.subheader("미국 매물 시세 vs 한국 기준가액")
comparison = build_korea_comparison(df, reference)
if comparison.empty:
    st.info("등록된 한국 기준가액이 있으면 미국 매물 중앙값과의 차이를 여기에서 비교합니다.")
else:
    matched = comparison[comparison["matched_rows"] > 0].copy()
    compare_cols = st.columns(4)
    compare_cols[0].metric("비교 대상", f"{len(comparison):,}건")
    compare_cols[1].metric("앱 매물 매칭", f"{len(matched):,}건")
    if not matched.empty:
        compare_cols[2].metric("평균 차이", format_currency(matched["gap_krw"].mean()))
        compare_cols[3].metric("평균 차이율", f"{matched['gap_ratio'].mean():.1%}")
    else:
        compare_cols[2].metric("평균 차이", "-")
        compare_cols[3].metric("평균 차이율", "-")

    st.dataframe(
        comparison,
        use_container_width=True,
        hide_index=True,
        column_config={
            "reference_price_krw": st.column_config.NumberColumn("한국 기준가액", format="₩%d"),
            "matched_rows": st.column_config.NumberColumn("매칭 매물 수", format="%d"),
            "us_market_median_krw": st.column_config.NumberColumn("미국 매물 중앙값", format="₩%d"),
            "gap_krw": st.column_config.NumberColumn("미국-한국 차이", format="₩%d"),
            "gap_ratio": st.column_config.NumberColumn("차이율", format="%.1%"),
        },
    )
    st.caption(
        "차이가 양수면 앱의 미국 매물 중앙값이 한국 기준가액보다 높은 편이고, "
        "음수면 한국 기준가액이 더 높은 편으로 해석할 수 있습니다."
    )

st.subheader("자료 입력 방법")
st.write("- 자동차365에서 중고차 시세 또는 평균매매가를 조회합니다.")
st.write("- 보험개발원/카히스토리에서 차량기준가액을 조회합니다.")
st.write("- 브랜드, 모델, 연식, 기준가액, 출처, 조회일자를 CSV에 입력합니다.")
st.write("- 업로드하면 `구입 판독 AI`에서 해당 차량과 매칭될 때 한국 기준가액이 판정에 반영됩니다.")
