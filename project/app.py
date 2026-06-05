import streamlit as st


st.set_page_config(
    page_title="중고차 데이터 분석 서비스",
    page_icon="🚗",
    layout="wide",
)


pages = [
    st.Page("pages/1_EDA.py", title="EDA", icon="📊"),
    st.Page("pages/2_시각화.py", title="시각화", icon="📈"),
    st.Page("pages/3_모델_서비스.py", title="모델/서비스", icon="🧮"),
    st.Page("pages/4_가격예측게임.py", title="가격 예측 게임", icon="🎮"),
    st.Page("pages/5_외부데이터.py", title="외부 데이터", icon="🔗"),
    st.Page("pages/6_추천.py", title="차량 추천", icon="✅"),
    st.Page("pages/7_구입판독AI.py", title="구입 판독 AI", icon="🤖"),
    st.Page("pages/8_한국기준보정.py", title="한국 기준 보정", icon="🇰🇷"),
    st.Page("pages/9_내차가격예측.py", title="내 차 가격 예측", icon="💰"),
]

navigation = st.navigation(pages)
navigation.run()
