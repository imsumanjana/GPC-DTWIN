"""Predictive model comparison, persistence, and prediction utilities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from time import perf_counter
from typing import Any

import joblib
import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold, KFold, cross_val_predict
from sklearn.pipeline import Pipeline

from gpc_dtwin import __version__
from gpc_dtwin.chart_style import apply_chart_style
from gpc_dtwin.columns import COLUMN_LABELS, MODEL_NUMERIC_PREDICTORS, quantity_label
from gpc_dtwin.services.model_registry import (
    MODEL_FACTORIES, algorithm_names, build_pipeline, build_preprocessor,
)


REVIEW_STATES = {"REQUIRES_REVIEW", "CONFLICTING"}


@dataclass
class ModelComparisonResult:
    response: str
    predictors: tuple[str, ...]
    omitted_predictors: tuple[str, ...]
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
        return algorithm_names()

    @staticmethod
    def _slug(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")

    @staticmethod
    def _filtered_response_rows(
        dataframe: pd.DataFrame,
        response: str,
        include_review_records: bool,
    ) -> pd.DataFrame:
        if response not in dataframe.columns:
            raise ValueError(f"Missing selected response: {response}")
        working = dataframe.copy()
        if "data_status" in working.columns:
            states = working["data_status"].astype("string").str.upper()
            keep = states.ne("EXCLUDED")
            if not include_review_records:
                keep &= ~states.isin(REVIEW_STATES)
            working = working.loc[keep].copy()
        working[response] = pd.to_numeric(working[response], errors="coerce")
        return working.dropna(subset=[response]).copy()

    @staticmethod
    def predictor_availability(
        dataframe: pd.DataFrame,
        response: str,
        predictors: list[str],
        include_review_records: bool = False,
    ) -> tuple[list[str], list[str]]:
        """Return predictors with response-overlapping values and unavailable fields."""
        requested = [
            predictor
            for predictor in dict.fromkeys(predictors)
            if predictor != response
        ]
        missing = [column for column in requested if column not in dataframe.columns]
        if missing:
            raise ValueError("Missing selected fields: " + ", ".join(missing))

        working = ModelingService._filtered_response_rows(
            dataframe, response, include_review_records
        )
        available: list[str] = []
        unavailable: list[str] = []

        for predictor in requested:
            if predictor in MODEL_NUMERIC_PREDICTORS:
                values = pd.to_numeric(working[predictor], errors="coerce")
            else:
                values = working[predictor].astype("string").str.strip()
                values = values.mask(values.eq(""))
            if values.notna().any():
                available.append(predictor)
            else:
                unavailable.append(predictor)

        return available, unavailable

    @staticmethod
    def _prepare_working_data(
        dataframe: pd.DataFrame,
        response: str,
        predictors: list[str],
        include_review_records: bool,
        group_column: str,
    ) -> tuple[pd.DataFrame, int, list[str], list[str]]:
        requested = [
            predictor
            for predictor in dict.fromkeys(predictors)
            if predictor != response
        ]
        if not requested:
            raise ValueError("Select at least one predictor.")

        required = [response, *requested]
        missing = [column for column in required if column not in dataframe.columns]
        if missing:
            raise ValueError("Missing selected fields: " + ", ".join(missing))

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
        working = working.dropna(subset=[response]).copy()

        usable: list[str] = []
        omitted: list[str] = []
        for predictor in requested:
            if predictor in MODEL_NUMERIC_PREDICTORS:
                values = pd.to_numeric(working[predictor], errors="coerce")
            else:
                values = working[predictor].astype("string").str.strip()
                values = values.mask(values.eq(""))
            working[predictor] = values
            if values.notna().any():
                usable.append(predictor)
            else:
                omitted.append(predictor)

        if not usable:
            response_label = COLUMN_LABELS.get(response, response)
            raise ValueError(
                f"No selected predictor has usable values for {response_label}. "
                "Choose fields that overlap the selected response."
            )
        if len(working) < 8:
            raise ValueError("At least eight usable response records are required.")

        keep_columns = [response, *usable, *extra]
        working = working.loc[:, list(dict.fromkeys(keep_columns))].copy()
        return working, original_count - len(working), usable, omitted

    @staticmethod
    def _preprocessor(predictors: list[str]):
        return build_preprocessor(predictors)


    @staticmethod
    def _pipeline(predictors: list[str], algorithm: str) -> Pipeline:
        return build_pipeline(predictors, algorithm)

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
            splits = list(splitter.split(working, groups=groups))
            return splits, groups, (
                f"Grouped {folds}-fold cross-validation by {COLUMN_LABELS.get(group_column, group_column)}"
            )
        folds = min(5, len(working))
        if folds < 2:
            raise ValueError("Insufficient observations for cross-validation.")
        splitter = KFold(n_splits=folds, shuffle=True, random_state=42)
        return list(splitter.split(working)), None, f"{folds}-fold cross-validation"

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

    @staticmethod
    def _fold_metrics(y: np.ndarray, predicted: np.ndarray, splits) -> dict[str, float]:
        rmses: list[float] = []
        maes: list[float] = []
        r2_values: list[float] = []
        for _, test_index in splits:
            truth = y[test_index]
            estimate = predicted[test_index]
            rmses.append(float(np.sqrt(mean_squared_error(truth, estimate))))
            maes.append(float(mean_absolute_error(truth, estimate)))
            if len(test_index) >= 2 and float(np.var(truth)) > 1e-12:
                r2_values.append(float(r2_score(truth, estimate)))
        return {
            "cv_rmse_mean": float(np.mean(rmses)),
            "cv_rmse_std": float(np.std(rmses, ddof=0)),
            "cv_mae_mean": float(np.mean(maes)),
            "cv_mae_std": float(np.std(maes, ddof=0)),
            "cv_r2_mean": float(np.mean(r2_values)) if r2_values else float("nan"),
            "cv_r2_std": float(np.std(r2_values, ddof=0)) if r2_values else float("nan"),
        }

    @staticmethod
    def _assign_dynamic_status(rankings: pd.DataFrame) -> pd.DataFrame:
        """Attach one-word, data-derived notes for the current validation run only.

        The note deliberately combines relative RMSE/MAE, R² consistency, and fold-to-fold
        RMSE variation.  It is never a fixed property of an algorithm.
        """
        table = rankings.copy()
        if table.empty:
            table["rmse_gap_percent"] = pd.Series(dtype=float)
            table["mae_gap_percent"] = pd.Series(dtype=float)
            table["cv_rmse_variation_percent"] = pd.Series(dtype=float)
            table["status"] = pd.Series(dtype="string")
            table["status_reason"] = pd.Series(dtype="string")
            return table

        leader_rmse = max(float(table.iloc[0]["rmse"]), 1e-12)
        best_mae = max(float(pd.to_numeric(table["mae"], errors="coerce").min()), 1e-12)
        best_r2 = float(pd.to_numeric(table["r2"], errors="coerce").max())

        rmse_gaps: list[float] = []
        mae_gaps: list[float] = []
        variations: list[float] = []
        statuses: list[str] = []
        reasons: list[str] = []

        for _, row in table.iterrows():
            rank = int(row["rank"])
            rmse = float(row["rmse"])
            mae = float(row["mae"])
            r2 = float(row["r2"])
            rmse_gap = max((rmse / leader_rmse - 1.0) * 100.0, 0.0)
            mae_gap = max((mae / best_mae - 1.0) * 100.0, 0.0)
            rmse_mean = max(float(row.get("cv_rmse_mean", rmse)), 1e-12)
            variation = max(float(row.get("cv_rmse_std", 0.0)) / rmse_mean * 100.0, 0.0)
            r2_drop = max(best_r2 - r2, 0.0) if np.isfinite(r2) and np.isfinite(best_r2) else 0.0

            if rank == 1:
                status = "Recommended"
                reason = (
                    f"Current validation leader; fold RMSE variation {variation:.1f}%."
                )
            elif variation > 50.0:
                status = "Uncertain"
                reason = (
                    f"High fold-to-fold RMSE variation ({variation:.1f}%); RMSE is "
                    f"{rmse_gap:.1f}% above the leader."
                )
            elif rmse_gap >= 50.0 or (r2 < 0.0 and best_r2 >= 0.30):
                status = "Weak"
                reason = (
                    f"RMSE is {rmse_gap:.1f}% above the leader; validation fit is materially weaker."
                )
            elif rmse_gap <= 5.0 and mae_gap <= 10.0 and variation <= 30.0:
                status = "Competitive"
                reason = (
                    f"Within {rmse_gap:.1f}% RMSE and {mae_gap:.1f}% MAE of the best values; "
                    f"fold variation {variation:.1f}%."
                )
            elif rmse_gap <= 20.0 and variation <= 15.0 and r2_drop <= 0.15:
                status = "Stable"
                reason = (
                    f"Consistent across folds ({variation:.1f}% variation); RMSE is "
                    f"{rmse_gap:.1f}% above the leader."
                )
            elif (rmse_gap <= 25.0 and mae_gap > 30.0) or (r2_drop > 0.30 and rmse_gap <= 30.0):
                status = "Mixed"
                reason = (
                    f"Validation indicators disagree (RMSE gap {rmse_gap:.1f}%, MAE gap "
                    f"{mae_gap:.1f}%, R² drop {r2_drop:.3f})."
                )
            elif rmse_gap <= 30.0 and variation <= 35.0:
                status = "Moderate"
                reason = (
                    f"Acceptable but below stronger candidates; RMSE gap {rmse_gap:.1f}% and "
                    f"fold variation {variation:.1f}%."
                )
            else:
                status = "Mixed"
                reason = (
                    f"No stronger classification from current metrics (RMSE gap {rmse_gap:.1f}%, "
                    f"MAE gap {mae_gap:.1f}%, fold variation {variation:.1f}%)."
                )

            rmse_gaps.append(rmse_gap)
            mae_gaps.append(mae_gap)
            variations.append(variation)
            statuses.append(status)
            reasons.append(reason)

        table["rmse_gap_percent"] = rmse_gaps
        table["mae_gap_percent"] = mae_gaps
        table["cv_rmse_variation_percent"] = variations
        table["status"] = statuses
        table["status_reason"] = reasons
        return table

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

        requested_predictors = list(dict.fromkeys(predictors))
        working, excluded_records, predictors, omitted_predictors = self._prepare_working_data(
            dataframe, response, requested_predictors, include_review_records, group_column
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
            predicted = cross_val_predict(pipeline, x, y, cv=cv)
            elapsed = perf_counter() - started
            rmse = float(np.sqrt(mean_squared_error(y, predicted)))
            mae = float(mean_absolute_error(y, predicted))
            r2 = float(r2_score(y, predicted))
            mape = self._mape(y, predicted)
            slug = self._slug(algorithm)
            prediction_table[f"{slug}_predicted"] = predicted
            prediction_table[f"{slug}_residual"] = y - predicted
            fold_metrics = self._fold_metrics(y, predicted, cv)
            ranking_rows.append({
                "algorithm": algorithm,
                "rmse": rmse,
                "mae": mae,
                "r2": r2,
                "mape_percent": mape,
                "fit_seconds": float(elapsed),
                **fold_metrics,
            })

        rankings = pd.DataFrame(ranking_rows).sort_values(
            ["rmse", "mae", "algorithm"], ascending=[True, True, True]
        ).reset_index(drop=True)
        rankings.insert(0, "rank", np.arange(1, len(rankings) + 1))
        rankings = self._assign_dynamic_status(rankings)
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
            "requested_predictors": requested_predictors,
            "omitted_predictors": omitted_predictors,
            "numeric_predictors": [column for column in predictors if column in MODEL_NUMERIC_PREDICTORS],
            "categorical_predictors": [column for column in predictors if column not in MODEL_NUMERIC_PREDICTORS],
            "input_defaults": defaults,
            "input_categories": categories,
            "numeric_training_ranges": numeric_ranges,
            "data_fingerprint_sha256": fingerprint,
            "observations": len(working),
            "excluded_records": excluded_records,
            "include_review_records": bool(include_review_records),
            "group_column": group_column,
            "cv_method": cv_method,
            "metrics": best_metrics,
            "ranking": rankings.replace({np.nan: None}).to_dict(orient="records"),
        }
        artifact = {"pipeline": best_pipeline, "metadata": metadata}

        return ModelComparisonResult(
            response=response,
            predictors=tuple(predictors),
            omitted_predictors=tuple(omitted_predictors),
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
        axis.set_xlabel(quantity_label("Prediction error", result.response))
        axis.grid(True, axis="x", alpha=0.25)
        axis.legend()
        return figure

    @staticmethod
    def diagnostic_figures(result: ModelComparisonResult, algorithm: str | None = None) -> dict[str, Figure]:
        algorithm = algorithm or result.best_algorithm
        slug = ModelingService._slug(algorithm)
        predicted_column = f"{slug}_predicted"
        residual_column = f"{slug}_residual"
        if predicted_column not in result.predictions.columns:
            raise ValueError("Predictions for the selected algorithm are unavailable.")
        observed = result.predictions["observed"].astype(float)
        predicted = result.predictions[predicted_column].astype(float)
        residual = result.predictions[residual_column].astype(float)

        fit_figure = Figure(figsize=(6.6, 5.8), constrained_layout=True)
        fit_axis = fit_figure.add_subplot(111)
        fit_axis.scatter(observed, predicted, label="Cross-validated predictions")
        minimum = min(float(observed.min()), float(predicted.min()))
        maximum = max(float(observed.max()), float(predicted.max()))
        fit_axis.plot([minimum, maximum], [minimum, maximum], linestyle="--", linewidth=1,
                      label="Ideal agreement")
        fit_axis.set_xlabel(quantity_label("Observed", result.response))
        fit_axis.set_ylabel(quantity_label("Cross-validated prediction", result.response))
        fit_axis.set_title(algorithm)

        residual_figure = Figure(figsize=(6.6, 5.8), constrained_layout=True)
        residual_axis = residual_figure.add_subplot(111)
        residual_axis.scatter(predicted, residual, label="Residuals")
        residual_axis.axhline(0, linestyle="--", linewidth=1, label="Zero residual")
        residual_axis.set_xlabel(quantity_label("Cross-validated prediction", result.response))
        residual_axis.set_ylabel(quantity_label("Residual", result.response))
        residual_axis.set_title("Residual pattern")

        figures = {"Observed vs predicted": fit_figure, "Residuals": residual_figure}
        for figure in figures.values():
            apply_chart_style(figure)
        return figures

    @staticmethod
    def diagnostics_figure(result: ModelComparisonResult, algorithm: str | None = None) -> Figure:
        """Backward-compatible combined diagnostic view."""
        figures = ModelingService.diagnostic_figures(result, algorithm)
        algorithm = algorithm or result.best_algorithm
        slug = ModelingService._slug(algorithm)
        observed = result.predictions["observed"].astype(float)
        predicted = result.predictions[f"{slug}_predicted"].astype(float)
        residual = result.predictions[f"{slug}_residual"].astype(float)
        figure = Figure(figsize=(9, 4.8), constrained_layout=True)
        fit_axis = figure.add_subplot(121)
        residual_axis = figure.add_subplot(122)
        fit_axis.scatter(observed, predicted, label="Cross-validated predictions")
        minimum = min(float(observed.min()), float(predicted.min()))
        maximum = max(float(observed.max()), float(predicted.max()))
        fit_axis.plot([minimum, maximum], [minimum, maximum], linestyle="--", linewidth=1,
                      label="Ideal agreement")
        fit_axis.set_xlabel(quantity_label("Observed", result.response)); fit_axis.set_ylabel(quantity_label("Cross-validated prediction", result.response))
        fit_axis.set_title(algorithm)
        residual_axis.scatter(predicted, residual, label="Residuals")
        residual_axis.axhline(0, linestyle="--", linewidth=1, label="Zero residual")
        residual_axis.set_xlabel(quantity_label("Cross-validated prediction", result.response)); residual_axis.set_ylabel(quantity_label("Residual", result.response))
        residual_axis.set_title("Residual pattern")
        apply_chart_style(figure)
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
        axis.set_xlabel(quantity_label("Permutation importance (RMSE increase)", result.response))
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
    def comparison_from_artifact(artifact: dict[str, Any]) -> ModelComparisonResult | None:
        """Reconstruct the validated ranking stored with a saved best-model artifact.

        Saved v1.2+ model metadata contains the complete seven-model ranking.  This
        compact reconstruction is sufficient for the downstream Digital Twin hand-off
        after a saved model is reloaded in a later application session.
        """
        ModelingService._validate_artifact(artifact)
        metadata = artifact["metadata"]
        records = metadata.get("ranking", [])
        if not isinstance(records, list) or not records:
            return None
        rankings = pd.DataFrame(records)
        required = {"rank", "algorithm", "rmse", "mae", "r2"}
        if rankings.empty or not required.issubset(rankings.columns):
            return None
        rankings = rankings.sort_values("rank").reset_index(drop=True)
        best_algorithm = str(metadata.get("algorithm", rankings.iloc[0]["algorithm"]))
        metrics = metadata.get("metrics", {})
        best_metrics = {
            "rmse": float(metrics.get("rmse", np.nan)),
            "mae": float(metrics.get("mae", np.nan)),
            "r2": float(metrics.get("r2", np.nan)),
            "mape_percent": float(metrics.get("mape_percent", np.nan)),
        }
        return ModelComparisonResult(
            response=str(metadata["response"]),
            predictors=tuple(str(value) for value in metadata.get("predictors", [])),
            omitted_predictors=tuple(str(value) for value in metadata.get("omitted_predictors", [])),
            observations=int(metadata.get("observations", 0)),
            excluded_records=int(metadata.get("excluded_records", 0)),
            cv_method=str(metadata.get("cv_method", "Saved validated comparison")),
            rankings=rankings,
            predictions=pd.DataFrame(),
            best_algorithm=best_algorithm,
            best_metrics=best_metrics,
            feature_influence=pd.DataFrame(),
            artifact=artifact,
        )

    @staticmethod
    def artifact_matches_dataframe(artifact: dict[str, Any], dataframe: pd.DataFrame) -> bool:
        """Check whether a saved ranking was fitted to the current active data/configuration."""
        ModelingService._validate_artifact(artifact)
        metadata = artifact["metadata"]
        expected = str(metadata.get("data_fingerprint_sha256", ""))
        if not expected:
            return False
        response = str(metadata["response"])
        predictors = [str(value) for value in metadata.get("predictors", [])]
        try:
            working, _, usable, _ = ModelingService._prepare_working_data(
                dataframe,
                response,
                predictors,
                bool(metadata.get("include_review_records", False)),
                str(metadata.get("group_column", "mix_id")),
            )
        except Exception:
            return False
        if set(usable) != set(predictors):
            return False
        fingerprint_frame = working[[response, *usable]].copy()
        actual = hashlib.sha256(
            pd.util.hash_pandas_object(fingerprint_frame, index=True).values.tobytes()
        ).hexdigest()
        return actual == expected

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
