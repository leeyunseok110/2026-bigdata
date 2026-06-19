import pandas as pd
import plotly.express as px

from src.currency import usd_to_krw


PRICE_BINS = [
    usd_to_krw(value)
    for value in [0, 10000, 20000, 30000, 40000, 60000, 80000, 100000, 150000, 250000]
] + [float("inf")]
PRICE_LABELS = [
    "₩0~1,500만",
    "₩1,500만~3,100만",
    "₩3,100만~4,600만",
    "₩4,600만~6,100만",
    "₩6,100만~9,200만",
    "₩9,200만~1.2억",
    "₩1.2억~1.5억",
    "₩1.5억~2.3억",
    "₩2.3억~3.8억",
    "₩3.8억+",
]


def price_distribution(df: pd.DataFrame, nbins: int = 80, title: str = "가격 분포"):
    return px.histogram(
        df,
        x="price",
        nbins=nbins,
        title=title,
        labels={"price": "가격(원)", "count": "매물 수"},
    )


def regular_price_distribution(df: pd.DataFrame, upper_quantile: float = 0.99):
    upper_price = df["price"].quantile(upper_quantile)
    regular_df = df[df["price"] <= upper_price]
    fig = price_distribution(
        regular_df,
        nbins=70,
        title=f"일반 가격대 세부 분포 ({upper_quantile:.0%} 이하)",
    )
    fig.add_vline(
        x=regular_df["price"].median(),
        line_dash="dash",
        annotation_text="중앙값",
        annotation_position="top right",
    )
    return fig


def price_range_counts(df: pd.DataFrame):
    price_groups = df.copy()
    price_groups["price_range"] = pd.cut(
        price_groups["price"],
        bins=PRICE_BINS,
        labels=PRICE_LABELS,
        include_lowest=True,
        right=False,
    )
    range_counts = price_groups["price_range"].value_counts(sort=False).reset_index()
    range_counts.columns = ["price_range", "count"]
    return px.bar(
        range_counts,
        x="price_range",
        y="count",
        title="가격 구간별 매물 수",
        labels={"price_range": "가격 구간", "count": "매물 수"},
    )


def log_price_distribution(df: pd.DataFrame):
    fig = price_distribution(df, nbins=80, title="가격 분포 (로그 스케일)")
    fig.update_xaxes(type="log")
    return fig


def expensive_car_prices(df: pd.DataFrame, limit: int = 15):
    top_cars = df.sort_values("price", ascending=False).head(limit).copy()
    top_cars["car_name"] = top_cars["brand"] + " " + top_cars["model"]
    return px.bar(
        top_cars.sort_values("price"),
        x="price",
        y="car_name",
        orientation="h",
        color="brand",
        title=f"초고가 차량 TOP {limit}",
        labels={"price": "가격(원)", "car_name": "차량"},
        hover_data=["model_year", "milage", "fuel_type", "transmission"],
    )


def brand_average_price(df: pd.DataFrame, limit: int = 15):
    brand_stats = (
        df.groupby("brand", as_index=False)
        .agg(avg_price=("price", "mean"), count=("price", "size"))
        .sort_values("avg_price", ascending=False)
        .head(limit)
    )
    return px.bar(
        brand_stats,
        x="brand",
        y="avg_price",
        color="count",
        title=f"평균 가격 상위 {limit}개 브랜드",
        labels={"brand": "브랜드", "avg_price": "평균 가격(원)", "count": "매물 수"},
    )


def year_average_price(df: pd.DataFrame):
    year_stats = df.groupby("model_year", as_index=False).agg(avg_price=("price", "mean"))
    return px.line(
        year_stats,
        x="model_year",
        y="avg_price",
        markers=True,
        title="연식별 평균 가격",
        labels={"model_year": "연식", "avg_price": "평균 가격(원)"},
    )


def mileage_price_scatter(df: pd.DataFrame):
    sample = df.sample(min(len(df), 3000), random_state=42) if len(df) > 3000 else df
    return px.scatter(
        sample,
        x="milage",
        y="price",
        color="accident_flag",
        hover_data=["brand", "model", "model_year", "fuel_type"],
        title="주행거리와 가격의 관계",
        labels={"milage": "주행거리(mi)", "price": "가격(원)", "accident_flag": "사고 이력"},
    )


def accident_price_box(df: pd.DataFrame):
    return px.box(
        df,
        x="accident_flag",
        y="price",
        color="accident_flag",
        title="사고 이력 여부별 가격 분포",
        labels={"accident_flag": "사고 이력", "price": "가격(원)"},
    )
