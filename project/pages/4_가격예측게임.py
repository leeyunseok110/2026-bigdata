import random

import streamlit as st

from src.data_loader import load_used_cars
from src.insights import format_currency, format_exchange_rate_caption, format_number


@st.cache_data
def get_data():
    return load_used_cars()


def get_game_pool():
    df = get_data()
    upper_price = df["price"].quantile(0.99)
    return df[df["price"] <= upper_price].reset_index(drop=True)


def pick_new_car():
    pool = get_game_pool()
    st.session_state.game_car_index = random.randint(0, len(pool) - 1)
    st.session_state.game_attempts = 0
    st.session_state.game_revealed = False
    st.session_state.game_last_message = ""


def reset_game_state():
    st.session_state.game_score = 0
    st.session_state.game_round = 1
    pick_new_car()


pool = get_game_pool()
MAX_ATTEMPTS = 10

if "game_car_index" not in st.session_state:
    st.session_state.game_score = 0
    st.session_state.game_round = 1
    pick_new_car()

car = pool.iloc[st.session_state.game_car_index]
actual_price = int(car["price"])

st.title("가격 예측 게임")
st.caption("차량 정보를 보고 실제 중고차 가격을 맞혀보세요. 입력한 가격이 낮으면 UP, 높으면 DOWN으로 알려줍니다.")
st.caption(format_exchange_rate_caption())
st.write("점수는 1번째 시도 10점에서 시작해 시도할 때마다 1점씩 감소하며, 10번째 시도는 1점입니다.")

score_cols = st.columns(4)
score_cols[0].metric("라운드", st.session_state.game_round)
score_cols[1].metric("점수", st.session_state.game_score)
score_cols[2].metric("시도 횟수", st.session_state.game_attempts)
score_cols[3].metric("남은 기회", max(MAX_ATTEMPTS - st.session_state.game_attempts, 0))

st.subheader("차량 정보")
info_cols = st.columns(3)
info_cols[0].metric("브랜드", car["brand"])
info_cols[1].metric("모델", car["model"])
info_cols[2].metric("연식", int(car["model_year"]))

detail_cols = st.columns(4)
detail_cols[0].metric("주행거리", f"{format_number(car['milage'])} mi")
detail_cols[1].metric("연료", car["fuel_type"])
detail_cols[2].metric("변속기", car["transmission"])
detail_cols[3].metric("사고 이력", car["accident_flag"])

guess = st.number_input(
    "예상 가격(원)",
    min_value=0,
    max_value=int(pool["price"].max()),
    value=int(pool["price"].median()),
    step=1_000_000,
)

button_cols = st.columns([1, 1, 1, 3])
submit_disabled = st.session_state.game_revealed or st.session_state.game_attempts >= MAX_ATTEMPTS
submit = button_cols[0].button("제출", type="primary", disabled=submit_disabled)
reveal = button_cols[1].button("정답 보기")
next_round = button_cols[2].button("다음 문제")

if submit:
    st.session_state.game_attempts += 1
    difference = abs(guess - actual_price)
    tolerance = max(actual_price * 0.05, 1000)

    if difference <= tolerance:
        earned = max(11 - st.session_state.game_attempts, 1)
        st.session_state.game_score += earned
        st.session_state.game_revealed = True
        st.session_state.game_last_message = (
            f"정답에 가깝습니다. 실제 가격은 {format_currency(actual_price)}이고 "
            f"{earned}점을 획득했습니다."
        )
    elif guess < actual_price:
        st.session_state.game_last_message = "UP: 실제 가격이 입력한 가격보다 높습니다."
    else:
        st.session_state.game_last_message = "DOWN: 실제 가격이 입력한 가격보다 낮습니다."

    if st.session_state.game_attempts >= MAX_ATTEMPTS and not st.session_state.game_revealed:
        st.session_state.game_revealed = True
        st.session_state.game_last_message = (
            f"기회를 모두 사용했습니다. 정답은 {format_currency(actual_price)}입니다."
        )

if reveal:
    st.session_state.game_revealed = True
    st.session_state.game_last_message = f"정답은 {format_currency(actual_price)}입니다."

if next_round:
    st.session_state.game_round += 1
    pick_new_car()
    st.rerun()

if st.session_state.game_last_message:
    if st.session_state.game_revealed:
        st.success(st.session_state.game_last_message)
    else:
        st.info(st.session_state.game_last_message)

if st.session_state.game_revealed:
    st.subheader("정답 차량")
    answer_cols = st.columns(3)
    answer_cols[0].metric("실제 가격", format_currency(actual_price))
    answer_cols[1].metric("내 입력", format_currency(guess))
    answer_cols[2].metric("차이", format_currency(abs(guess - actual_price)))

    st.dataframe(
        car[
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
        ]
        .to_frame()
        .T,
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

st.divider()
if st.button("게임 초기화"):
    reset_game_state()
    st.rerun()
