import pandas as pd

from src.currency import USD_TO_KRW_RATE, USD_TO_KRW_RATE_DATE


def format_currency(value: float) -> str:
    return f"₩{value:,.0f}"


def format_exchange_rate_caption() -> str:
    return f"환율 기준: 1 USD = ₩{USD_TO_KRW_RATE:,.2f} ({USD_TO_KRW_RATE_DATE})"


def format_number(value: float) -> str:
    return f"{value:,.0f}"


def build_insights(full_df: pd.DataFrame, filtered_df: pd.DataFrame) -> list[str]:
    if filtered_df.empty:
        return ["선택한 조건에 맞는 차량이 없습니다. 필터 범위를 넓혀보세요."]

    insights = []
    full_avg = full_df["price"].mean()
    filtered_avg = filtered_df["price"].mean()
    diff = filtered_avg - full_avg

    if diff >= 0:
        insights.append(f"선택한 조건의 평균 가격은 전체 평균보다 {format_currency(diff)} 높습니다.")
    else:
        insights.append(f"선택한 조건의 평균 가격은 전체 평균보다 {format_currency(abs(diff))} 낮습니다.")

    top_brand = filtered_df["brand"].value_counts().idxmax()
    top_brand_count = filtered_df["brand"].value_counts().max()
    insights.append(f"필터링 결과에서 가장 많은 브랜드는 {top_brand}이며, {top_brand_count:,}대가 포함되어 있습니다.")

    no_accident = filtered_df[filtered_df["accident_flag"] == "사고 이력 없음"]["price"].mean()
    accident = filtered_df[filtered_df["accident_flag"] == "사고/손상 이력 있음"]["price"].mean()
    if pd.notna(no_accident) and pd.notna(accident):
        gap = no_accident - accident
        if gap >= 0:
            insights.append(f"사고 이력이 없는 차량의 평균 가격이 사고/손상 이력이 있는 차량보다 {format_currency(gap)} 높습니다.")
        else:
            insights.append(f"사고/손상 이력이 있는 차량의 평균 가격이 사고 이력이 없는 차량보다 {format_currency(abs(gap))} 높습니다.")

    return insights
