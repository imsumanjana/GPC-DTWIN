"""Predictive model comparison, persistence, and prediction utilities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from time import perf_counter
from typing import Any, Callable

import joblib
import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesRegressor, GradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import ElasticNet, LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold, KFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.svm import SVR

from gpc_dtwin import __version__
from gpc_dtwin.columns import COLUMN_LABELS, MODEL_NUMERIC_PREDICTORS


MODEL_FACTORIES: dict[str, Callable[[], Any]] = {
    "Linear Regression": lambda: LinearRegression(),
    "Ridge Regression": lambda: Ridge(alpha=1.0),
    "Elastic Net": lambda: ElasticNet(alpha=0.03, l1_ratio=0.35, max_iter=20000, random_state=42),
    "Support Vector Regression": lambda: SVR(kernel="rbf", C=25.0, epsilon=0.08, gamma="scale"),
    "Random Forest": lambda: RandomForestRegressor(
        n_estimators=180, min_samples_leaf=1, random_state=42, n_jobs=-1
    ),
    "Gradient Boosting": lambda: GradientBoostingRegressor(
        n_estimators=160, learning_rate=0.04, max_depth=2, random_state=42,
        loss="huber"
    ),
    "Extra Trees": lambda: ExtraTreesRegressor(
        n_estimators=180, min_samples_leaf=1, random_state=42, n_jobs=-1
    ),
}

REVIEW_STATES = {"REQUIRES_REVIEW", "CONFLICTING"}


@dataclass
class ModelComparisonResult:
    response: str
    predictors: tuple[str, ...]
    observations: int
    excluded_records: int
    cv_method: str
    rankings: pd.DataFrame
    predictions: pd.DataFrame
    best_algorithm: str
    best_metrics: dict[str, float]
    feature_influence: pd.DataFrame
    artifact: dict[str, Any]


class ModelingService:
    """Compare regression algorithms with leakage-aware cross-validation."""

    @staticmethod
    def algorithm_names() -> list[str]:
        return list(MODEL_FACTORIES)

    @staticmethod
    def _slug(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")

    @staticmethod
    def _prepare_working_data(
        dataframe: pd.DataFrame,
        response: str,
        predictors: list[str],
        include_review_records: bool,
        group_column: str,
    ) -> tuple[pd.DataFrame, int]:
        predictors = list(dict.fromkeys(predictors))
        required = [response, *predictors]
        missing = [column for column in required if column not in dataframe.columns]
        if missing:
            raise ValueError("Missing selected fields: " + ", ".join(missing))
        if not predictors:
            raise ValueError("Select at least one predictor.")

        extra = []
        for column in ("record_id", "mix_id", "data_status", group_column):
            if column in dataframe.columns and column not in required and column not in extra:
                extra.append(column)
        working = dataframe.loc[:, [*required, *extra]].copy()
        original_count = len(working)

        if "data_status" in working.columns:
            states = working["data_status"].astype("string").str.upper()
            keep = states.ne("EXCLUDED")
            if not include_review_records:
                keep &= ~states.isin(REVIEW_STATES)
            working = working.loc[keep].copy()

        working[response] = pd.to_numeric(working[response], errors="coerce")
        working = working.dropna(subset=[response])

        all_missing = []
        for predictor in predictors:
            if predictor in MODEL_NUMERIC_PREDICTORS:
                working[predictor] = pd.to_numeric(working[predictor], errors="coerce")
            if working[predictor].isna().all():
                all_missing.append(predictor)
        if all_missing:
            raise ValueError(
                "Selected predictors contain no usable values: " + ", ".join(all_missing)
            )
        if len(working) < 8:
            raise ValueError("At least eight usable response records are required.")

        return working, original_count - len(working)

    @staticmethod
    def _preprocessor(predictors: list[str]) -> tuple[ColumnTransformer, list[str], list[str]]:
        numeric = [column for column in predictors if column in MODEL_NUMERIC_PREDICTORS]
        categorical = [column for column in predictors if column not in numeric]
        transformers: list[tuple[str, Pipeline, list[str]]] = []
        if numeric:
            transformers.append((
                "numeric",
                Pipeline([
                    ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
                    ("scale", StandardScaler()),
                ]),
                numeric,
            ))
        if categorical:
            transformers.append((
                "categorical",
                Pipeline([
                    ("imputer", SimpleImputer(strategy="constant", fill_value="Missing")),
                    ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
                ]),
                categorical,
            ))
        return ColumnTransformer(transformers=transformers, remainder="drop"), numeric, categorical

    @staticmethod
    def _pipeline(predictors: list[str], algorithm: str) -> Pipeline:
        if algorithm not in MODEL_FACTORIES:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
        preprocessor, _, _ = ModelingService._preprocessor(predictors)
        return Pipeline([
            ("preprocess", preprocessor),
            ("model", MODEL_FACTORIES[algorithm]()),
        ])

    @staticmethod
    def _cross_validation(working: pd.DataFrame, group_column: str):
        if group_column in working.columns:
            groups = working[group_column].astype("string").fillna("Missing").to_numpy()
            unique_groups = len(np.unique(groups))
        else:
            groups = None
            unique_groups = 0
        if groups is not None and unique_groups >= 3:
            folds = min(5, unique_groups)
            return GroupKFold(n_splits=folds), groups, (
                f"Grouped {folds}-fold cross-validation by {COLUMN_LABELS.get(group_column, group_column)}"
            )
        folds = min(5, len(working))
        if folds < 2:
            raise ValueError("Insufficient observations for cross-validation.")
        return KFold(n_splits=folds, shuffle=True, random_state=42), None, f"{folds}-fold cross-validation"

    @staticmethod
    def _mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        valid = np.abs(y_true) > 1e-10
        if not np.any(valid):
            return float("nan")
        return float(np.mean(np.abs((y_true[valid] - y_pred[valid]) / y_true[valid])) * 100)

    @staticmethod
    def _defaults(working: pd.DataFrame, predictors: list[str]) -> tuple[dict[str, Any], dict[str, list[str]]]:
        defaults: dict[str, Any] = {}
        categories: dict[str, list[str]] = {}
        for column in predictors:
            if column in MODEL_NUMERIC_PREDICTORS:
                values = pd.to_numeric(working[column], errors="coerce")
                defaults[column] = None if values.dropna().empty else float(values.median())
            else:
                values = working[column].dropna().astype(str)
                defaults[column] = None if values.empty else str(values.mode().iloc[0])
                categories[column] = sorted(values.unique().tolist())
        return defaults, categories

    def compare_models(
        self,
        dataframe: pd.DataFrame,
        response: str,
        predictors: list[str],
        algorithms: list[str] | None = None,
        include_review_records: bool = False,
        group_column: str = "mix_id",
    ) -> ModelComparisonResult:
        predictors = list(dict.fromkeys(predictors))
        algorithms = list(dict.fromkeys(algorithms or self.algorithm_names()))
        if not algorithms:
            raise ValueError("Select at least one algorithm.")
        unsupported = [name for name in algorithms if name not in MODEL_FACTORIES]
        if unsupported:
            raise ValueError("Unsupported algorithms: " + ", ".join(unsupported))

        working, excluded_records = self._prepare_working_data(
            dataframe, response, predictors, include_review_records, group_column
        )
        x = working[predictors]
        y = working[response].to_numpy(dtype=float)
        cv, groups, cv_method = self._cross_validation(working, group_column)

        identity_columns = [column for column in ("record_id", "mix_id") if column in working.columns]
        prediction_table = working[identity_columns].copy().reset_index(drop=True)
        prediction_table["observed"] = y
        ranking_rows: list[dict[str, Any]] = []

        for algorithm in algorithms:
            pipeline = self._pipeline(predictors, algorithm)
            started = perf_counter()
            if groups is None:
                predicted = cross_val_predict(pipeline, x, y, cv=cv)
            else:
                predicted = cross_val_predict(pipeline, x, y, cv=cv, groups=groups)
            elapsed = perf_counter() - started
            rmse = float(np.sqrt(mean_squared_error(y, predicted)))
            mae = float(mean_absolute_error(y, predicted))
            r2 = float(r2_score(y, predicted))
            mape = self._mape(y, predicted)
            slug = self._slug(algorithm)
            prediction_table[f"{slug}_predicted"] = predicted
            prediction_table[f"{slug}_residual"] = y - predicted
            ranking_rows.append({
                "algorithm": algorithm,
                "rmse": rmse,
                "mae": mae,
                "r2": r2,
                "mape_percent": mape,
                "fit_seconds": float(elapsed),
            })

        rankings = pd.DataFrame(ranking_rows).sort_values(
            ["rmse", "mae", "algorithm"], ascending=[True, True, True]
        ).reset_index(drop=True)
        rankings.insert(0, "rank", np.arange(1, len(rankings) + 1))
        best_algorithm = str(rankings.iloc[0]["algorithm"])
        best_pipeline = self._pipeline(predictors, best_algorithm)
        best_pipeline.fit(x, y)

        influence = self._feature_influence(best_pipeline, x, y, predictors)
        defaults, categories = self._defaults(working, predictors)
        numeric_ranges = {}
        for column in predictors:
            if column in MODEL_NUMERIC_PREDICTORS:
                values = pd.to_numeric(working[column], errors="coerce").dropna()
                if not values.empty:
                    numeric_ranges[column] = [float(values.min()), float(values.max())]
        fingerprint_frame = working[[response, *predictors]].copy()
        fingerprint = hashlib.sha256(
            pd.util.hash_pandas_object(fingerprint_frame, index=True).values.tobytes()
        ).hexdigest()
        best_row = rankings.iloc[0]
        best_metrics = {
            "rmse": float(best_row["rmse"]),
            "mae": float(best_row["mae"]),
            "r2": float(best_row["r2"]),
            "mape_percent": float(best_row["mape_percent"]),
        }
        metadata = {
            "format_version": 1,
            "application_version": __version__,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "algorithm": best_algorithm,
            "response": response,
            "response_label": COLUMN_LABELS.get(response, response),
            "predictors": predictors,
            "numeric_predictors": [column for column in predictors if column in MODEL_NUMERIC_PREDICTORS],
            "categorical_predictors": [column for column in predictors if column not in MODEL_NUMERIC_PREDICTORS],
            "input_defaults": defaults,
            "input_categories": categories,
            "numeric_training_ranges": numeric_ranges,
            "data_fingerprint_sha256": fingerprint,
            "observations": len(working),
            "excluded_records": excluded_records,
            "include_review_records": bool(include_review_records),
            "cv_method": cv_method,
            "metrics": best_metrics,
        }
        artifact = {"pipeline": best_pipeline, "metadata": metadata}

        return ModelComparisonResult(
            response=response,
            predictors=tuple(predictors),
            observations=len(working),
            excluded_records=excluded_records,
            cv_method=cv_method,
            rankings=rankings,
            predictions=prediction_table,
            best_algorithm=best_algorithm,
            best_metrics=best_metrics,
            feature_influence=influence,
            artifact=artifact,
        )

    @staticmethod
    def _feature_influence(
        pipeline: Pipeline, x: pd.DataFrame, y: np.ndarray, predictors: list[str]
    ) -> pd.DataFrame:
        try:
            result = permutation_importance(
                pipeline,
                x,
                y,
                scoring="neg_root_mean_squared_error",
                n_repeats=10,
                random_state=42,
            )
            table = pd.DataFrame({
                "predictor": predictors,
                "importance_mean": result.importances_mean,
                "importance_std": result.importances_std,
            })
            table["predictor_label"] = table["predictor"].map(
                lambda value: COLUMN_LABELS.get(value, value)
            )
            return table.sort_values("importance_mean", ascending=False).reset_index(drop=True)
        except Exception:
            return pd.DataFrame(columns=[
                "predictor", "importance_mean", "importance_std", "predictor_label"
            ])

    @staticmethod
    def comparison_figure(result: ModelComparisonResult) -> Figure:
        figure = Figure(figsize=(8.5, 5.4), constrained_layout=True)
        axis = figure.add_subplot(111)
        table = result.rankings.sort_values("rmse", ascending=True)
        positions = np.arange(len(table))
        width = 0.36
        axis.barh(positions - width / 2, table["rmse"], height=width, label="RMSE")
        axis.barh(positions + width / 2, table["mae"], height=width, label="MAE")
        axis.set_yticks(positions, table["algorithm"])
        axis.set_xlabel(COLUMN_LABELS.get(result.response, result.response))
        axis.grid(True, axis="x", alpha=0.25)
        axis.legend()
        return figure

    @staticmethod
    def diagnostics_figure(result: ModelComparisonResult, algorithm: str | None = None) -> Figure:
        algorithm = algorithm or result.best_algorithm
        slug = ModelingService._slug(algorithm)
        predicted_column = f"{slug}_predicted"
        residual_column = f"{slug}_residual"
        if predicted_column not in result.predictions.columns:
            raise ValueError("Predictions for the selected algorithm are unavailable.")
        observed = result.predictions["observed"].astype(float)
        predicted = result.predictions[predicted_column].astype(float)
        residual = result.predictions[residual_column].astype(float)

        figure = Figure(figsize=(9, 4.8), constrained_layout=True)
        fit_axis = figure.add_subplot(121)
        residual_axis = figure.add_subplot(122)
        fit_axis.scatter(observed, predicted)
        minimum = min(float(observed.min()), float(predicted.min()))
        maximum = max(float(observed.max()), float(predicted.max()))
        fit_axis.plot([minimum, maximum], [minimum, maximum], linestyle="--", linewidth=1)
        fit_axis.set_xlabel("Observed")
        fit_axis.set_ylabel("Cross-validated prediction")
        fit_axis.set_title(algorithm)
        fit_axis.grid(True, alpha=0.25)

        residual_axis.scatter(predicted, residual)
        residual_axis.axhline(0, linestyle="--", linewidth=1)
        residual_axis.set_xlabel("Cross-validated prediction")
        residual_axis.set_ylabel("Residual")
        residual_axis.set_title("Residual pattern")
        residual_axis.grid(True, alpha=0.25)
        return figure

    @staticmethod
    def influence_figure(result: ModelComparisonResult) -> Figure:
        figure = Figure(figsize=(8.2, 5.2), constrained_layout=True)
        axis = figure.add_subplot(111)
        table = result.feature_influence.sort_values("importance_mean", ascending=True)
        if table.empty:
            axis.text(0.5, 0.5, "Feature influence is unavailable", ha="center", va="center")
            axis.set_axis_off()
            return figure
        axis.barh(table["predictor_label"], table["importance_mean"], xerr=table["importance_std"])
        axis.set_xlabel("Permutation importance (RMSE increase)")
        axis.grid(True, axis="x", alpha=0.25)
        return figure

    @staticmethod
    def predict_dataframe(artifact: dict[str, Any], dataframe: pd.DataFrame) -> pd.DataFrame:
        ModelingService._validate_artifact(artifact)
        metadata = artifact["metadata"]
        predictors = list(metadata["predictors"])
        missing = [column for column in predictors if column not in dataframe.columns]
        if missing:
            raise ValueError("Prediction data are missing fields: " + ", ".join(missing))
        x = dataframe[predictors].copy()
        for column in metadata.get("numeric_predictors", []):
            x[column] = pd.to_numeric(x[column], errors="coerce")
        predicted = artifact["pipeline"].predict(x)
        result = pd.DataFrame(index=dataframe.index)
        for column in ("record_id", "mix_id"):
            if column in dataframe.columns:
                result[column] = dataframe[column].values
        result["predicted_response"] = predicted
        result["prediction_input_missing_count"] = x.isna().sum(axis=1).to_numpy()
        result["input_completeness_percent"] = (
            (len(predictors) - x.isna().sum(axis=1)) / max(len(predictors), 1) * 100
        ).to_numpy()
        ranges = metadata.get("numeric_training_ranges", {})
        outside_counts = []
        outside_fields = []
        for _, row in x.iterrows():
            fields = []
            for column, limits in ranges.items():
                value = pd.to_numeric(pd.Series([row.get(column)]), errors="coerce").iloc[0]
                if pd.notna(value) and (float(value) < float(limits[0]) or float(value) > float(limits[1])):
                    fields.append(column)
            outside_counts.append(len(fields))
            outside_fields.append(", ".join(fields))
        result["outside_training_range_count"] = outside_counts
        result["outside_training_range_fields"] = outside_fields
        response = metadata["response"]
        if response in dataframe.columns:
            observed = pd.to_numeric(dataframe[response], errors="coerce")
            result["observed_response"] = observed.to_numpy()
            result["residual"] = observed.to_numpy() - predicted
        return result.reset_index(drop=True)

    @staticmethod
    def predict_scenario(artifact: dict[str, Any], values: dict[str, Any]) -> float:
        ModelingService._validate_artifact(artifact)
        predictors = list(artifact["metadata"]["predictors"])
        frame = pd.DataFrame([{column: values.get(column) for column in predictors}])
        return float(artifact["pipeline"].predict(frame)[0])

    @staticmethod
    def _validate_artifact(artifact: dict[str, Any]) -> None:
        if not isinstance(artifact, dict) or "pipeline" not in artifact or "metadata" not in artifact:
            raise ValueError("The selected model file is not compatible.")
        metadata = artifact["metadata"]
        required = {"algorithm", "response", "predictors", "metrics", "created_at_utc"}
        if not required.issubset(metadata):
            raise ValueError("The selected model metadata are incomplete.")

    @staticmethod
    def save_artifact(artifact: dict[str, Any], directory: Path | str) -> Path:
        ModelingService._validate_artifact(artifact)
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        metadata = artifact["metadata"]
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        stem = "__".join([
            ModelingService._slug(str(metadata["response"])),
            ModelingService._slug(str(metadata["algorithm"])),
            timestamp,
        ])
        model_path = directory / f"{stem}.joblib"
        metadata_path = directory / f"{stem}.json"
        joblib.dump(artifact, model_path)
        metadata_copy = dict(metadata)
        metadata_copy["artifact_file"] = model_path.name
        metadata_path.write_text(
            json.dumps(metadata_copy, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return model_path

    @staticmethod
    def load_artifact(path: Path | str) -> dict[str, Any]:
        artifact = joblib.load(Path(path))
        ModelingService._validate_artifact(artifact)
        return artifact

    @staticmethod
    def list_saved_models(directory: Path | str) -> pd.DataFrame:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        rows: list[dict[str, Any]] = []
        for metadata_path in sorted(directory.glob("*.json"), reverse=True):
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                artifact_name = metadata.get("artifact_file", metadata_path.with_suffix(".joblib").name)
                artifact_path = directory / artifact_name
                if not artifact_path.exists():
                    continue
                metrics = metadata.get("metrics", {})
                rows.append({
                    "created_at_utc": metadata.get("created_at_utc", ""),
                    "algorithm": metadata.get("algorithm", ""),
                    "response": metadata.get("response", ""),
                    "observations": metadata.get("observations", ""),
                    "rmse": metrics.get("rmse", np.nan),
                    "mae": metrics.get("mae", np.nan),
                    "r2": metrics.get("r2", np.nan),
                    "artifact_path": str(artifact_path),
                })
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
        return pd.DataFrame(rows)

    @staticmethod
    def delete_artifact(path: Path | str) -> None:
        model_path = Path(path)
        metadata_path = model_path.with_suffix(".json")
        if model_path.exists():
            model_path.unlink()
        if metadata_path.exists():
            metadata_path.unlink()
