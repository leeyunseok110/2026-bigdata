import pandas as pd
import streamlit as st

from src.data_loader import load_used_cars
from src.insights import format_currency, format_exchange_rate_caption, format_number
from src.model import train_price_model
from src.recommender import BODY_TYPE_ORDER
from src.vehicle_evaluator import evaluate_vehicle


@st.cache_data
def get_data():
    return load_used_cars()


@st.cache_resource
def get_price_model(_data):
    return train_price_model(_data)


df = get_data()
price_model, model_metrics = get_price_model(df)

st.title("구입 차량 가성비 판독 AI")
st.caption("구입하려는 차량 조건과 판매가를 입력하면 예측가, 동급 시세, 사고/리콜 위험을 함께 판독합니다.")
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
    model = st.text_input("모델", value=model_options[0] if model_options else "")

with st.form("vehicle_eval_form"):
    st.subheader("차량 정보 입력")
    left, right = st.columns(2)

    with left:
        model_year = st.number_input(
            "연식",
            min_value=int(df["model_year"].min()),
            max_value=int(df["model_year"].max()) + 1,
            value=int(df["model_year"].median()),
            step=1,
        )
        milage = st.number_input(
            "주행거리(mi)",
            min_value=0,
            max_value=int(df["milage"].max()),
            value=int(df["milage"].median()),
            step=1000,
        )
        asking_price = st.number_input(
            "판매가/구입 희망가(원)",
            min_value=0,
            max_value=int(df["price"].quantile(0.995)),
            value=int(df["price"].median()),
            step=1_000_000,
        )

    with right:
        fuel_type = st.selectbox("연료 종류", sorted(brand_df["fuel_type"].dropna().unique()))
        transmission = st.selectbox("변속기", ["자동", "수동", "기타"])
        accident_label = st.selectbox("사고/손상 이력", ["없음", "있음"])
        accident_flag_options = sorted(df["accident_flag"].dropna().unique())
        no_accident_flag = next((value for value in accident_flag_options if "없" in value), accident_flag_options[0])
        accident_flag = no_accident_flag if accident_label == "없음" else next(
            (value for value in accident_flag_options if value != no_accident_flag),
            accident_flag_options[-1],
        )
        clean_title = st.selectbox("클린 타이틀", sorted(df["clean_title"].dropna().unique()))
        body_type = st.selectbox("차종", ["자동 추정"] + BODY_TYPE_ORDER, index=0)
        seat_group = st.selectbox("탑승 인원", ["자동 추정", "2 seats", "4-5 seats", "6+ seats"], index=0)

    submitted = st.form_submit_button("가성비 판독", type="primary")

if not submitted:
    st.info("왼쪽부터 차량 조건을 입력하고 `가성비 판독`을 누르세요.")
    st.stop()

input_data = {
    "brand": brand,
    "model": model,
    "model_year": int(model_year),
    "milage": float(milage),
    "fuel_type": fuel_type,
    "transmission": transmission,
    "accident_flag": accident_flag,
    "accident_raw": "None reported" if accident_label == "없음" else "At least 1 accident or damage reported",
    "clean_title": clean_title,
    "asking_price": float(asking_price),
    "body_type": body_type,
    "seat_group": seat_group,
}

result = evaluate_vehicle(df, price_model, input_data)
subject = result["subject"]

st.subheader("AI 판독 결과")
metric_cols = st.columns(4)
metric_cols[0].metric("판정", result["verdict"])
metric_cols[1].metric("가성비 점수", f"{subject['recommendation_score']:.1f}/100")
metric_cols[2].metric("AI 예측 적정가", format_currency(result["predicted_price"]))
metric_cols[3].metric("입력가-예측가 차이", format_currency(result["model_gap"]))

st.write(result["verdict_detail"])

detail_cols = st.columns(4)
detail_cols[0].metric("동급 중앙값", format_currency(subject["segment_median_price"]))
detail_cols[1].metric("동급 대비 차이", format_currency(subject["price_vs_segment_median"]))
detail_cols[2].metric("할인율", f"{subject['deal_ratio']:.1%}")
detail_cols[3].metric("데이터 신뢰도", f"{subject['data_confidence']:.2f}")

if result["korea_reference"] is not None:
    korea_ref = result["korea_reference"]
    st.subheader("한국 기준가액 보정")
    korea_cols = st.columns(4)
    korea_cols[0].metric("한국 기준가액", format_currency(korea_ref["reference_price_krw"]))
    korea_cols[1].metric("입력가-한국 기준가", format_currency(result["korea_gap"]))
    korea_cols[2].metric("한국 기준 대비", f"{result['korea_gap_ratio']:.1%}")
    korea_cols[3].metric("출처", str(korea_ref.get("reference_source", "-")))
    st.caption(f"조회일자: {korea_ref.get('reference_date', '-')}")
else:
    st.info("이 차량과 매칭되는 한국 기준가액이 아직 없습니다. `한국 기준 보정` 페이지에서 자동차365/보험개발원 조회값을 등록하면 판정에 반영됩니다.")

st.subheader("판독 근거")
reason_items = [
    f"추천 이유: {subject['recommendation_reason']}",
    f"모델 성능 참고: MAE {format_currency(model_metrics['mae'])}, R² {model_metrics['r2']:.3f}",
]
if pd.notna(subject.get("epa_combined_mpg")):
    reason_items.append(f"EPA 복합 연비: {subject['epa_combined_mpg']:.1f} MPG")
else:
    reason_items.append("EPA 연비 데이터: 매칭 부족")
reason_items.append(f"NHTSA 리콜 수: {int(subject.get('nhtsa_recall_count', 0))}건")
if bool(subject.get("nhtsa_do_not_drive", False)) or bool(subject.get("nhtsa_park_outside", False)):
    reason_items.append("NHTSA 소비자 주의 경고가 있어 추가 확인이 필요합니다.")
for item in reason_items:
    st.write(f"- {item}")

st.subheader("유사 비교 매물")
similar = result["similar"].copy()
display_columns = [
    "brand",
    "model",
    "model_year",
    "price",
    "milage",
    "fuel_type",
    "accident_flag",
    "epa_combined_mpg",
    "nhtsa_recall_count",
]
st.dataframe(
    similar[[column for column in display_columns if column in similar.columns]],
    use_container_width=True,
    hide_index=True,
    column_config={
        "price": st.column_config.NumberColumn("가격(원)", format="₩%d"),
        "milage": st.column_config.NumberColumn("주행거리(mi)", format="%d"),
        "epa_combined_mpg": st.column_config.NumberColumn("복합 연비(MPG)", format="%.1f"),
        "nhtsa_recall_count": st.column_config.NumberColumn("리콜 수", format="%d"),
    },
)

st.caption("판독 결과는 데이터 기반 참고용입니다. 실제 구입 전 정비 이력, 보험 이력, 침수/소유자 변경, 현장 점검을 반드시 확인하세요.")
