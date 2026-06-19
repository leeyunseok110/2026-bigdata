# pages/3_data.py
import streamlit as st
import plotly.express as px
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from utils.data_loader import load_bike_data, get_station_summary

st.title("🔍 데이터 조회")

df = load_bike_data()
summary = get_station_summary(df)

tab1, tab2 = st.tabs(["대여소 요약", "원본 데이터"])

with tab1:
    st.subheader("대여소별 요약 통계")
    st.dataframe(summary, use_container_width=True)

    selected_station = st.selectbox("상세 확인할 대여소 선택", summary["대여소"].tolist())
    detail = df[df["대여소"] == selected_station]
    daily_detail = detail.groupby("날짜")["대여건수"].sum().reset_index()

    fig = px.line(
        daily_detail,
        x="날짜",
        y="대여건수",
        markers=True,
        title=f"{selected_station} 일자별 대여 추이"
    )
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("원본 데이터")
    selected_columns = st.multiselect(
        "표시할 컬럼 선택",
        options=df.columns.tolist(),
        default=df.columns.tolist()
    )

    if selected_columns:
        show_df = df[selected_columns]
        st.write(f"총 {len(show_df):,}건")
        st.dataframe(show_df, use_container_width=True, height=400)

        csv = show_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "📥 CSV 다운로드",
            data=csv,
            file_name="bike_data.csv",
            mime="text/csv"
        )
    else:
        st.warning("컬럼을 1개 이상 선택하세요.")