# utils/data_loader.py
import streamlit as st
import pandas as pd
import numpy as np


@st.cache_data
def load_bike_data():
    np.random.seed(42)

    n = 3000
    stations = [
        "여의도역", "강남역", "홍대입구", "서울역", "잠실역",
        "신촌역", "합정역", "건대입구", "왕십리역", "이태원역"
    ]
    dates = pd.date_range("2025-01-01", periods=90)

    df = pd.DataFrame({
        "날짜": np.random.choice(dates, n),
        "대여소": np.random.choice(stations, n),
        "대여건수": np.random.poisson(lam=15, size=n),
        "반납건수": np.random.poisson(lam=14, size=n),
        "이용시간(분)": np.random.exponential(scale=25, size=n).astype(int) + 5
    })

    df["날짜"] = pd.to_datetime(df["날짜"])
    df = df.sort_values(["날짜", "대여소"]).reset_index(drop=True)
    return df


@st.cache_data
def get_station_summary(df):
    if df.empty:
        return pd.DataFrame()

    summary = df.groupby("대여소").agg(
        총대여건수=("대여건수", "sum"),
        총반납건수=("반납건수", "sum"),
        평균이용시간=("이용시간(분)", "mean"),
        일평균대여=("대여건수", lambda x: x.sum() / max(df["날짜"].nunique(), 1))
    ).round(1).reset_index()

    return summary