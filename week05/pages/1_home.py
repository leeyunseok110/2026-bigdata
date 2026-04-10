# pages/1_home.py
import streamlit as st
import plotly.express as px
import pandas as pd
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from utils.data_loader import load_bike_data

st.title("🚲 서울시 공공자전거 대시보드")

df = load_bike_data()

# 사이드바 필터
st.sidebar.subheader("필터")
selected_stations = st.sidebar.multiselect(
    "대여소 선택",
    options=sorted(df["대여소"].unique()),
    default=sorted(df["대여소"].unique())
)

date_range = st.sidebar.date_input(
    "날짜 범위",
    value=(df["날짜"].min(), df["날짜"].max()),
    min_value=df["날짜"].min(),
    max_value=df["날짜"].max()
)

# 필터 적용
if len(date_range) == 2:
    filtered = df[
        (df["대여소"].isin(selected_stations)) &
        (df["날짜"] >= pd.Timestamp(date_range[0])) &
        (df["날짜"] <= pd.Timestamp(date_range[1]))
    ]
else:
    filtered = df[df["대여소"].isin(selected_stations)]

# KPI
k1, k2, k3, k4 = st.columns(4)
k1.metric("총 대여 건수", f"{filtered['대여건수'].sum():,}건")
k2.metric("일 평균 대여", f"{filtered['대여건수'].sum() / max(filtered['날짜'].nunique(), 1):.0f}건")
k3.metric("평균 이용 시간", f"{filtered['이용시간(분)'].mean():.0f}분")
k4.metric("대여소 수", f"{filtered['대여소'].nunique()}곳")

st.divider()

st.caption(
    f"데이터 기간: {filtered['날짜'].min().strftime('%Y-%m-%d')} ~ {filtered['날짜'].max().strftime('%Y-%m-%d')}"
)

# 월별 추이
monthly = filtered.groupby("날짜")["대여건수"].sum().reset_index()
fig = px.area(monthly, x="날짜", y="대여건수", title="일자별 대여 건수 추이")
st.plotly_chart(fig, use_container_width=True)

# 하단 차트
col1, col2 = st.columns(2)

with col1:
    top5 = (
        filtered.groupby("대여소")["대여건수"]
        .sum()
        .nlargest(5)
        .reset_index()
    )
    fig_bar = px.bar(
        top5,
        x="대여건수",
        y="대여소",
        orientation="h",
        title="대여소별 총 대여 건수 TOP 5"
    )
    st.plotly_chart(fig_bar, use_container_width=True)

with col2:
    station_total = filtered.groupby("대여소")["대여건수"].sum().reset_index()
    fig_pie = px.pie(
        station_total,
        names="대여소",
        values="대여건수",
        title="대여소별 대여 비중",
        hole=0.4
    )
    st.plotly_chart(fig_pie, use_container_width=True)