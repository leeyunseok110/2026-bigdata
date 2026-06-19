# my_profile.py
import streamlit as st
import pandas as pd

st.title("자기소개")

st.write("## 기본 정보")
st.write("**이름**: 이윤석")
st.write("**학과**: 인공지능소프트웨어학과")
st.write("**학년**: 3학년")

st.write("---")

st.write("## 이번 학기 시간표")
schedule = pd.DataFrame({
    "요일": ["월", "화", "수", "목", "금"],
    "2교시": ["-", "-", "-", "인공지능서비스프로젝트", "빅데이터분석프로젝트"],
    "3교시": ["-", "-", "-", "인공지능서비스프로젝트", "빅데이터분석프로젝트"],
    "4교시": ["-", "-", "-", "인공지능서비스프로젝트", "빅데이터분석프로젝트"],
    "5교시": ["-", "-", "-", "-", "-"],
    "6교시": ["인공지능라이브러리", "인공지능캡스톤디자인", "-", "-", "자연어처리"],
    "7교시": ["인공지능라이브러리", "인공지능캡스톤디자인", "-", "-", "자연어처리"],
    "8교시": ["인공지능라이브러리", "인공지능캡스톤디자인", "-", "-", "자연어처리"],
    "9교시": ["-", "인공지능캡스톤디자인", "-", "-", "-"]
})
st.dataframe(schedule, use_container_width=True)

st.write("---")

st.write("## 관심 분야")
st.write("- 머신러닝")
st.write("- 데이터 시각화")

st.write("---")

st.write("## 이번 학기 목표")
goals = pd.DataFrame({
    "목표": ["평균 성적 3.5 넘기"],
    "달성률": [0]
})
st.dataframe(goals, use_container_width=True)

st.bar_chart(goals.set_index("목표"))