"""Uncertainty-guided experiment recommendation and closed-loop model update analysis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Iterable

import joblib
import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from scipy.stats import norm, qmc

from gpc_dtwin import __version__
from gpc_dtwin.chart_style import apply_chart_style
from gpc_dtwin.columns import COLUMN_LABELS, DATA_COLUMNS, MODEL_NUMERIC_PREDICTORS
from gpc_dtwin.services.digital_twin_service import DigitalTwinService, TwinBuildResult


ACQUISITION_STRATEGIES = (
    "Maximum uncertainty",
    "Expected improvement",
    "Confidence bound",
    "Balanced exploration",
)
DIRECTIONS = ("Maximize", "Minimize")


@dataclass(frozen=True)
class LearningVariable:
    field: str
    lower: float
    upper: float


@dataclass
class ActiveLearningRunResult:
    response: str
    predictors: tuple[str, ...]
    variables: tuple[LearningVariable, ...]
    method: str
    strategy: str
    direction: str
    confidence_percent: float
    candidate_count: int
    recommendation_count: int
    binder_closure: bool
    diversity_weight: float
    exploration_parameter: float
    confidence_bound_weight: float
    include_review_records: bool
    recommendations: pd.DataFrame
    candidate_pool: pd.DataFrame
    surrogate_summary: pd.DataFrame
    artifact: dict[str, Any]
    metadata: dict[str, Any]


@dataclass
class UpdateComparisonResult:
    comparison: pd.DataFrame
    updated_summary: pd.DataFrame
    updated_artifact: dict[str, Any]
    metadata: dict[str, Any]


class ActiveLearningService:
    """Recommend informative material scenarios from uncertainty-aware surrogates."""

    COMPOSITION_FIELDS = (
        "fa_percent_numeric", "ggbs_percent_numeric", "sf_percent_numeric"
    )

    @staticmethod
    def method_names() -> list[str]:
        return DigitalTwinService.method_names()

    @staticmethod
    def acquisition_names() -> list[str]:
        return list(ACQUISITION_STRATEGIES)

    @staticmethod
    def _slug(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")

    @staticmethod
    def default_bounds(
        dataframe: pd.DataFrame, fields: Iterable[str]
    ) -> dict[str, tuple[float, float]]:
        bounds: dict[str, tuple[float, float]] = {}
        for field in fields:
            if field not in dataframe.columns:
                continue
            values = pd.to_numeric(dataframe[field], errors="coerce").dropna()
            if values.empty:
                continue
            lower = float(values.min())
            upper = float(values.max())
            if np.isclose(lower, upper):
                margin = max(abs(lower) * 0.05, 0.5)
                lower -= margin
                upper += margin
            bounds[field] = (lower, upper)
        return bounds

    @classmethod
    def _validate_variables(
        cls, variables: Iterable[LearningVariable], binder_closure: bool
    ) -> tuple[LearningVariable, ...]:
        items = tuple(variables)
        if not items:
            raise ValueError("Select at least one experiment variable.")
        fields = [item.field for item in items]
        if len(fields) != len(set(fields)):
            raise ValueError("Experiment variables must be unique.")
        for item in items:
            if item.field not in MODEL_NUMERIC_PREDICTORS:
                raise ValueError(f"Experiment variables must be numeric: {item.field}")
            if not np.isfinite(item.lower) or not np.isfinite(item.upper):
                raise ValueError(f"Bounds must be finite for {item.field}.")
            if item.lower >= item.upper:
                raise ValueError(f"Lower bound must be below upper bound for {item.field}.")
        if binder_closure:
            missing = [field for field in cls.COMPOSITION_FIELDS if field not in fields]
            if missing:
                raise ValueError("Binder closure requires FA, GGBS, and SF as experiment variables.")
            mapping = {item.field: item for item in items}
            lower_total = sum(mapping[field].lower for field in cls.COMPOSITION_FIELDS)
            upper_total = sum(mapping[field].upper for field in cls.COMPOSITION_FIELDS)
            if lower_total > 100.0 + 1e-9 or upper_total < 100.0 - 1e-9:
                raise ValueError("The selected binder bounds cannot total 100%.")
        return items

    @staticmethod
    def _sample_population(
        variables: tuple[LearningVariable, ...], count: int, seed: int
    ) -> np.ndarray:
        count = int(np.clip(count, 50, 20000))
        sampler = qmc.LatinHypercube(d=len(variables), seed=seed)
        unit = sampler.random(n=count)
        lower = np.asarray([item.lower for item in variables], dtype=float)
        upper = np.asarray([item.upper for item in variables], dtype=float)
        return qmc.scale(unit, lower, upper)

    @classmethod
    def _repair_closure(
        cls,
        population: np.ndarray,
        variables: tuple[LearningVariable, ...],
        binder_closure: bool,
    ) -> np.ndarray:
        lower = np.asarray([item.lower for item in variables], dtype=float)
        upper = np.asarray([item.upper for item in variables], dtype=float)
        repaired = np.clip(np.asarray(population, dtype=float), lower, upper)
        if not binder_closure:
            return repaired

        field_to_index = {item.field: index for index, item in enumerate(variables)}
        indices = np.asarray([field_to_index[field] for field in cls.COMPOSITION_FIELDS])
        local_lower = lower[indices]
        local_upper = upper[indices]
        for row in repaired:
            values = np.clip(row[indices], local_lower, local_upper)
            for _ in range(30):
                difference = 100.0 - float(values.sum())
                if abs(difference) <= 1e-9:
                    break
                room = local_upper - values if difference > 0 else values - local_lower
                available = float(room.sum())
                if available <= 1e-12:
                    break
                values += np.sign(difference) * min(abs(difference), available) * room / available
                values = np.clip(values, local_lower, local_upper)
            residual = 100.0 - float(values.sum())
            if abs(residual) > 1e-7:
                for index in np.argsort(-(local_upper - local_lower)):
                    candidate = float(np.clip(values[index] + residual, local_lower[index], local_upper[index]))
                    applied = candidate - values[index]
                    values[index] = candidate
                    residual -= applied
                    if abs(residual) <= 1e-7:
                        break
            row[indices] = values
        return repaired

    @staticmethod
    def _candidate_frame(
        population: np.ndarray,
        variables: tuple[LearningVariable, ...],
        artifact: dict[str, Any],
    ) -> pd.DataFrame:
        metadata = artifact["metadata"]
        predictors = list(metadata["predictors"])
        defaults = metadata.get("input_defaults", {})
        frame = pd.DataFrame([
            {field: defaults.get(field) for field in predictors}
            for _ in range(len(population))
        ])
        for index, variable in enumerate(variables):
            if variable.field in frame.columns:
                frame[variable.field] = population[:, index]
        return frame

    @staticmethod
    def _minmax(values: np.ndarray) -> np.ndarray:
        array = np.asarray(values, dtype=float)
        finite = np.isfinite(array)
        result = np.zeros_like(array, dtype=float)
        if not finite.any():
            return result
        minimum = float(np.min(array[finite]))
        maximum = float(np.max(array[finite]))
        if np.isclose(minimum, maximum):
            result[finite] = 1.0
        else:
            result[finite] = (array[finite] - minimum) / (maximum - minimum)
        return result

    @staticmethod
    def _existing_distance(
        dataframe: pd.DataFrame,
        population: np.ndarray,
        variables: tuple[LearningVariable, ...],
    ) -> np.ndarray:
        fields = [item.field for item in variables]
        if any(field not in dataframe.columns for field in fields):
            return np.ones(len(population), dtype=float)
        existing = dataframe[fields].apply(pd.to_numeric, errors="coerce").dropna().drop_duplicates()
        if existing.empty:
            return np.ones(len(population), dtype=float)
        lower = np.asarray([item.lower for item in variables], dtype=float)
        span = np.asarray([max(item.upper - item.lower, 1e-12) for item in variables], dtype=float)
        candidates_norm = (population - lower) / span
        existing_norm = (existing.to_numpy(dtype=float) - lower) / span
        distances = np.sqrt(
            np.sum((candidates_norm[:, None, :] - existing_norm[None, :, :]) ** 2, axis=2)
        )
        return np.min(distances, axis=1)

    @staticmethod
    def _expected_improvement(
        mean: np.ndarray,
        std: np.ndarray,
        best_observed: float,
        direction: str,
        exploration_parameter: float,
    ) -> np.ndarray:
        std = np.asarray(std, dtype=float)
        if direction == "Maximize":
            improvement = np.asarray(mean, dtype=float) - best_observed - exploration_parameter
        else:
            improvement = best_observed - np.asarray(mean, dtype=float) - exploration_parameter
        safe_std = np.maximum(std, 1e-12)
        z_value = improvement / safe_std
        expected = improvement * norm.cdf(z_value) + safe_std * norm.pdf(z_value)
        expected = np.where(std <= 1e-12, np.maximum(improvement, 0.0), expected)
        return np.maximum(expected, 0.0)

    @classmethod
    def _acquisition(
        cls,
        predictions: pd.DataFrame,
        artifact: dict[str, Any],
        strategy: str,
        direction: str,
        exploration_parameter: float,
        confidence_bound_weight: float,
        novelty: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        mean = predictions["predicted_mean"].to_numpy(dtype=float)
        std = predictions["prediction_std"].to_numpy(dtype=float)
        response_range = artifact["metadata"].get("response_training_range", [0.0, 1.0])
        best_observed = float(response_range[1] if direction == "Maximize" else response_range[0])
        expected = cls._expected_improvement(
            mean, std, best_observed, direction, exploration_parameter
        )
        uncertainty_score = cls._minmax(std)
        improvement_score = cls._minmax(expected)
        novelty_score = cls._minmax(novelty)

        if direction == "Maximize":
            bound = mean + confidence_bound_weight * std
            potential = mean
        else:
            bound = -(mean - confidence_bound_weight * std)
            potential = -mean
        bound_score = cls._minmax(bound)
        potential_score = cls._minmax(potential)

        if strategy == "Maximum uncertainty":
            score = 0.85 * uncertainty_score + 0.15 * novelty_score
        elif strategy == "Expected improvement":
            score = 0.80 * improvement_score + 0.10 * uncertainty_score + 0.10 * novelty_score
        elif strategy == "Confidence bound":
            score = 0.80 * bound_score + 0.10 * uncertainty_score + 0.10 * novelty_score
        elif strategy == "Balanced exploration":
            score = (
                0.35 * improvement_score
                + 0.25 * uncertainty_score
                + 0.20 * potential_score
                + 0.20 * novelty_score
            )
        else:
            raise ValueError(f"Unsupported acquisition strategy: {strategy}")
        return cls._minmax(score), expected

    @staticmethod
    def _select_diverse(
        candidate_table: pd.DataFrame,
        normalized_population: np.ndarray,
        count: int,
        diversity_weight: float,
    ) -> list[int]:
        count = int(np.clip(count, 1, len(candidate_table)))
        base = candidate_table["acquisition_score"].to_numpy(dtype=float)
        available = set(range(len(candidate_table)))
        selected: list[int] = []
        first = int(np.nanargmax(base))
        selected.append(first)
        available.remove(first)
        while available and len(selected) < count:
            choices = np.asarray(sorted(available), dtype=int)
            distances = np.sqrt(
                np.sum(
                    (
                        normalized_population[choices, None, :]
                        - normalized_population[np.asarray(selected), :][None, :, :]
                    ) ** 2,
                    axis=2,
                )
            )
            min_distance = np.min(distances, axis=1)
            distance_score = ActiveLearningService._minmax(min_distance)
            adjusted = (
                (1.0 - diversity_weight) * base[choices]
                + diversity_weight * distance_score
            )
            chosen = int(choices[int(np.nanargmax(adjusted))])
            selected.append(chosen)
            available.remove(chosen)
        return selected

    def recommend(
        self,
        dataframe: pd.DataFrame,
        response: str,
        predictors: list[str],
        variables: Iterable[LearningVariable],
        method: str = "Random Forest",
        strategy: str = "Balanced exploration",
        direction: str = "Maximize",
        confidence_percent: float = 95.0,
        candidate_count: int = 1200,
        recommendation_count: int = 10,
        binder_closure: bool = True,
        diversity_weight: float = 0.30,
        exploration_parameter: float = 0.01,
        confidence_bound_weight: float = 2.0,
        include_review_records: bool = False,
        seed: int = 42,
    ) -> ActiveLearningRunResult:
        if strategy not in ACQUISITION_STRATEGIES:
            raise ValueError(f"Unsupported acquisition strategy: {strategy}")
        if direction not in DIRECTIONS:
            raise ValueError(f"Unsupported objective direction: {direction}")
        variable_items = self._validate_variables(variables, binder_closure)
        predictors = list(dict.fromkeys(predictors))
        missing_variables = [item.field for item in variable_items if item.field not in predictors]
        if missing_variables:
            raise ValueError(
                "Every experiment variable must also be selected as a predictor: "
                + ", ".join(missing_variables)
            )
        diversity_weight = float(np.clip(diversity_weight, 0.0, 0.95))
        candidate_count = int(np.clip(candidate_count, 50, 20000))
        recommendation_count = int(np.clip(recommendation_count, 1, min(100, candidate_count)))

        requested_predictors = list(predictors)
        twin: TwinBuildResult = DigitalTwinService().build_twin(
            dataframe=dataframe,
            response=response,
            predictors=requested_predictors,
            method=method,
            confidence_percent=confidence_percent,
            include_review_records=include_review_records,
            group_column="mix_id",
        )
        predictors = list(twin.predictors)
        omitted_variables = [
            item.field for item in variable_items if item.field not in predictors
        ]
        variable_items = tuple(
            item for item in variable_items if item.field in predictors
        )
        if not variable_items:
            raise ValueError(
                "None of the selected experiment variables has usable values for the selected response."
            )
        effective_binder_closure = bool(
            binder_closure
            and all(
                field in {item.field for item in variable_items}
                for field in self.COMPOSITION_FIELDS
            )
        )
        population = self._sample_population(variable_items, candidate_count, seed)
        population = self._repair_closure(
            population, variable_items, effective_binder_closure
        )
        candidate_frame = self._candidate_frame(population, variable_items, twin.artifact)
        predictions = DigitalTwinService.predict_dataframe(twin.artifact, candidate_frame)
        novelty = self._existing_distance(dataframe, population, variable_items)
        acquisition, expected = self._acquisition(
            predictions=predictions,
            artifact=twin.artifact,
            strategy=strategy,
            direction=direction,
            exploration_parameter=float(exploration_parameter),
            confidence_bound_weight=float(confidence_bound_weight),
            novelty=novelty,
        )

        table = pd.DataFrame(population, columns=[item.field for item in variable_items])
        for column in (
            "predicted_mean", "prediction_std", "lower_bound", "upper_bound",
            "interval_width", "normalized_uncertainty_percent", "nearest_training_distance",
            "outside_training_range_count", "outside_training_range_fields",
            "reliability_class", "reliability_reason", "input_completeness_percent",
        ):
            table[column] = predictions[column].to_numpy()
        table["existing_design_distance"] = novelty
        table["novelty_score"] = self._minmax(novelty)
        table["expected_improvement"] = expected
        table["acquisition_score"] = acquisition
        table["candidate_id"] = [f"AL-C{index + 1:05d}" for index in range(len(table))]

        # Remove near-duplicates while retaining enough candidates for selection.
        duplicate_threshold = 1e-5
        eligible = table["existing_design_distance"].to_numpy(dtype=float) > duplicate_threshold
        if int(np.sum(eligible)) >= recommendation_count:
            table = table.loc[eligible].reset_index(drop=True)
            population = population[eligible]

        lower = np.asarray([item.lower for item in variable_items], dtype=float)
        span = np.asarray([max(item.upper - item.lower, 1e-12) for item in variable_items], dtype=float)
        normalized_population = (population - lower) / span
        selected_indices = self._select_diverse(
            table, normalized_population, recommendation_count, diversity_weight
        )
        recommendations = table.iloc[selected_indices].copy()
        recommendations = recommendations.sort_values(
            ["acquisition_score", "existing_design_distance"], ascending=[False, False]
        ).reset_index(drop=True)
        recommendations.insert(0, "recommendation_rank", np.arange(1, len(recommendations) + 1))
        recommendations.insert(1, "recommendation_id", [
            f"AL-R{rank:03d}" for rank in range(1, len(recommendations) + 1)
        ])
        recommendations["response"] = response
        recommendations["response_label"] = COLUMN_LABELS.get(response, response)
        recommendations["strategy"] = strategy
        recommendations["direction"] = direction

        table = table.sort_values("acquisition_score", ascending=False).reset_index(drop=True)
        table.insert(0, "candidate_rank", np.arange(1, len(table) + 1))
        table["response"] = response

        summary = pd.DataFrame([{
            "response": response,
            "response_label": COLUMN_LABELS.get(response, response),
            "method": method,
            "strategy": strategy,
            "direction": direction,
            "observations": twin.observations,
            "rmse": twin.metrics["rmse"],
            "mae": twin.metrics["mae"],
            "r2": twin.metrics["r2"],
            "coverage_percent": twin.metrics["coverage_percent"],
            "normalized_rmse_percent": twin.metrics["normalized_rmse_percent"],
            "calibration_gap_percent": twin.metrics["calibration_gap_percent"],
            "mean_interval_width": twin.metrics["mean_interval_width"],
            "used_predictors": ", ".join(twin.predictors),
            "omitted_predictors": ", ".join(twin.omitted_predictors),
            "omitted_variables": ", ".join(omitted_variables),
        }])
        created = datetime.now(timezone.utc).isoformat()
        metadata = {
            "format_version": 1,
            "artifact_type": "active_learning_run",
            "application_version": __version__,
            "created_at_utc": created,
            "response": response,
            "response_label": COLUMN_LABELS.get(response, response),
            "requested_predictors": requested_predictors,
            "predictors": predictors,
            "omitted_predictors": list(twin.omitted_predictors),
            "omitted_predictor_reasons": dict(twin.omitted_reasons),
            "omitted_variables": omitted_variables,
            "variables": [item.__dict__ for item in variable_items],
            "method": method,
            "strategy": strategy,
            "direction": direction,
            "confidence_percent": float(confidence_percent),
            "candidate_count": int(candidate_count),
            "eligible_candidates": int(len(table)),
            "recommendation_count": int(len(recommendations)),
            "binder_closure": effective_binder_closure,
            "diversity_weight": diversity_weight,
            "exploration_parameter": float(exploration_parameter),
            "confidence_bound_weight": float(confidence_bound_weight),
            "include_review_records": bool(include_review_records),
            "seed": int(seed),
            "baseline_metrics": dict(twin.metrics),
            "data_fingerprint_sha256": twin.artifact["metadata"].get("data_fingerprint_sha256", ""),
        }
        return ActiveLearningRunResult(
            response=response,
            predictors=tuple(predictors),
            variables=variable_items,
            method=method,
            strategy=strategy,
            direction=direction,
            confidence_percent=float(confidence_percent),
            candidate_count=candidate_count,
            recommendation_count=len(recommendations),
            binder_closure=effective_binder_closure,
            diversity_weight=diversity_weight,
            exploration_parameter=float(exploration_parameter),
            confidence_bound_weight=float(confidence_bound_weight),
            include_review_records=bool(include_review_records),
            recommendations=recommendations,
            candidate_pool=table,
            surrogate_summary=summary,
            artifact=twin.artifact,
            metadata=metadata,
        )

    @staticmethod
    def experiment_plan(result: ActiveLearningRunResult) -> pd.DataFrame:
        metadata = result.artifact["metadata"]
        defaults = metadata.get("input_defaults", {})
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        rows: list[dict[str, Any]] = []
        for _, recommendation in result.recommendations.iterrows():
            rank = int(recommendation["recommendation_rank"])
            row = {column: "" for column in DATA_COLUMNS}
            row.update({field: defaults.get(field, "") for field in result.predictors})
            for variable in result.variables:
                row[variable.field] = float(recommendation[variable.field])
            fa = row.get("fa_percent_numeric", "")
            ggbs = row.get("ggbs_percent_numeric", "")
            sf = row.get("sf_percent_numeric", "")
            if all(value != "" and pd.notna(value) for value in (fa, ggbs, sf)):
                row["mix_proportion_label"] = f"{float(fa):.2f}:{float(ggbs):.2f}:{float(sf):.2f}"
            row.update({
                "record_id": f"AL-{timestamp}-{rank:03d}",
                "record_group": "ACTIVE_LEARNING_PLAN",
                "dataset_origin": "GPC-DTwin experiment recommendation",
                "data_block": "Recommended material scenario",
                "data_locator": str(recommendation["recommendation_id"]),
                "mix_id": f"AL{rank:03d}",
                "data_status": "REQUIRES_REVIEW",
                "notes": (
                    f"Recommended using {result.strategy}; estimated "
                    f"{COLUMN_LABELS.get(result.response, result.response)} "
                    f"{float(recommendation['predicted_mean']):.4g} with interval "
                    f"[{float(recommendation['lower_bound']):.4g}, "
                    f"{float(recommendation['upper_bound']):.4g}]. Enter measured results "
                    "in the corresponding response field before appending the completed CSV."
                ),
            })
            # Predicted values are not written into measured response fields.
            row[result.response] = ""
            rows.append(row)
        # Keep the editable experiment plan as object dtype. Pandas 3.x uses a
        # strict StringDtype for all-blank columns, which otherwise rejects a
        # later numeric laboratory result assignment. Object dtype preserves
        # blank cells while allowing users or tests to enter measured numbers.
        return pd.DataFrame(rows, columns=DATA_COLUMNS, dtype=object)

    def compare_update(
        self, result: ActiveLearningRunResult, dataframe: pd.DataFrame
    ) -> UpdateComparisonResult:
        updated = DigitalTwinService().build_twin(
            dataframe=dataframe,
            response=result.response,
            predictors=list(result.predictors),
            method=result.method,
            confidence_percent=result.confidence_percent,
            include_review_records=result.include_review_records,
            group_column="mix_id",
        )
        before_observations = int(result.artifact["metadata"].get("observations", 0))
        if updated.observations <= before_observations:
            raise ValueError(
                "No additional usable response records were found. Enter measured values, "
                "assign a usable data status, and append the completed records before comparing."
            )
        before = result.metadata.get("baseline_metrics", {})
        after = updated.metrics
        definitions = [
            ("RMSE", "rmse", "Lower is better"),
            ("MAE", "mae", "Lower is better"),
            ("R²", "r2", "Higher is better"),
            ("Coverage (%)", "coverage_percent", "Closer to confidence is better"),
            ("Mean interval width", "mean_interval_width", "Lower is better"),
            ("Normalized RMSE (%)", "normalized_rmse_percent", "Lower is better"),
            ("Calibration gap (%)", "calibration_gap_percent", "Lower is better"),
        ]
        rows: list[dict[str, Any]] = []
        for label, key, preference in definitions:
            before_value = float(before.get(key, np.nan))
            after_value = float(after.get(key, np.nan))
            rows.append({
                "metric": label,
                "before_update": before_value,
                "after_update": after_value,
                "change": after_value - before_value,
                "preference": preference,
            })
        comparison = pd.DataFrame(rows)
        updated_summary = pd.DataFrame([{
            "response": result.response,
            "method": result.method,
            "observations_before": before_observations,
            "observations_after": int(updated.observations),
            "records_added": int(updated.observations - before_observations),
            **{f"updated_{key}": value for key, value in updated.metrics.items()},
        }])
        metadata = {
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "response": result.response,
            "method": result.method,
            "baseline_fingerprint": result.metadata.get("data_fingerprint_sha256", ""),
            "updated_fingerprint": updated.artifact["metadata"].get("data_fingerprint_sha256", ""),
        }
        return UpdateComparisonResult(
            comparison=comparison,
            updated_summary=updated_summary,
            updated_artifact=updated.artifact,
            metadata=metadata,
        )

    @staticmethod
    def acquisition_figure(
        result: ActiveLearningRunResult,
        x_field: str | None = None,
        y_field: str | None = None,
    ) -> Figure:
        variable_fields = [item.field for item in result.variables]
        if x_field not in variable_fields:
            x_field = variable_fields[0]
        if y_field not in variable_fields or y_field == x_field:
            y_field = variable_fields[1] if len(variable_fields) > 1 else None

        figure = Figure(figsize=(7.0, 7.0), constrained_layout=True)
        axis = figure.add_subplot(111)
        pool = result.candidate_pool
        recommendations = result.recommendations
        if y_field is None:
            scatter = axis.scatter(
                pool[x_field], pool["acquisition_score"],
                c=pool["normalized_uncertainty_percent"], cmap="viridis", alpha=0.65,
            )
            axis.scatter(
                recommendations[x_field], recommendations["acquisition_score"],
                marker="*", s=180, edgecolors="black", linewidths=0.8, label="Recommended",
            )
            axis.set_ylabel("Acquisition score (–)")
            figure.colorbar(scatter, ax=axis, label="Relative uncertainty (%)")
        else:
            scatter = axis.scatter(
                pool[x_field], pool[y_field], c=pool["acquisition_score"],
                cmap="viridis", alpha=0.45, s=24,
            )
            axis.scatter(
                recommendations[x_field], recommendations[y_field],
                marker="*", s=190, facecolors="none", edgecolors="black",
                linewidths=1.2, label="Recommended",
            )
            for _, row in recommendations.head(12).iterrows():
                axis.annotate(
                    str(int(row["recommendation_rank"])),
                    (row[x_field], row[y_field]),
                    xytext=(4, 4), textcoords="offset points", fontsize=8,
                )
            axis.set_ylabel(COLUMN_LABELS.get(y_field, y_field))
            figure.colorbar(scatter, ax=axis, label="Acquisition score (–)")
        axis.set_xlabel(COLUMN_LABELS.get(x_field, x_field))
        axis.set_title(f"{result.strategy}: recommended experiment region")
        axis.grid(True, alpha=0.22)
        axis.legend(loc="best")
        return figure

    @staticmethod
    def recommendation_figures(result: ActiveLearningRunResult) -> dict[str, Figure]:
        table = result.recommendations.sort_values("recommendation_rank")
        ranks = table["recommendation_rank"].to_numpy(dtype=int)
        mean = table["predicted_mean"].to_numpy(dtype=float)
        lower = table["lower_bound"].to_numpy(dtype=float)
        upper = table["upper_bound"].to_numpy(dtype=float)

        response_figure = Figure(figsize=(6.6, 5.8), constrained_layout=True)
        response_axis = response_figure.add_subplot(111)
        yerr = np.vstack([mean - lower, upper - mean])
        response_axis.errorbar(
            ranks, mean, yerr=yerr, fmt="o", capsize=3,
            label="Estimated response ± interval",
        )
        response_axis.set_xlabel("Recommendation rank")
        response_axis.set_ylabel(COLUMN_LABELS.get(result.response, result.response))
        response_axis.set_title("Estimated response and prediction interval")

        score_figure = Figure(figsize=(6.6, 5.8), constrained_layout=True)
        score_axis = score_figure.add_subplot(111)
        score_axis.plot(ranks, table["acquisition_score"], marker="o", label="Acquisition")
        score_axis.plot(ranks, table["novelty_score"], marker="s", label="Novelty")
        score_axis.plot(
            ranks,
            ActiveLearningService._minmax(table["normalized_uncertainty_percent"].to_numpy()),
            marker="^", label="Uncertainty",
        )
        score_axis.set_xlabel("Recommendation rank")
        score_axis.set_ylabel("Normalized score (–)")
        score_axis.set_ylim(-0.05, 1.05)
        score_axis.set_title("Priority components")
        figures = {"Response intervals": response_figure, "Priority scores": score_figure}
        for figure in figures.values():
            apply_chart_style(figure)
        return figures

    @staticmethod
    def recommendation_figure(result: ActiveLearningRunResult) -> Figure:
        """Backward-compatible combined recommendation view."""
        table = result.recommendations.sort_values("recommendation_rank")
        ranks = table["recommendation_rank"].to_numpy(dtype=int)
        mean = table["predicted_mean"].to_numpy(dtype=float)
        lower = table["lower_bound"].to_numpy(dtype=float)
        upper = table["upper_bound"].to_numpy(dtype=float)
        figure = Figure(figsize=(7.0, 7.0), constrained_layout=True)
        response_axis = figure.add_subplot(211)
        score_axis = figure.add_subplot(212)
        yerr = np.vstack([mean - lower, upper - mean])
        response_axis.errorbar(ranks, mean, yerr=yerr, fmt="o", capsize=3,
                               label="Estimated response ± interval")
        response_axis.set_ylabel(COLUMN_LABELS.get(result.response, result.response))
        response_axis.set_title("Estimated response and prediction interval")
        score_axis.plot(ranks, table["acquisition_score"], marker="o", label="Acquisition")
        score_axis.plot(ranks, table["novelty_score"], marker="s", label="Novelty")
        score_axis.plot(
            ranks, ActiveLearningService._minmax(table["normalized_uncertainty_percent"].to_numpy()),
            marker="^", label="Uncertainty",
        )
        score_axis.set_xlabel("Recommendation rank")
        score_axis.set_ylabel("Normalized score (–)")
        score_axis.set_ylim(-0.05, 1.05)
        apply_chart_style(figure)
        return figure

    @staticmethod
    def update_figure(result: UpdateComparisonResult) -> Figure:
        table = result.comparison.copy()
        figure = Figure(figsize=(7.0, 7.0), constrained_layout=True)
        axis = figure.add_subplot(111)
        positions = np.arange(len(table))
        width = 0.36
        axis.bar(positions - width / 2, table["before_update"], width, label="Before")
        axis.bar(positions + width / 2, table["after_update"], width, label="After")
        axis.set_xticks(positions)
        axis.set_xticklabels(table["metric"], rotation=35, ha="right")
        axis.set_title("Model metrics before and after completed experiments")
        axis.set_ylabel("Metric value (mixed units)")
        axis.grid(True, axis="y", alpha=0.22)
        axis.legend(loc="best")
        return figure

    @staticmethod
    def save_result(
        result: ActiveLearningRunResult,
        directory: Path | str,
        name: str | None = None,
    ) -> Path:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        stem = name or "__".join([
            "active_learning",
            ActiveLearningService._slug(result.response),
            ActiveLearningService._slug(result.strategy),
            timestamp,
        ])
        artifact_path = directory / f"{stem}.joblib"
        metadata_path = directory / f"{stem}.json"
        joblib.dump(result, artifact_path)
        metadata = dict(result.metadata)
        metadata["artifact_file"] = artifact_path.name
        metadata_path.write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return artifact_path

    @staticmethod
    def load_result(path: Path | str) -> ActiveLearningRunResult:
        result = joblib.load(Path(path))
        if not isinstance(result, ActiveLearningRunResult):
            raise ValueError("The selected file is not an active-learning run.")
        return result

    @staticmethod
    def list_saved_results(directory: Path | str) -> pd.DataFrame:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        rows: list[dict[str, Any]] = []
        for metadata_path in sorted(directory.glob("*.json"), reverse=True):
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                artifact_path = directory / metadata.get(
                    "artifact_file", metadata_path.with_suffix(".joblib").name
                )
                if not artifact_path.exists():
                    continue
                rows.append({
                    "created_at_utc": metadata.get("created_at_utc", ""),
                    "response": metadata.get("response", ""),
                    "method": metadata.get("method", ""),
                    "strategy": metadata.get("strategy", ""),
                    "direction": metadata.get("direction", ""),
                    "recommendations": metadata.get("recommendation_count", ""),
                    "candidates_evaluated": metadata.get("candidate_count", ""),
                    "artifact_path": str(artifact_path),
                })
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
        return pd.DataFrame(rows)

    @staticmethod
    def delete_result(path: Path | str) -> None:
        artifact_path = Path(path)
        metadata_path = artifact_path.with_suffix(".json")
        if artifact_path.exists():
            artifact_path.unlink()
        if metadata_path.exists():
            metadata_path.unlink()
