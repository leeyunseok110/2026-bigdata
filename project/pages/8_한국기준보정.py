import pandas as pd
import streamlit as st

from src.data_loader import load_used_cars
from src.insights import format_currency
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

st.title("한국 기준 시세 보정")
st.caption("자동차365 또는 보험개발원에서 조회한 차량 기준가액을 CSV로 넣으면 구입 판독 AI가 한국 기준가를 함께 반영합니다.")

metric_cols = st.columns(3)
metric_cols[0].metric("등록된 기준가액", f"{len(reference):,}건")
metric_cols[1].metric("기준가액 파일", "있음" if KOREA_REFERENCE_PATH.exists() else "없음")
metric_cols[2].metric("앱 매물 수", f"{len(df):,}건")

st.subheader("CSV 형식")
st.write("아래 컬럼명 그대로 CSV를 만들면 됩니다.")
st.code(",".join(KOREA_REFERENCE_COLUMNS), language="text")

if st.button("템플릿 CSV 생성"):
    template = create_reference_template(df)
    st.success(f"템플릿을 생성했습니다: {KOREA_TEMPLATE_PATH}")
    st.dataframe(template.head(20), use_container_width=True, hide_index=True)

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

st.subheader("자료 입력 방법")
st.write("- 자동차365에서 중고차 시세 또는 평균매매가를 조회합니다.")
st.write("- 보험개발원/카히스토리에서 차량기준가액을 조회합니다.")
st.write("- 브랜드, 모델, 연식, 기준가액, 출처, 조회일자를 CSV에 입력합니다.")
st.write("- 업로드하면 `구입 판독 AI`에서 해당 차량과 매칭될 때 한국 기준가액이 판정에 반영됩니다.")
