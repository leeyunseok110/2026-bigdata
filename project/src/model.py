import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


FEATURE_COLUMNS = [
    "brand",
    "model",
    "model_year",
    "milage",
    "fuel_type",
    "transmission",
    "accident_flag",
    "clean_title",
]

NUMERIC_FEATURES = ["model_year", "milage"]
CATEGORICAL_FEATURES = ["brand", "model", "fuel_type", "transmission", "accident_flag", "clean_title"]


def train_price_model(df: pd.DataFrame):
    model_df = df[FEATURE_COLUMNS + ["price"]].dropna().copy()
    price_limit = model_df["price"].quantile(0.99)
    original_rows = len(model_df)
    model_df = model_df[model_df["price"] <= price_limit].copy()
    x = model_df[FEATURE_COLUMNS]
    y = model_df["price"]

    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=0.2,
        random_state=42,
    )

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), NUMERIC_FEATURES),
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
        ]
    )

    regressor = RandomForestRegressor(
        n_estimators=250,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1,
    )

    pipeline = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            (
                "model",
                TransformedTargetRegressor(
                    regressor=regressor,
                    func=np.log1p,
                    inverse_func=np.expm1,
                ),
            ),
        ]
    )

    pipeline.fit(x_train, y_train)
    predictions = pipeline.predict(x_test)

    metrics = {
        "mae": mean_absolute_error(y_test, predictions),
        "r2": r2_score(y_test, predictions),
        "train_rows": len(x_train),
        "test_rows": len(x_test),
        "used_rows": len(model_df),
        "excluded_rows": original_rows - len(model_df),
        "price_limit": price_limit,
    }

    return pipeline, metrics


def predict_price(model, input_data: dict) -> float:
    prediction_df = pd.DataFrame([input_data], columns=FEATURE_COLUMNS)
    prediction = model.predict(prediction_df)[0]
    return max(float(prediction), 0.0)
