# pages/2_charts.py
import streamlit as st
import plotly.express as px
import altair as alt
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from utils.data_loader import load_bike_data

st.title("📊 차트 분석")

df = load_bike_data()

tab1, tab2, tab3 = st.tabs(["일자별 패턴", "대여소 비교", "이용시간 분포"])

with tab1:
    st.subheader("일자별 대여 패턴")
    daily = df.groupby("날짜")["대여건수"].sum().reset_index()
    fig = px.line(daily, x="날짜", y="대여건수", markers=True, title="일자별 총 대여 건수")
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("대여소별 비교 (Altair)")
    station_daily = df.groupby(["날짜", "대여소"])["대여건수"].sum().reset_index()

    top_stations = (
        df.groupby("대여소")["대여건수"]
        .sum()
        .nlargest(5)
        .index
        .tolist()
    )

    selected_stations = st.multiselect(
        "비교할 대여소 선택",
        options=sorted(df["대여소"].unique()),
        default=top_stations[:3]
    )

    if selected_stations:
        chart_data = station_daily[station_daily["대여소"].isin(selected_stations)]
        brush = alt.selection_interval(encodings=["x"])

        upper = alt.Chart(chart_data).mark_line(point=True).encode(
            x="날짜:T",
            y="대여건수:Q",
            color="대여소:N",
            tooltip=["날짜:T", "대여소:N", "대여건수:Q"]
        ).properties(
            height=250,
            title="날짜 범위를 드래그해서 선택"
        ).add_params(brush)

        lower = alt.Chart(chart_data).mark_bar().encode(
            x=alt.X("대여소:N", axis=alt.Axis(labelAngle=0)),
            y="mean(대여건수):Q",
            color="대여소:N",
            tooltip=["대여소:N", "mean(대여건수):Q"]
        ).transform_filter(
            brush
        ).properties(
            height=200,
            title="선택 구간 평균 대여 건수"
        )

        st.altair_chart(upper & lower, use_container_width=True)
    else:
        st.warning("대여소를 1개 이상 선택하세요.")

with tab3:
    st.subheader("이용시간 분포")
    fig = px.histogram(
        df,
        x="이용시간(분)",
        nbins=30,
        title="이용시간 분포",
        marginal="box"
    )
    st.plotly_chart(fig, use_container_width=True)

    c1, c2, c3 = st.columns(3)
    c1.metric("중앙값", f"{df['이용시간(분)'].median():.0f}분")
    c2.metric("평균", f"{df['이용시간(분)'].mean():.0f}분")
    c3.metric("최댓값", f"{df['이용시간(분)'].max():.0f}분")