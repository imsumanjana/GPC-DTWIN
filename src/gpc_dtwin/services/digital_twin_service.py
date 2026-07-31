"""Uncertainty-aware digital twin modeling, calibration, and response maps."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any
import warnings

import joblib
import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from scipy.stats import norm
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.exceptions import ConvergenceWarning
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, Matern, WhiteKernel
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold, KFold
from sklearn.neighbors import NearestNeighbors
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from gpc_dtwin import __version__
from gpc_dtwin.chart_style import apply_chart_style
from gpc_dtwin.columns import COLUMN_LABELS, MODEL_NUMERIC_PREDICTORS


TWIN_METHODS = ("Gaussian Process", "Forest Ensemble")
REVIEW_STATES = {"REQUIRES_REVIEW", "CONFLICTING"}


@dataclass
class TwinBuildResult:
    response: str
    predictors: tuple[str, ...]
    method: str
    confidence_percent: float
    observations: int
    excluded_records: int
    cv_method: str
    metrics: dict[str, float]
    calibration: pd.DataFrame
    artifact: dict[str, Any]


class DigitalTwinService:
    """Build calibrated surrogate models with prediction intervals and domain checks."""

    @staticmethod
    def method_names() -> list[str]:
        return list(TWIN_METHODS)

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
        if not predictors:
            raise ValueError("Select at least one predictor.")
        if response in predictors:
            predictors.remove(response)
        required = [response, *predictors]
        missing = [column for column in required if column not in dataframe.columns]
        if missing:
            raise ValueError("Missing selected fields: " + ", ".join(missing))

        extra: list[str] = []
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
        unusable: list[str] = []
        for predictor in predictors:
            if predictor in MODEL_NUMERIC_PREDICTORS:
                working[predictor] = pd.to_numeric(working[predictor], errors="coerce")
            if working[predictor].isna().all():
                unusable.append(predictor)
        if unusable:
            raise ValueError("Selected predictors contain no usable values: " + ", ".join(unusable))
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
    def _cross_validation(working: pd.DataFrame, group_column: str):
        if group_column in working.columns:
            groups = working[group_column].astype("string").fillna("Missing").to_numpy()
            unique_groups = len(np.unique(groups))
        else:
            groups = None
            unique_groups = 0
        if groups is not None and unique_groups >= 3:
            folds = min(5, unique_groups)
            splitter = GroupKFold(n_splits=folds)
            return list(splitter.split(working, groups=groups)), (
                f"Grouped {folds}-fold cross-validation by "
                f"{COLUMN_LABELS.get(group_column, group_column)}"
            )
        folds = min(5, len(working))
        if folds < 2:
            raise ValueError("Insufficient observations for cross-validation.")
        splitter = KFold(n_splits=folds, shuffle=True, random_state=42)
        return list(splitter.split(working)), f"{folds}-fold cross-validation"

    @staticmethod
    def _build_model(method: str, feature_count: int, response_variance: float):
        if method == "Gaussian Process":
            length_scale = np.ones(max(feature_count, 1), dtype=float)
            noise = max(response_variance * 0.01, 1e-6)
            kernel = (
                ConstantKernel(1.0, (1e-2, 1e3))
                * Matern(length_scale=length_scale, length_scale_bounds=(1e-2, 1e3), nu=1.5)
                + WhiteKernel(noise_level=noise, noise_level_bounds=(1e-8, max(response_variance * 10, 1e-4)))
            )
            return GaussianProcessRegressor(
                kernel=kernel,
                alpha=1e-8,
                normalize_y=True,
                n_restarts_optimizer=1,
                random_state=42,
            )
        if method == "Forest Ensemble":
            return RandomForestRegressor(
                n_estimators=260,
                min_samples_leaf=1,
                max_features=0.85,
                bootstrap=True,
                random_state=42,
                n_jobs=1,
            )
        raise ValueError(f"Unsupported twin method: {method}")

    @classmethod
    def _fit_components(
        cls, x: pd.DataFrame, y: np.ndarray, predictors: list[str], method: str
    ) -> tuple[ColumnTransformer, Any, np.ndarray]:
        preprocessor, _, _ = cls._preprocessor(predictors)
        transformed = np.asarray(preprocessor.fit_transform(x), dtype=float)
        model = cls._build_model(method, transformed.shape[1], float(np.var(y)))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ConvergenceWarning)
            model.fit(transformed, y)
        return preprocessor, model, transformed

    @staticmethod
    def _predict_transformed(
        method: str, model: Any, transformed: np.ndarray, confidence_percent: float
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        confidence = float(confidence_percent) / 100.0
        alpha = 1.0 - confidence
        if not 0.5 < confidence < 1.0:
            raise ValueError("Confidence level must be between 50 and 100 percent.")
        if method == "Gaussian Process":
            mean, std = model.predict(transformed, return_std=True)
            z_value = float(norm.ppf(1.0 - alpha / 2.0))
            lower = mean - z_value * std
            upper = mean + z_value * std
            return np.asarray(mean), np.asarray(std), np.asarray(lower), np.asarray(upper)
        if method == "Forest Ensemble":
            tree_predictions = np.vstack([tree.predict(transformed) for tree in model.estimators_])
            mean = tree_predictions.mean(axis=0)
            std = tree_predictions.std(axis=0, ddof=1)
            lower = np.quantile(tree_predictions, alpha / 2.0, axis=0)
            upper = np.quantile(tree_predictions, 1.0 - alpha / 2.0, axis=0)
            return mean, std, lower, upper
        raise ValueError(f"Unsupported twin method: {method}")

    @staticmethod
    def _defaults(
        working: pd.DataFrame, predictors: list[str]
    ) -> tuple[dict[str, Any], dict[str, list[str]], dict[str, list[float]]]:
        defaults: dict[str, Any] = {}
        categories: dict[str, list[str]] = {}
        numeric_ranges: dict[str, list[float]] = {}
        for column in predictors:
            if column in MODEL_NUMERIC_PREDICTORS:
                values = pd.to_numeric(working[column], errors="coerce").dropna()
                if values.empty:
                    defaults[column] = None
                else:
                    defaults[column] = float(values.median())
                    numeric_ranges[column] = [float(values.min()), float(values.max())]
            else:
                values = working[column].dropna().astype(str)
                defaults[column] = None if values.empty else str(values.mode().iloc[0])
                categories[column] = sorted(values.unique().tolist())
        return defaults, categories, numeric_ranges

    @staticmethod
    def _distance_quantiles(training_transformed: np.ndarray) -> dict[str, float]:
        if len(training_transformed) < 2:
            return {"q50": 0.0, "q90": 0.0, "q99": 0.0}
        neighbors = NearestNeighbors(n_neighbors=2).fit(training_transformed)
        distances, _ = neighbors.kneighbors(training_transformed)
        nearest_other = distances[:, 1]
        return {
            "q50": float(np.quantile(nearest_other, 0.50)),
            "q90": float(np.quantile(nearest_other, 0.90)),
            "q99": float(np.quantile(nearest_other, 0.99)),
        }

    def build_twin(
        self,
        dataframe: pd.DataFrame,
        response: str,
        predictors: list[str],
        method: str = "Gaussian Process",
        confidence_percent: float = 95.0,
        include_review_records: bool = False,
        group_column: str = "mix_id",
    ) -> TwinBuildResult:
        predictors = [column for column in dict.fromkeys(predictors) if column != response]
        if method not in TWIN_METHODS:
            raise ValueError(f"Unsupported twin method: {method}")
        working, excluded_records = self._prepare_working_data(
            dataframe, response, predictors, include_review_records, group_column
        )
        x = working[predictors].copy()
        y = working[response].to_numpy(dtype=float)
        splits, cv_method = self._cross_validation(working, group_column)

        cv_mean = np.full(len(working), np.nan, dtype=float)
        cv_std = np.full(len(working), np.nan, dtype=float)
        cv_lower = np.full(len(working), np.nan, dtype=float)
        cv_upper = np.full(len(working), np.nan, dtype=float)

        for train_index, test_index in splits:
            preprocessor, model, _ = self._fit_components(
                x.iloc[train_index], y[train_index], predictors, method
            )
            transformed_test = np.asarray(preprocessor.transform(x.iloc[test_index]), dtype=float)
            mean, std, lower, upper = self._predict_transformed(
                method, model, transformed_test, confidence_percent
            )
            cv_mean[test_index] = mean
            cv_std[test_index] = std
            cv_lower[test_index] = lower
            cv_upper[test_index] = upper

        residual = y - cv_mean
        inside = (y >= cv_lower) & (y <= cv_upper)
        interval_width = cv_upper - cv_lower
        rmse = float(np.sqrt(mean_squared_error(y, cv_mean)))
        mae = float(mean_absolute_error(y, cv_mean))
        r2 = float(r2_score(y, cv_mean))
        coverage = float(np.mean(inside) * 100.0)
        mean_width = float(np.mean(interval_width))
        response_span = max(float(np.max(y) - np.min(y)), 1e-9)
        normalized_rmse = float(rmse / response_span * 100.0)
        calibration_gap = float(abs(coverage - confidence_percent))

        identity_columns = [column for column in ("record_id", "mix_id") if column in working.columns]
        calibration = working[identity_columns].copy().reset_index(drop=True)
        calibration["observed_response"] = y
        calibration["predicted_mean"] = cv_mean
        calibration["prediction_std"] = cv_std
        calibration["lower_bound"] = cv_lower
        calibration["upper_bound"] = cv_upper
        calibration["interval_width"] = interval_width
        calibration["residual"] = residual
        calibration["within_interval"] = inside

        preprocessor, model, transformed_training = self._fit_components(x, y, predictors, method)
        defaults, categories, numeric_ranges = self._defaults(working, predictors)
        distance_quantiles = self._distance_quantiles(transformed_training)
        fingerprint_frame = working[[response, *predictors]].copy()
        fingerprint = hashlib.sha256(
            pd.util.hash_pandas_object(fingerprint_frame, index=True).values.tobytes()
        ).hexdigest()
        metrics = {
            "rmse": rmse,
            "mae": mae,
            "r2": r2,
            "coverage_percent": coverage,
            "mean_interval_width": mean_width,
            "normalized_rmse_percent": normalized_rmse,
            "calibration_gap_percent": calibration_gap,
        }
        metadata = {
            "format_version": 1,
            "artifact_type": "uncertainty_aware_twin",
            "application_version": __version__,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "method": method,
            "response": response,
            "response_label": COLUMN_LABELS.get(response, response),
            "predictors": predictors,
            "numeric_predictors": [c for c in predictors if c in MODEL_NUMERIC_PREDICTORS],
            "categorical_predictors": [c for c in predictors if c not in MODEL_NUMERIC_PREDICTORS],
            "confidence_percent": float(confidence_percent),
            "input_defaults": defaults,
            "input_categories": categories,
            "numeric_training_ranges": numeric_ranges,
            "response_training_range": [float(np.min(y)), float(np.max(y))],
            "training_distance_quantiles": distance_quantiles,
            "data_fingerprint_sha256": fingerprint,
            "observations": len(working),
            "excluded_records": excluded_records,
            "include_review_records": bool(include_review_records),
            "cv_method": cv_method,
            "metrics": metrics,
        }
        artifact = {
            "preprocessor": preprocessor,
            "model": model,
            "training_transformed": transformed_training,
            "metadata": metadata,
        }
        return TwinBuildResult(
            response=response,
            predictors=tuple(predictors),
            method=method,
            confidence_percent=float(confidence_percent),
            observations=len(working),
            excluded_records=excluded_records,
            cv_method=cv_method,
            metrics=metrics,
            calibration=calibration,
            artifact=artifact,
        )

    @staticmethod
    def _validate_artifact(artifact: dict[str, Any]) -> None:
        if not isinstance(artifact, dict):
            raise ValueError("The selected twin file is not compatible.")
        required_top = {"preprocessor", "model", "training_transformed", "metadata"}
        if not required_top.issubset(artifact):
            raise ValueError("The selected twin file is incomplete.")
        metadata = artifact["metadata"]
        required_meta = {
            "method", "response", "predictors", "metrics", "created_at_utc",
            "confidence_percent", "numeric_training_ranges",
        }
        if not required_meta.issubset(metadata):
            raise ValueError("The selected twin metadata are incomplete.")

    @staticmethod
    def _prepare_prediction_frame(artifact: dict[str, Any], dataframe: pd.DataFrame) -> pd.DataFrame:
        DigitalTwinService._validate_artifact(artifact)
        metadata = artifact["metadata"]
        predictors = list(metadata["predictors"])
        missing = [column for column in predictors if column not in dataframe.columns]
        if missing:
            raise ValueError("Prediction data are missing fields: " + ", ".join(missing))
        frame = dataframe[predictors].copy()
        for column in metadata.get("numeric_predictors", []):
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        return frame

    @staticmethod
    def _range_violations(
        metadata: dict[str, Any], frame: pd.DataFrame
    ) -> tuple[list[int], list[str]]:
        counts: list[int] = []
        descriptions: list[str] = []
        ranges = metadata.get("numeric_training_ranges", {})
        for _, row in frame.iterrows():
            fields: list[str] = []
            for column, limits in ranges.items():
                value = pd.to_numeric(pd.Series([row.get(column)]), errors="coerce").iloc[0]
                if pd.notna(value) and (
                    float(value) < float(limits[0]) or float(value) > float(limits[1])
                ):
                    fields.append(column)
            counts.append(len(fields))
            descriptions.append(", ".join(fields))
        return counts, descriptions

    @staticmethod
    def _reliability(
        metadata: dict[str, Any], std: np.ndarray, distances: np.ndarray, outside_counts: list[int]
    ) -> tuple[list[str], list[str], np.ndarray]:
        response_range = metadata.get("response_training_range", [0.0, 1.0])
        response_span = max(float(response_range[1]) - float(response_range[0]), 1e-9)
        normalized = np.asarray(std, dtype=float) / response_span * 100.0
        quantiles = metadata.get("training_distance_quantiles", {})
        q50 = max(float(quantiles.get("q50", 0.0)), 1e-9)
        q90 = max(float(quantiles.get("q90", q50)), q50)
        q99 = max(float(quantiles.get("q99", q90)), q90)
        classes: list[str] = []
        reasons: list[str] = []
        for value, distance, outside in zip(normalized, distances, outside_counts):
            if outside > 0:
                grade = "D"
                reason = "One or more inputs are outside the fitted range."
            elif distance > q99 * 1.25 or value > 30.0:
                grade = "D"
                reason = "The scenario is remote from available observations or has high uncertainty."
            elif distance > q90 or value > 20.0:
                grade = "C"
                reason = "The scenario has limited nearby support."
            elif distance > q50 or value > 10.0:
                grade = "B"
                reason = "The scenario is supported with moderate uncertainty."
            else:
                grade = "A"
                reason = "The scenario is close to available observations with low uncertainty."
            classes.append(grade)
            reasons.append(reason)
        return classes, reasons, normalized

    @classmethod
    def predict_dataframe(cls, artifact: dict[str, Any], dataframe: pd.DataFrame) -> pd.DataFrame:
        frame = cls._prepare_prediction_frame(artifact, dataframe)
        metadata = artifact["metadata"]
        transformed = np.asarray(artifact["preprocessor"].transform(frame), dtype=float)
        mean, std, lower, upper = cls._predict_transformed(
            metadata["method"], artifact["model"], transformed, metadata["confidence_percent"]
        )
        nearest = NearestNeighbors(n_neighbors=1).fit(np.asarray(artifact["training_transformed"]))
        distances, _ = nearest.kneighbors(transformed)
        nearest_distance = distances[:, 0]
        outside_counts, outside_fields = cls._range_violations(metadata, frame)
        classes, reasons, normalized = cls._reliability(
            metadata, std, nearest_distance, outside_counts
        )

        result = pd.DataFrame(index=dataframe.index)
        for column in ("record_id", "mix_id"):
            if column in dataframe.columns:
                result[column] = dataframe[column].values
        result["predicted_mean"] = mean
        result["prediction_std"] = std
        result["lower_bound"] = lower
        result["upper_bound"] = upper
        result["interval_width"] = upper - lower
        result["normalized_uncertainty_percent"] = normalized
        result["nearest_training_distance"] = nearest_distance
        result["outside_training_range_count"] = outside_counts
        result["outside_training_range_fields"] = outside_fields
        result["reliability_class"] = classes
        result["reliability_reason"] = reasons
        result["prediction_input_missing_count"] = frame.isna().sum(axis=1).to_numpy()
        result["input_completeness_percent"] = (
            (len(frame.columns) - frame.isna().sum(axis=1)) / max(len(frame.columns), 1) * 100.0
        ).to_numpy()
        response = metadata["response"]
        if response in dataframe.columns:
            observed = pd.to_numeric(dataframe[response], errors="coerce")
            result["observed_response"] = observed.to_numpy()
            result["residual"] = observed.to_numpy() - mean
            result["within_interval"] = (
                (observed.to_numpy() >= lower) & (observed.to_numpy() <= upper)
            )
        return result.reset_index(drop=True)

    @classmethod
    def predict_scenario(cls, artifact: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
        cls._validate_artifact(artifact)
        predictors = list(artifact["metadata"]["predictors"])
        frame = pd.DataFrame([{column: values.get(column) for column in predictors}])
        row = cls.predict_dataframe(artifact, frame).iloc[0]
        return row.to_dict()

    @staticmethod
    def map_axis_candidates(artifact: dict[str, Any]) -> list[str]:
        """Return numeric predictors with a finite, non-zero fitted range."""
        DigitalTwinService._validate_artifact(artifact)
        metadata = artifact["metadata"]
        ranges = metadata.get("numeric_training_ranges", {})
        candidates: list[str] = []
        for column in metadata.get("predictors", []):
            limits = ranges.get(column)
            if not isinstance(limits, (list, tuple)) or len(limits) != 2:
                continue
            low, high = float(limits[0]), float(limits[1])
            if np.isfinite(low) and np.isfinite(high) and high - low > 1e-12:
                candidates.append(column)
        return candidates

    @classmethod
    def response_map(
        cls,
        artifact: dict[str, Any],
        x_field: str,
        y_field: str,
        resolution: int = 45,
    ) -> pd.DataFrame:
        cls._validate_artifact(artifact)
        metadata = artifact["metadata"]
        predictors = list(metadata["predictors"])
        numeric_ranges = metadata.get("numeric_training_ranges", {})
        candidates = cls.map_axis_candidates(artifact)
        if x_field == y_field:
            raise ValueError("Select two different response-map axes.")
        if x_field not in predictors or y_field not in predictors:
            raise ValueError("Both response-map axes must be predictors used by the active twin.")
        if x_field not in numeric_ranges or y_field not in numeric_ranges:
            raise ValueError("Response maps require numeric predictors with fitted ranges.")
        if x_field not in candidates or y_field not in candidates:
            raise ValueError(
                "The selected variables do not span a usable two-dimensional range. "
                "Choose predictors that vary in the fitted data, or use a one-dimensional response curve."
            )
        resolution = int(np.clip(resolution, 15, 100))
        x_low, x_high = map(float, numeric_ranges[x_field])
        y_low, y_high = map(float, numeric_ranges[y_field])
        x_values = np.linspace(x_low, x_high, resolution, dtype=float)
        y_values = np.linspace(y_low, y_high, resolution, dtype=float)
        grid_x, grid_y = np.meshgrid(x_values, y_values, indexing="xy")
        defaults = metadata.get("input_defaults", {})
        rows: list[dict[str, Any]] = []
        for row_index in range(resolution):
            for column_index in range(resolution):
                row = {column: defaults.get(column) for column in predictors}
                row[x_field] = float(grid_x[row_index, column_index])
                row[y_field] = float(grid_y[row_index, column_index])
                rows.append(row)
        frame = pd.DataFrame(rows, columns=predictors)
        predictions = cls.predict_dataframe(artifact, frame)
        # Explicit grid coordinates prevent reconstruction from unique values and
        # therefore avoid shape failures when a field is nearly constant.
        predictions.insert(0, "grid_column", np.tile(np.arange(resolution), resolution))
        predictions.insert(0, "grid_row", np.repeat(np.arange(resolution), resolution))
        predictions.insert(0, y_field, grid_y.ravel(order="C"))
        predictions.insert(0, x_field, grid_x.ravel(order="C"))
        predictions.attrs["grid_shape"] = (resolution, resolution)
        predictions.attrs["x_field"] = x_field
        predictions.attrs["y_field"] = y_field
        return predictions

    @classmethod
    def response_curve(
        cls,
        artifact: dict[str, Any],
        field: str,
        resolution: int = 100,
    ) -> pd.DataFrame:
        """Generate a one-dimensional response curve for one varying predictor."""
        cls._validate_artifact(artifact)
        metadata = artifact["metadata"]
        if field not in cls.map_axis_candidates(artifact):
            raise ValueError("The selected predictor does not have a usable fitted range.")
        resolution = int(np.clip(resolution, 15, 200))
        low, high = map(float, metadata["numeric_training_ranges"][field])
        values = np.linspace(low, high, resolution, dtype=float)
        defaults = metadata.get("input_defaults", {})
        predictors = list(metadata["predictors"])
        frame = pd.DataFrame([
            {**{column: defaults.get(column) for column in predictors}, field: float(value)}
            for value in values
        ], columns=predictors)
        predictions = cls.predict_dataframe(artifact, frame)
        predictions.insert(0, field, values)
        predictions.attrs["curve_field"] = field
        return predictions

    @staticmethod
    def _single_figure(title: str) -> tuple[Figure, Any]:
        figure = Figure(figsize=(6.0, 6.0), constrained_layout=True)
        axis = figure.add_subplot(111)
        axis.set_title(title)
        return figure, axis

    @classmethod
    def calibration_figures(cls, result: TwinBuildResult) -> dict[str, Figure]:
        table = result.calibration
        observed = table["observed_response"].to_numpy(dtype=float)
        predicted = table["predicted_mean"].to_numpy(dtype=float)
        lower = table["lower_bound"].to_numpy(dtype=float)
        upper = table["upper_bound"].to_numpy(dtype=float)
        residual = table["residual"].to_numpy(dtype=float)
        std = table["prediction_std"].to_numpy(dtype=float)

        interval_figure, fit_axis = cls._single_figure("Prediction intervals")
        yerr = np.vstack([predicted - lower, upper - predicted])
        fit_axis.errorbar(
            observed, predicted, yerr=yerr, fmt="o", alpha=0.75, capsize=2,
            label="Cross-validated estimate ± interval",
        )
        minimum = min(float(observed.min()), float(lower.min()))
        maximum = max(float(observed.max()), float(upper.max()))
        fit_axis.plot(
            [minimum, maximum], [minimum, maximum], linestyle="--", linewidth=1,
            label="Ideal agreement",
        )
        fit_axis.set_xlabel("Observed")
        fit_axis.set_ylabel("Cross-validated estimate")

        error_figure, residual_axis = cls._single_figure("Error and uncertainty")
        residual_axis.scatter(std, np.abs(residual), label="Absolute error")
        residual_axis.set_xlabel("Estimated uncertainty")
        residual_axis.set_ylabel("Absolute error")

        coverage_figure, calibration_axis = cls._single_figure(
            f"Coverage {result.metrics['coverage_percent']:.1f}%"
        )
        standardized = np.divide(
            residual, std, out=np.zeros_like(residual, dtype=float), where=np.asarray(std) > 1e-12,
        )
        calibration_axis.hist(
            standardized, bins=min(10, max(4, len(standardized) // 2)),
            label="Standardized residuals",
        )
        calibration_axis.axvline(0, linestyle="--", linewidth=1, label="Zero residual")
        calibration_axis.set_xlabel("Standardized residual")
        calibration_axis.set_ylabel("Count")

        figures = {
            "Prediction intervals": interval_figure,
            "Error & uncertainty": error_figure,
            "Coverage": coverage_figure,
        }
        for figure in figures.values():
            apply_chart_style(figure)
        return figures

    @classmethod
    def calibration_figure(cls, result: TwinBuildResult) -> Figure:
        """Backward-compatible combined calibration figure."""
        figures = cls.calibration_figures(result)
        table = result.calibration
        figure = Figure(figsize=(10.5, 4.8), constrained_layout=True)
        observed = table["observed_response"].to_numpy(dtype=float)
        predicted = table["predicted_mean"].to_numpy(dtype=float)
        lower = table["lower_bound"].to_numpy(dtype=float)
        upper = table["upper_bound"].to_numpy(dtype=float)
        residual = table["residual"].to_numpy(dtype=float)
        std = table["prediction_std"].to_numpy(dtype=float)
        fit_axis, residual_axis, calibration_axis = (
            figure.add_subplot(131), figure.add_subplot(132), figure.add_subplot(133)
        )
        yerr = np.vstack([predicted - lower, upper - predicted])
        fit_axis.errorbar(observed, predicted, yerr=yerr, fmt="o", alpha=0.75, capsize=2,
                          label="Estimate ± interval")
        minimum = min(float(observed.min()), float(lower.min()))
        maximum = max(float(observed.max()), float(upper.max()))
        fit_axis.plot([minimum, maximum], [minimum, maximum], linestyle="--", linewidth=1,
                      label="Ideal agreement")
        fit_axis.set_xlabel("Observed"); fit_axis.set_ylabel("Cross-validated estimate")
        fit_axis.set_title("Prediction intervals")
        residual_axis.scatter(std, np.abs(residual), label="Absolute error")
        residual_axis.set_xlabel("Estimated uncertainty"); residual_axis.set_ylabel("Absolute error")
        residual_axis.set_title("Error and uncertainty")
        standardized = np.divide(residual, std, out=np.zeros_like(residual), where=std > 1e-12)
        calibration_axis.hist(standardized, bins=min(10, max(4, len(standardized)//2)),
                              label="Standardized residuals")
        calibration_axis.axvline(0, linestyle="--", linewidth=1, label="Zero residual")
        calibration_axis.set_xlabel("Standardized residual"); calibration_axis.set_ylabel("Count")
        calibration_axis.set_title(f"Coverage {result.metrics['coverage_percent']:.1f}%")
        apply_chart_style(figure)
        return figure

    @staticmethod
    def _surface_matrix(surface: pd.DataFrame, value_field: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        x_field = str(surface.attrs.get("x_field") or "")
        y_field = str(surface.attrs.get("y_field") or "")
        if not x_field or not y_field:
            excluded = {"grid_row", "grid_column", value_field}
            candidates = [column for column in surface.columns if column not in excluded]
            if len(candidates) < 2:
                raise ValueError("Response-map coordinates are unavailable.")
            x_field, y_field = candidates[0], candidates[1]
        required = {x_field, y_field, "grid_row", "grid_column", value_field}
        if not required.issubset(surface.columns):
            raise ValueError("Response-map data are incomplete.")
        row_count = int(surface["grid_row"].max()) + 1
        column_count = int(surface["grid_column"].max()) + 1
        expected = row_count * column_count
        if len(surface) != expected:
            raise ValueError("Response-map grid is incomplete and cannot be rendered.")
        ordered = surface.sort_values(["grid_row", "grid_column"])
        x = ordered[x_field].to_numpy(dtype=float).reshape(row_count, column_count)
        y = ordered[y_field].to_numpy(dtype=float).reshape(row_count, column_count)
        values = ordered[value_field].to_numpy(dtype=float).reshape(row_count, column_count)
        return x, y, values

    @classmethod
    def response_map_figures(
        cls,
        surface: pd.DataFrame,
        x_field: str,
        y_field: str,
        response_label: str,
    ) -> dict[str, Figure]:
        surface.attrs["x_field"] = x_field
        surface.attrs["y_field"] = y_field
        grid_x, grid_y, mean = cls._surface_matrix(surface, "predicted_mean")
        _, _, uncertainty = cls._surface_matrix(surface, "normalized_uncertainty_percent")
        reliability_values = surface.copy()
        reliability_values["reliability_code"] = reliability_values["reliability_class"].map(
            {"A": 1, "B": 2, "C": 3, "D": 4}
        )
        _, _, reliability = cls._surface_matrix(reliability_values, "reliability_code")

        mean_figure, mean_axis = cls._single_figure("Estimated response")
        mean_plot = mean_axis.contourf(grid_x, grid_y, mean, levels=18, cmap="viridis")
        mean_figure.colorbar(mean_plot, ax=mean_axis, label=response_label)

        uncertainty_figure, uncertainty_axis = cls._single_figure("Relative uncertainty")
        uncertainty_plot = uncertainty_axis.contourf(
            grid_x, grid_y, uncertainty, levels=18, cmap="magma"
        )
        uncertainty_figure.colorbar(uncertainty_plot, ax=uncertainty_axis, label="Uncertainty (%)")

        reliability_figure, reliability_axis = cls._single_figure("Reliability class")
        reliability_plot = reliability_axis.contourf(
            grid_x, grid_y, reliability, levels=[0.5, 1.5, 2.5, 3.5, 4.5], cmap="RdYlGn_r"
        )
        colorbar = reliability_figure.colorbar(
            reliability_plot, ax=reliability_axis, ticks=[1, 2, 3, 4], label="Reliability"
        )
        colorbar.ax.set_yticklabels(["A", "B", "C", "D"])

        figures = {
            "Estimated response": mean_figure,
            "Relative uncertainty": uncertainty_figure,
            "Reliability": reliability_figure,
        }
        for figure in figures.values():
            for axis in figure.axes:
                if getattr(axis, "_colorbar", None) is None:
                    axis.set_xlabel(COLUMN_LABELS.get(x_field, x_field))
                    axis.set_ylabel(COLUMN_LABELS.get(y_field, y_field))
            apply_chart_style(figure)
        return figures

    @classmethod
    def response_curve_figure(
        cls, curve: pd.DataFrame, field: str, response_label: str
    ) -> Figure:
        figure, axis = cls._single_figure("One-dimensional response curve")
        x = curve[field].to_numpy(dtype=float)
        mean = curve["predicted_mean"].to_numpy(dtype=float)
        lower = curve["lower_bound"].to_numpy(dtype=float)
        upper = curve["upper_bound"].to_numpy(dtype=float)
        axis.plot(x, mean, label="Estimated response")
        axis.fill_between(x, lower, upper, alpha=0.25, label="Prediction interval")
        axis.set_xlabel(COLUMN_LABELS.get(field, field))
        axis.set_ylabel(response_label)
        apply_chart_style(figure)
        return figure

    @classmethod
    def response_map_figure(
        cls,
        surface: pd.DataFrame,
        x_field: str,
        y_field: str,
        response_label: str,
    ) -> Figure:
        """Backward-compatible combined response-map figure."""
        surface.attrs["x_field"] = x_field
        surface.attrs["y_field"] = y_field
        grid_x, grid_y, mean = cls._surface_matrix(surface, "predicted_mean")
        _, _, uncertainty = cls._surface_matrix(surface, "normalized_uncertainty_percent")
        reliability_values = surface.copy()
        reliability_values["reliability_code"] = reliability_values["reliability_class"].map(
            {"A": 1, "B": 2, "C": 3, "D": 4}
        )
        _, _, reliability = cls._surface_matrix(reliability_values, "reliability_code")
        figure = Figure(figsize=(11.8, 4.5), constrained_layout=True)
        mean_axis, uncertainty_axis, reliability_axis = (
            figure.add_subplot(131), figure.add_subplot(132), figure.add_subplot(133)
        )
        mean_plot = mean_axis.contourf(grid_x, grid_y, mean, levels=18, cmap="viridis")
        figure.colorbar(mean_plot, ax=mean_axis, label=response_label)
        mean_axis.set_title("Estimated response")
        uncertainty_plot = uncertainty_axis.contourf(grid_x, grid_y, uncertainty, levels=18, cmap="magma")
        figure.colorbar(uncertainty_plot, ax=uncertainty_axis, label="Uncertainty (%)")
        uncertainty_axis.set_title("Relative uncertainty")
        reliability_plot = reliability_axis.contourf(
            grid_x, grid_y, reliability, levels=[0.5,1.5,2.5,3.5,4.5], cmap="RdYlGn_r"
        )
        colorbar = figure.colorbar(reliability_plot, ax=reliability_axis, ticks=[1,2,3,4], label="Reliability")
        colorbar.ax.set_yticklabels(["A","B","C","D"])
        reliability_axis.set_title("Reliability class")
        for axis in (mean_axis, uncertainty_axis, reliability_axis):
            axis.set_xlabel(COLUMN_LABELS.get(x_field, x_field))
            axis.set_ylabel(COLUMN_LABELS.get(y_field, y_field))
        apply_chart_style(figure)
        return figure

    @staticmethod
    def save_artifact(artifact: dict[str, Any], directory: Path | str) -> Path:
        DigitalTwinService._validate_artifact(artifact)
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        metadata = artifact["metadata"]
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        stem = "__".join([
            DigitalTwinService._slug(str(metadata["response"])),
            DigitalTwinService._slug(str(metadata["method"])),
            timestamp,
        ])
        artifact_path = directory / f"{stem}.joblib"
        metadata_path = directory / f"{stem}.json"
        joblib.dump(artifact, artifact_path)
        metadata_copy = dict(metadata)
        metadata_copy["artifact_file"] = artifact_path.name
        metadata_path.write_text(
            json.dumps(metadata_copy, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return artifact_path

    @staticmethod
    def load_artifact(path: Path | str) -> dict[str, Any]:
        artifact = joblib.load(Path(path))
        DigitalTwinService._validate_artifact(artifact)
        return artifact

    @staticmethod
    def list_saved_twins(directory: Path | str) -> pd.DataFrame:
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
                    "method": metadata.get("method", ""),
                    "response": metadata.get("response", ""),
                    "confidence_percent": metadata.get("confidence_percent", np.nan),
                    "observations": metadata.get("observations", ""),
                    "rmse": metrics.get("rmse", np.nan),
                    "r2": metrics.get("r2", np.nan),
                    "coverage_percent": metrics.get("coverage_percent", np.nan),
                    "artifact_path": str(artifact_path),
                })
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
        return pd.DataFrame(rows)

    @staticmethod
    def delete_artifact(path: Path | str) -> None:
        artifact_path = Path(path)
        metadata_path = artifact_path.with_suffix(".json")
        if artifact_path.exists():
            artifact_path.unlink()
        if metadata_path.exists():
            metadata_path.unlink()
