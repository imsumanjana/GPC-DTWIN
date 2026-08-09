"""Shared regression-model registry used by predictive modelling and the digital twin."""

from __future__ import annotations

from typing import Any, Callable

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesRegressor, GradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import ElasticNet, LinearRegression, Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.svm import SVR

from gpc_dtwin.columns import MODEL_NUMERIC_PREDICTORS


MODEL_FACTORIES: dict[str, Callable[[], Any]] = {
    "Linear Regression": lambda: LinearRegression(),
    "Ridge Regression": lambda: Ridge(alpha=1.0),
    "Elastic Net": lambda: ElasticNet(
        alpha=0.03, l1_ratio=0.35, max_iter=20000, random_state=42
    ),
    "Support Vector Regression": lambda: SVR(
        kernel="rbf", C=25.0, epsilon=0.08, gamma="scale"
    ),
    "Random Forest": lambda: RandomForestRegressor(
        n_estimators=180, min_samples_leaf=1, random_state=42, n_jobs=1
    ),
    "Gradient Boosting": lambda: GradientBoostingRegressor(
        n_estimators=160,
        learning_rate=0.04,
        max_depth=2,
        random_state=42,
        loss="huber",
    ),
    "Extra Trees": lambda: ExtraTreesRegressor(
        n_estimators=180, min_samples_leaf=1, random_state=42, n_jobs=1
    ),
}


def algorithm_names() -> list[str]:
    return list(MODEL_FACTORIES)


def build_estimator(algorithm: str) -> Any:
    try:
        return MODEL_FACTORIES[algorithm]()
    except KeyError as error:
        raise ValueError(f"Unsupported algorithm: {algorithm}") from error


def build_preprocessor(
    predictors: list[str],
) -> tuple[ColumnTransformer, list[str], list[str]]:
    """Build the canonical predictor transformation used throughout GPC-DTwin."""
    numeric = [column for column in predictors if column in MODEL_NUMERIC_PREDICTORS]
    categorical = [column for column in predictors if column not in numeric]
    transformers: list[tuple[str, Pipeline, list[str]]] = []
    if numeric:
        transformers.append(
            (
                "numeric",
                Pipeline(
                    [
                        (
                            "imputer",
                            SimpleImputer(strategy="median", keep_empty_features=True),
                        ),
                        ("scale", StandardScaler()),
                    ]
                ),
                numeric,
            )
        )
    if categorical:
        transformers.append(
            (
                "categorical",
                Pipeline(
                    [
                        (
                            "imputer",
                            SimpleImputer(strategy="constant", fill_value="Missing"),
                        ),
                        (
                            "onehot",
                            OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                        ),
                    ]
                ),
                categorical,
            )
        )
    return ColumnTransformer(transformers=transformers, remainder="drop"), numeric, categorical


def build_pipeline(predictors: list[str], algorithm: str) -> Pipeline:
    preprocessor, _, _ = build_preprocessor(predictors)
    return Pipeline(
        [
            ("preprocess", preprocessor),
            ("model", build_estimator(algorithm)),
        ]
    )
