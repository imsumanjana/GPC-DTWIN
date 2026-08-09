"""Multi-objective optimisation, inverse design, and reusable run storage."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Iterable

import joblib
import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from scipy.stats import qmc

from gpc_dtwin import __version__
from gpc_dtwin.chart_style import apply_chart_style
from gpc_dtwin.columns import COLUMN_LABELS, MODEL_NUMERIC_PREDICTORS
from gpc_dtwin.services.digital_twin_service import DigitalTwinService, TwinBuildResult


OBJECTIVE_DIRECTIONS = ("Maximize", "Minimize")
TARGET_RELATIONS = ("At least", "At most", "Closest")
RELIABILITY_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3}


@dataclass(frozen=True)
class ObjectiveDefinition:
    response: str
    direction: str = "Maximize"
    weight: float = 1.0


@dataclass(frozen=True)
class ConstraintDefinition:
    response: str
    relation: str
    threshold: float


@dataclass(frozen=True)
class TargetDefinition:
    response: str
    relation: str
    target: float
    weight: float = 1.0


@dataclass(frozen=True)
class VariableDefinition:
    field: str
    lower: float
    upper: float


@dataclass
class OptimizationRunResult:
    run_type: str
    objectives: tuple[ObjectiveDefinition, ...]
    constraints: tuple[ConstraintDefinition, ...]
    variables: tuple[VariableDefinition, ...]
    predictors: tuple[str, ...]
    method: str
    confidence_percent: float
    population_size: int
    generations: int
    candidates_evaluated: int
    uncertainty_weight: float
    binder_closure: bool
    pareto_solutions: pd.DataFrame
    final_population: pd.DataFrame
    surrogate_summary: pd.DataFrame
    artifacts: dict[str, dict[str, Any]]
    metadata: dict[str, Any]


@dataclass
class InverseDesignResult:
    run_type: str
    targets: tuple[TargetDefinition, ...]
    variables: tuple[VariableDefinition, ...]
    predictors: tuple[str, ...]
    method: str
    confidence_percent: float
    candidates_evaluated: int
    uncertainty_weight: float
    binder_closure: bool
    recommendations: pd.DataFrame
    surrogate_summary: pd.DataFrame
    artifacts: dict[str, dict[str, Any]]
    metadata: dict[str, Any]


class OptimizationService:
    """Create Pareto fronts and inverse-design recommendations from fitted surrogates."""

    COMPOSITION_FIELDS = (
        "fa_percent_numeric", "ggbs_percent_numeric", "sf_percent_numeric"
    )

    @staticmethod
    def _slug(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")

    @staticmethod
    def _validate_variables(variables: Iterable[VariableDefinition]) -> tuple[VariableDefinition, ...]:
        items = tuple(variables)
        if not items:
            raise ValueError("Select at least one decision variable.")
        fields = [item.field for item in items]
        if len(fields) != len(set(fields)):
            raise ValueError("Decision variables must be unique.")
        for item in items:
            if item.field not in MODEL_NUMERIC_PREDICTORS:
                raise ValueError(f"Decision variable must be numeric: {item.field}")
            if not np.isfinite(item.lower) or not np.isfinite(item.upper):
                raise ValueError(f"Bounds must be finite for {item.field}.")
            if item.lower >= item.upper:
                raise ValueError(f"Lower bound must be below upper bound for {item.field}.")
        return items

    @staticmethod
    def _validate_objectives(
        objectives: Iterable[ObjectiveDefinition],
    ) -> tuple[ObjectiveDefinition, ...]:
        items = tuple(objectives)
        if not items:
            raise ValueError("Select at least one objective.")
        responses = [item.response for item in items]
        if len(responses) != len(set(responses)):
            raise ValueError("Each objective response must be unique.")
        for item in items:
            if item.direction not in OBJECTIVE_DIRECTIONS:
                raise ValueError(f"Unsupported objective direction: {item.direction}")
            if not np.isfinite(item.weight) or item.weight <= 0:
                raise ValueError("Objective weights must be positive.")
        return items

    @staticmethod
    def _validate_constraints(
        constraints: Iterable[ConstraintDefinition],
    ) -> tuple[ConstraintDefinition, ...]:
        items = tuple(constraints)
        for item in items:
            if item.relation not in ("At least", "At most"):
                raise ValueError(f"Unsupported constraint relation: {item.relation}")
            if not np.isfinite(item.threshold):
                raise ValueError("Constraint thresholds must be finite.")
        return items

    @staticmethod
    def _validate_targets(targets: Iterable[TargetDefinition]) -> tuple[TargetDefinition, ...]:
        items = tuple(targets)
        if not items:
            raise ValueError("Select at least one target.")
        responses = [item.response for item in items]
        if len(responses) != len(set(responses)):
            raise ValueError("Each target response must be unique.")
        for item in items:
            if item.relation not in TARGET_RELATIONS:
                raise ValueError(f"Unsupported target relation: {item.relation}")
            if not np.isfinite(item.target):
                raise ValueError("Target values must be finite.")
            if not np.isfinite(item.weight) or item.weight <= 0:
                raise ValueError("Target weights must be positive.")
        return items

    @staticmethod
    def default_bounds(dataframe: pd.DataFrame, fields: Iterable[str]) -> dict[str, tuple[float, float]]:
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
    def _validate_closure(
        cls, variables: tuple[VariableDefinition, ...], binder_closure: bool
    ) -> None:
        if not binder_closure:
            return
        fields = {item.field for item in variables}
        missing = [field for field in cls.COMPOSITION_FIELDS if field not in fields]
        if missing:
            raise ValueError(
                "Binder closure requires FA, GGBS, and SF to be decision variables."
            )
        lower_total = sum(
            next(item.lower for item in variables if item.field == field)
            for field in cls.COMPOSITION_FIELDS
        )
        upper_total = sum(
            next(item.upper for item in variables if item.field == field)
            for field in cls.COMPOSITION_FIELDS
        )
        if lower_total > 100.0 + 1e-9 or upper_total < 100.0 - 1e-9:
            raise ValueError("Binder bounds cannot satisfy FA + GGBS + SF = 100.")

    @staticmethod
    def _response_span(artifact: dict[str, Any]) -> float:
        limits = artifact["metadata"].get("response_training_range", [0.0, 1.0])
        return max(float(limits[1]) - float(limits[0]), 1e-9)

    @staticmethod
    def _response_specific_predictors(
        dataframe: pd.DataFrame,
        response: str,
        predictors: list[str],
        include_review_records: bool,
    ) -> tuple[list[str], list[str]]:
        """Return predictors that contain usable values for a response subset.

        Experimental tables often record different response families under different
        test conditions. A predictor such as AAS:B can therefore be valid for
        compressive-strength rows while being intentionally blank for flexural rows.
        Optimization must adapt each surrogate to its supported fields instead of
        rejecting the complete multi-response search.
        """
        if response not in dataframe.columns:
            raise ValueError(f"Response field is unavailable: {response}")
        mask = pd.to_numeric(dataframe[response], errors="coerce").notna()
        if "data_status" in dataframe.columns:
            states = dataframe["data_status"].astype("string").str.upper()
            mask &= states.ne("EXCLUDED")
            if not include_review_records:
                mask &= ~states.isin({"REQUIRES_REVIEW", "CONFLICTING"})
        subset = dataframe.loc[mask]
        usable: list[str] = []
        dropped: list[str] = []
        for predictor in dict.fromkeys(predictors):
            if predictor not in subset.columns:
                dropped.append(predictor)
                continue
            if predictor in MODEL_NUMERIC_PREDICTORS:
                values = pd.to_numeric(subset[predictor], errors="coerce")
                valid = values.notna().any()
            else:
                values = subset[predictor].astype("string").str.strip()
                valid = values.notna().any() and values.ne("").any()
            (usable if valid else dropped).append(predictor)
        if not usable:
            raise ValueError(
                f"No selected predictor has usable values for {COLUMN_LABELS.get(response, response)}."
            )
        return usable, dropped

    def _build_surrogates(
        self,
        dataframe: pd.DataFrame,
        responses: Iterable[str],
        predictors: list[str],
        method: str,
        confidence_percent: float,
        include_review_records: bool,
    ) -> tuple[dict[str, dict[str, Any]], pd.DataFrame]:
        unique_responses = list(dict.fromkeys(responses))
        if not unique_responses:
            raise ValueError("No response fields were selected.")
        artifacts: dict[str, dict[str, Any]] = {}
        rows: list[dict[str, Any]] = []
        twin_service = DigitalTwinService()
        for response in unique_responses:
            usable_predictors, dropped_predictors = self._response_specific_predictors(
                dataframe, response, predictors, include_review_records
            )
            result: TwinBuildResult = twin_service.build_twin(
                dataframe=dataframe,
                response=response,
                predictors=usable_predictors,
                method=method,
                confidence_percent=confidence_percent,
                include_review_records=include_review_records,
                group_column="mix_id",
            )
            result.artifact["metadata"]["selected_predictors"] = list(predictors)
            result.artifact["metadata"]["dropped_predictors"] = list(dropped_predictors)
            artifacts[response] = result.artifact
            rows.append({
                "response": response,
                "response_label": COLUMN_LABELS.get(response, response),
                "method": method,
                "observations": result.observations,
                "used_predictors": ", ".join(usable_predictors),
                "dropped_predictors": ", ".join(dropped_predictors),
                "rmse": result.metrics["rmse"],
                "mae": result.metrics["mae"],
                "r2": result.metrics["r2"],
                "coverage_percent": result.metrics["coverage_percent"],
                "normalized_rmse_percent": result.metrics["normalized_rmse_percent"],
                "calibration_gap_percent": result.metrics["calibration_gap_percent"],
            })
        return artifacts, pd.DataFrame(rows)

    @staticmethod
    def _sample_population(
        variables: tuple[VariableDefinition, ...], size: int, seed: int
    ) -> np.ndarray:
        sampler = qmc.LatinHypercube(d=len(variables), seed=seed)
        unit = sampler.random(n=size)
        lower = np.array([item.lower for item in variables], dtype=float)
        upper = np.array([item.upper for item in variables], dtype=float)
        return qmc.scale(unit, lower, upper)

    @classmethod
    def _repair_population(
        cls,
        population: np.ndarray,
        variables: tuple[VariableDefinition, ...],
        binder_closure: bool,
    ) -> np.ndarray:
        lower = np.array([item.lower for item in variables], dtype=float)
        upper = np.array([item.upper for item in variables], dtype=float)
        repaired = np.clip(np.asarray(population, dtype=float), lower, upper)
        if not binder_closure:
            return repaired

        field_to_index = {item.field: index for index, item in enumerate(variables)}
        indices = np.array([field_to_index[field] for field in cls.COMPOSITION_FIELDS], dtype=int)
        local_lower = lower[indices]
        local_upper = upper[indices]
        for row in repaired:
            values = np.clip(row[indices], local_lower, local_upper)
            for _ in range(20):
                difference = 100.0 - float(values.sum())
                if abs(difference) <= 1e-9:
                    break
                room = local_upper - values if difference > 0 else values - local_lower
                available = float(room.sum())
                if available <= 1e-12:
                    break
                step = min(abs(difference), available)
                values += np.sign(difference) * step * room / available
                values = np.clip(values, local_lower, local_upper)
            final_difference = 100.0 - float(values.sum())
            if abs(final_difference) > 1e-7:
                for local_index in np.argsort(-(local_upper - local_lower)):
                    candidate = values[local_index] + final_difference
                    clipped = float(np.clip(candidate, local_lower[local_index], local_upper[local_index]))
                    applied = clipped - values[local_index]
                    values[local_index] = clipped
                    final_difference -= applied
                    if abs(final_difference) <= 1e-7:
                        break
            row[indices] = values
        return repaired

    @staticmethod
    def _candidate_frame(
        population: np.ndarray,
        variables: tuple[VariableDefinition, ...],
        artifact: dict[str, Any],
    ) -> pd.DataFrame:
        metadata = artifact["metadata"]
        predictors = list(metadata["predictors"])
        defaults = metadata.get("input_defaults", {})
        frame = pd.DataFrame([{field: defaults.get(field) for field in predictors}] * len(population))
        for index, variable in enumerate(variables):
            if variable.field in frame.columns:
                frame[variable.field] = population[:, index]
        return frame

    def _evaluate_population(
        self,
        population: np.ndarray,
        variables: tuple[VariableDefinition, ...],
        artifacts: dict[str, dict[str, Any]],
    ) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
        table = pd.DataFrame(
            population,
            columns=[item.field for item in variables],
        )
        response_tables: dict[str, pd.DataFrame] = {}
        for response, artifact in artifacts.items():
            frame = self._candidate_frame(population, variables, artifact)
            predicted = DigitalTwinService.predict_dataframe(artifact, frame)
            response_tables[response] = predicted
            prefix = self._slug(response)
            table[f"{prefix}_estimate"] = predicted["predicted_mean"].to_numpy()
            table[f"{prefix}_std"] = predicted["prediction_std"].to_numpy()
            table[f"{prefix}_lower"] = predicted["lower_bound"].to_numpy()
            table[f"{prefix}_upper"] = predicted["upper_bound"].to_numpy()
            table[f"{prefix}_uncertainty_percent"] = predicted[
                "normalized_uncertainty_percent"
            ].to_numpy()
            table[f"{prefix}_reliability"] = predicted["reliability_class"].to_numpy()
            table[f"{prefix}_outside_range"] = predicted[
                "outside_training_range_count"
            ].to_numpy()
        reliability_columns = [column for column in table.columns if column.endswith("_reliability")]
        if reliability_columns:
            table["reliability_class"] = table[reliability_columns].apply(
                lambda row: max(row, key=lambda value: RELIABILITY_ORDER.get(str(value), 3)), axis=1
            )
        else:
            table["reliability_class"] = "D"
        return table, response_tables

    @staticmethod
    def _constraint_violation(
        table: pd.DataFrame,
        constraints: tuple[ConstraintDefinition, ...],
        artifacts: dict[str, dict[str, Any]],
    ) -> np.ndarray:
        violation = np.zeros(len(table), dtype=float)
        for item in constraints:
            prefix = OptimizationService._slug(item.response)
            values = table[f"{prefix}_estimate"].to_numpy(dtype=float)
            span = OptimizationService._response_span(artifacts[item.response])
            if item.relation == "At least":
                violation += np.maximum(0.0, item.threshold - values) / span
            else:
                violation += np.maximum(0.0, values - item.threshold) / span
        return violation

    @staticmethod
    def _objective_matrix(
        table: pd.DataFrame,
        objectives: tuple[ObjectiveDefinition, ...],
        uncertainty_weight: float,
    ) -> np.ndarray:
        matrix = np.zeros((len(table), len(objectives)), dtype=float)
        for column_index, item in enumerate(objectives):
            prefix = OptimizationService._slug(item.response)
            mean = table[f"{prefix}_estimate"].to_numpy(dtype=float)
            std = table[f"{prefix}_std"].to_numpy(dtype=float)
            if item.direction == "Maximize":
                matrix[:, column_index] = -(mean - uncertainty_weight * std)
            else:
                matrix[:, column_index] = mean + uncertainty_weight * std
        return matrix

    @staticmethod
    def _dominates(
        left: int,
        right: int,
        objective_matrix: np.ndarray,
        violation: np.ndarray,
    ) -> bool:
        left_violation = float(violation[left])
        right_violation = float(violation[right])
        if left_violation <= 1e-12 and right_violation > 1e-12:
            return True
        if left_violation > 1e-12 and right_violation <= 1e-12:
            return False
        if left_violation > 1e-12 and right_violation > 1e-12:
            return left_violation < right_violation - 1e-12
        left_values = objective_matrix[left]
        right_values = objective_matrix[right]
        return bool(
            np.all(left_values <= right_values + 1e-12)
            and np.any(left_values < right_values - 1e-12)
        )

    @classmethod
    def _non_dominated_sort(
        cls, objective_matrix: np.ndarray, violation: np.ndarray
    ) -> tuple[list[list[int]], np.ndarray]:
        size = len(objective_matrix)
        dominated: list[list[int]] = [[] for _ in range(size)]
        domination_count = np.zeros(size, dtype=int)
        fronts: list[list[int]] = [[]]
        for left in range(size):
            for right in range(left + 1, size):
                if cls._dominates(left, right, objective_matrix, violation):
                    dominated[left].append(right)
                    domination_count[right] += 1
                elif cls._dominates(right, left, objective_matrix, violation):
                    dominated[right].append(left)
                    domination_count[left] += 1
        for index in range(size):
            if domination_count[index] == 0:
                fronts[0].append(index)
        current = 0
        while current < len(fronts) and fronts[current]:
            next_front: list[int] = []
            for left in fronts[current]:
                for right in dominated[left]:
                    domination_count[right] -= 1
                    if domination_count[right] == 0:
                        next_front.append(right)
            if next_front:
                fronts.append(next_front)
            current += 1
        ranks = np.full(size, max(size, 1), dtype=int)
        for rank, front in enumerate(fronts):
            ranks[front] = rank
        return fronts, ranks

    @staticmethod
    def _crowding_distance(front: list[int], objective_matrix: np.ndarray) -> np.ndarray:
        distance = np.zeros(len(front), dtype=float)
        if len(front) <= 2:
            distance[:] = np.inf
            return distance
        front_values = objective_matrix[np.asarray(front)]
        for objective_index in range(front_values.shape[1]):
            order = np.argsort(front_values[:, objective_index], kind="stable")
            distance[order[0]] = np.inf
            distance[order[-1]] = np.inf
            minimum = float(front_values[order[0], objective_index])
            maximum = float(front_values[order[-1], objective_index])
            span = maximum - minimum
            if span <= 1e-12:
                continue
            for position in range(1, len(order) - 1):
                previous_value = front_values[order[position - 1], objective_index]
                next_value = front_values[order[position + 1], objective_index]
                distance[order[position]] += (next_value - previous_value) / span
        return distance

    @classmethod
    def _rank_and_crowding(
        cls, objective_matrix: np.ndarray, violation: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, list[list[int]]]:
        fronts, ranks = cls._non_dominated_sort(objective_matrix, violation)
        crowding = np.zeros(len(objective_matrix), dtype=float)
        for front in fronts:
            local = cls._crowding_distance(front, objective_matrix)
            for local_index, population_index in enumerate(front):
                crowding[population_index] = local[local_index]
        return ranks, crowding, fronts

    @staticmethod
    def _tournament(
        ranks: np.ndarray, crowding: np.ndarray, rng: np.random.Generator
    ) -> int:
        first, second = rng.integers(0, len(ranks), size=2)
        if ranks[first] < ranks[second]:
            return int(first)
        if ranks[second] < ranks[first]:
            return int(second)
        if crowding[first] > crowding[second]:
            return int(first)
        if crowding[second] > crowding[first]:
            return int(second)
        return int(first if rng.random() < 0.5 else second)

    @staticmethod
    def _sbx_pair(
        parent_a: np.ndarray,
        parent_b: np.ndarray,
        lower: np.ndarray,
        upper: np.ndarray,
        rng: np.random.Generator,
        eta: float = 15.0,
    ) -> tuple[np.ndarray, np.ndarray]:
        child_a = parent_a.copy()
        child_b = parent_b.copy()
        for index in range(len(parent_a)):
            if rng.random() > 0.5 or abs(parent_a[index] - parent_b[index]) <= 1e-14:
                continue
            x1, x2 = sorted((float(parent_a[index]), float(parent_b[index])))
            low, high = float(lower[index]), float(upper[index])
            random_value = rng.random()
            beta = 1.0 + 2.0 * (x1 - low) / max(x2 - x1, 1e-14)
            alpha = 2.0 - beta ** (-(eta + 1.0))
            if random_value <= 1.0 / alpha:
                beta_q = (random_value * alpha) ** (1.0 / (eta + 1.0))
            else:
                beta_q = (1.0 / (2.0 - random_value * alpha)) ** (1.0 / (eta + 1.0))
            value_a = 0.5 * ((x1 + x2) - beta_q * (x2 - x1))
            beta = 1.0 + 2.0 * (high - x2) / max(x2 - x1, 1e-14)
            alpha = 2.0 - beta ** (-(eta + 1.0))
            if random_value <= 1.0 / alpha:
                beta_q = (random_value * alpha) ** (1.0 / (eta + 1.0))
            else:
                beta_q = (1.0 / (2.0 - random_value * alpha)) ** (1.0 / (eta + 1.0))
            value_b = 0.5 * ((x1 + x2) + beta_q * (x2 - x1))
            if rng.random() < 0.5:
                value_a, value_b = value_b, value_a
            child_a[index] = np.clip(value_a, low, high)
            child_b[index] = np.clip(value_b, low, high)
        return child_a, child_b

    @staticmethod
    def _mutate(
        child: np.ndarray,
        lower: np.ndarray,
        upper: np.ndarray,
        rng: np.random.Generator,
        eta: float = 20.0,
    ) -> np.ndarray:
        result = child.copy()
        probability = 1.0 / max(len(result), 1)
        for index in range(len(result)):
            if rng.random() > probability:
                continue
            low, high = float(lower[index]), float(upper[index])
            span = high - low
            if span <= 1e-14:
                continue
            value = float(result[index])
            delta1 = (value - low) / span
            delta2 = (high - value) / span
            random_value = rng.random()
            mutation_power = 1.0 / (eta + 1.0)
            if random_value < 0.5:
                xy = 1.0 - delta1
                value_q = 2.0 * random_value + (1.0 - 2.0 * random_value) * xy ** (eta + 1.0)
                delta_q = value_q ** mutation_power - 1.0
            else:
                xy = 1.0 - delta2
                value_q = 2.0 * (1.0 - random_value) + 2.0 * (random_value - 0.5) * xy ** (eta + 1.0)
                delta_q = 1.0 - value_q ** mutation_power
            result[index] = np.clip(value + delta_q * span, low, high)
        return result

    @staticmethod
    def _compromise_scores(
        table: pd.DataFrame,
        objectives: tuple[ObjectiveDefinition, ...],
        uncertainty_weight: float,
        violation: np.ndarray,
    ) -> np.ndarray:
        weights = np.array([item.weight for item in objectives], dtype=float)
        weights /= weights.sum()
        score = np.zeros(len(table), dtype=float)
        relative_uncertainty = np.zeros(len(table), dtype=float)
        for index, item in enumerate(objectives):
            prefix = OptimizationService._slug(item.response)
            values = table[f"{prefix}_estimate"].to_numpy(dtype=float)
            minimum, maximum = float(np.min(values)), float(np.max(values))
            span = max(maximum - minimum, 1e-12)
            if item.direction == "Maximize":
                normalized = (values - minimum) / span
            else:
                normalized = (maximum - values) / span
            score += weights[index] * normalized
            relative_uncertainty += weights[index] * (
                table[f"{prefix}_uncertainty_percent"].to_numpy(dtype=float) / 100.0
            )
        score -= min(float(uncertainty_weight), 3.0) * 0.15 * relative_uncertainty
        score -= np.minimum(np.asarray(violation, dtype=float), 2.0) * 0.5
        return score

    def optimize(
        self,
        dataframe: pd.DataFrame,
        objectives: Iterable[ObjectiveDefinition],
        constraints: Iterable[ConstraintDefinition],
        variables: Iterable[VariableDefinition],
        predictors: list[str],
        method: str = "Random Forest",
        confidence_percent: float = 95.0,
        population_size: int = 64,
        generations: int = 20,
        uncertainty_weight: float = 0.5,
        binder_closure: bool = True,
        include_review_records: bool = False,
        seed: int = 42,
    ) -> OptimizationRunResult:
        objective_items = self._validate_objectives(objectives)
        constraint_items = self._validate_constraints(constraints)
        variable_items = self._validate_variables(variables)
        self._validate_closure(variable_items, binder_closure)
        predictors = list(dict.fromkeys(predictors))
        if not predictors:
            raise ValueError("Select at least one surrogate input.")
        missing_variables = [item.field for item in variable_items if item.field not in predictors]
        if missing_variables:
            raise ValueError(
                "Decision variables must also be surrogate inputs: " + ", ".join(missing_variables)
            )
        population_size = int(np.clip(population_size, 16, 300))
        if population_size % 2:
            population_size += 1
        generations = int(np.clip(generations, 1, 150))
        uncertainty_weight = float(np.clip(uncertainty_weight, 0.0, 3.0))

        responses = [item.response for item in objective_items] + [
            item.response for item in constraint_items
        ]
        artifacts, surrogate_summary = self._build_surrogates(
            dataframe, responses, predictors, method, confidence_percent, include_review_records
        )

        rng = np.random.default_rng(seed)
        lower = np.array([item.lower for item in variable_items], dtype=float)
        upper = np.array([item.upper for item in variable_items], dtype=float)
        population = self._sample_population(variable_items, population_size, seed)
        population = self._repair_population(population, variable_items, binder_closure)
        evaluated_count = 0

        table, _ = self._evaluate_population(population, variable_items, artifacts)
        evaluated_count += len(population)
        objective_matrix = self._objective_matrix(table, objective_items, uncertainty_weight)
        violation = self._constraint_violation(table, constraint_items, artifacts)

        for _ in range(generations):
            ranks, crowding, _ = self._rank_and_crowding(objective_matrix, violation)
            offspring_rows: list[np.ndarray] = []
            while len(offspring_rows) < population_size:
                parent_a = population[self._tournament(ranks, crowding, rng)]
                parent_b = population[self._tournament(ranks, crowding, rng)]
                child_a, child_b = self._sbx_pair(parent_a, parent_b, lower, upper, rng)
                offspring_rows.append(self._mutate(child_a, lower, upper, rng))
                if len(offspring_rows) < population_size:
                    offspring_rows.append(self._mutate(child_b, lower, upper, rng))
            offspring = self._repair_population(
                np.asarray(offspring_rows[:population_size]), variable_items, binder_closure
            )
            combined = np.vstack([population, offspring])
            combined_table, _ = self._evaluate_population(combined, variable_items, artifacts)
            evaluated_count += len(offspring)
            combined_objectives = self._objective_matrix(
                combined_table, objective_items, uncertainty_weight
            )
            combined_violation = self._constraint_violation(
                combined_table, constraint_items, artifacts
            )
            _, _, fronts = self._rank_and_crowding(combined_objectives, combined_violation)
            selected: list[int] = []
            for front in fronts:
                if len(selected) + len(front) <= population_size:
                    selected.extend(front)
                    continue
                local_distance = self._crowding_distance(front, combined_objectives)
                local_order = np.argsort(-local_distance, kind="stable")
                remaining = population_size - len(selected)
                selected.extend([front[index] for index in local_order[:remaining]])
                break
            selected_indices = np.asarray(selected, dtype=int)
            population = combined[selected_indices]
            table = combined_table.iloc[selected_indices].reset_index(drop=True)
            objective_matrix = combined_objectives[selected_indices]
            violation = combined_violation[selected_indices]

        ranks, crowding, fronts = self._rank_and_crowding(objective_matrix, violation)
        table = table.copy()
        table["constraint_violation"] = violation
        table["feasible"] = violation <= 1e-12
        table["pareto_rank"] = ranks
        table["crowding_distance"] = crowding
        table["compromise_score"] = self._compromise_scores(
            table, objective_items, uncertainty_weight, violation
        )

        feasible_front = table.loc[(table["pareto_rank"] == 0) & table["feasible"]].copy()
        if feasible_front.empty:
            minimum_violation = float(table["constraint_violation"].min())
            feasible_front = table.loc[
                np.isclose(table["constraint_violation"], minimum_violation)
                & (table["pareto_rank"] == table.loc[
                    np.isclose(table["constraint_violation"], minimum_violation), "pareto_rank"
                ].min())
            ].copy()
        pareto = feasible_front.sort_values(
            ["compromise_score", "constraint_violation"], ascending=[False, True]
        ).reset_index(drop=True)
        pareto.insert(0, "solution_rank", np.arange(1, len(pareto) + 1))
        final_population = table.sort_values(
            ["pareto_rank", "constraint_violation", "compromise_score"],
            ascending=[True, True, False],
        ).reset_index(drop=True)

        metadata = {
            "format_version": 1,
            "artifact_type": "multi_objective_optimization",
            "application_version": __version__,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "method": method,
            "search_algorithm": "Constraint-aware NSGA-II",
            "confidence_percent": float(confidence_percent),
            "population_size": population_size,
            "generations": generations,
            "candidates_evaluated": int(evaluated_count),
            "uncertainty_weight": uncertainty_weight,
            "binder_closure": bool(binder_closure),
            "objectives": [asdict(item) for item in objective_items],
            "constraints": [asdict(item) for item in constraint_items],
            "variables": [asdict(item) for item in variable_items],
            "predictors": predictors,
            "seed": int(seed),
            "pareto_solutions": len(pareto),
            "feasible_population": int(table["feasible"].sum()),
        }
        return OptimizationRunResult(
            run_type="multi_objective_optimization",
            objectives=objective_items,
            constraints=constraint_items,
            variables=variable_items,
            predictors=tuple(predictors),
            method=method,
            confidence_percent=float(confidence_percent),
            population_size=population_size,
            generations=generations,
            candidates_evaluated=evaluated_count,
            uncertainty_weight=uncertainty_weight,
            binder_closure=bool(binder_closure),
            pareto_solutions=pareto,
            final_population=final_population,
            surrogate_summary=surrogate_summary,
            artifacts=artifacts,
            metadata=metadata,
        )

    @staticmethod
    def _target_loss(
        values: np.ndarray,
        target: TargetDefinition,
        span: float,
    ) -> np.ndarray:
        if target.relation == "At least":
            return np.maximum(0.0, target.target - values) / span
        if target.relation == "At most":
            return np.maximum(0.0, values - target.target) / span
        return np.abs(values - target.target) / span

    @staticmethod
    def _select_diverse(
        table: pd.DataFrame,
        variables: tuple[VariableDefinition, ...],
        count: int,
    ) -> pd.DataFrame:
        ordered = table.sort_values("design_loss", ascending=True).reset_index(drop=True)
        if len(ordered) <= count:
            return ordered
        fields = [item.field for item in variables]
        lower = np.array([item.lower for item in variables], dtype=float)
        upper = np.array([item.upper for item in variables], dtype=float)
        span = np.maximum(upper - lower, 1e-12)
        normalized = (ordered[fields].to_numpy(dtype=float) - lower) / span
        selected = [0]
        threshold = 0.06
        for index in range(1, len(ordered)):
            distance = np.linalg.norm(normalized[index] - normalized[selected], axis=1)
            if float(distance.min()) >= threshold:
                selected.append(index)
            if len(selected) >= count:
                break
        if len(selected) < count:
            for index in range(len(ordered)):
                if index not in selected:
                    selected.append(index)
                if len(selected) >= count:
                    break
        return ordered.iloc[selected[:count]].reset_index(drop=True)

    def inverse_design(
        self,
        dataframe: pd.DataFrame,
        targets: Iterable[TargetDefinition],
        variables: Iterable[VariableDefinition],
        predictors: list[str],
        method: str = "Random Forest",
        confidence_percent: float = 95.0,
        candidate_count: int = 2500,
        recommendation_count: int = 20,
        uncertainty_weight: float = 0.5,
        binder_closure: bool = True,
        include_review_records: bool = False,
        seed: int = 42,
    ) -> InverseDesignResult:
        target_items = self._validate_targets(targets)
        variable_items = self._validate_variables(variables)
        self._validate_closure(variable_items, binder_closure)
        predictors = list(dict.fromkeys(predictors))
        missing_variables = [item.field for item in variable_items if item.field not in predictors]
        if missing_variables:
            raise ValueError(
                "Decision variables must also be surrogate inputs: " + ", ".join(missing_variables)
            )
        candidate_count = int(np.clip(candidate_count, 200, 50000))
        recommendation_count = int(np.clip(recommendation_count, 3, 100))
        uncertainty_weight = float(np.clip(uncertainty_weight, 0.0, 3.0))

        artifacts, surrogate_summary = self._build_surrogates(
            dataframe,
            [item.response for item in target_items],
            predictors,
            method,
            confidence_percent,
            include_review_records,
        )
        population = self._sample_population(variable_items, candidate_count, seed)
        population = self._repair_population(population, variable_items, binder_closure)
        table, _ = self._evaluate_population(population, variable_items, artifacts)

        weights = np.array([item.weight for item in target_items], dtype=float)
        weights /= weights.sum()
        total_loss = np.zeros(len(table), dtype=float)
        uncertainty_loss = np.zeros(len(table), dtype=float)
        satisfied_count = np.zeros(len(table), dtype=int)
        for index, item in enumerate(target_items):
            prefix = self._slug(item.response)
            values = table[f"{prefix}_estimate"].to_numpy(dtype=float)
            std = table[f"{prefix}_std"].to_numpy(dtype=float)
            span = self._response_span(artifacts[item.response])
            loss = self._target_loss(values, item, span)
            total_loss += weights[index] * loss
            uncertainty_loss += weights[index] * std / span
            if item.relation == "At least":
                satisfied_count += values >= item.target
            elif item.relation == "At most":
                satisfied_count += values <= item.target
            else:
                satisfied_count += np.abs(values - item.target) <= 0.05 * span

        reliability_penalty = table["reliability_class"].map(
            {"A": 0.0, "B": 0.03, "C": 0.10, "D": 0.25}
        ).fillna(0.25).to_numpy(dtype=float)
        outside_columns = [column for column in table.columns if column.endswith("_outside_range")]
        outside_penalty = (
            table[outside_columns].sum(axis=1).to_numpy(dtype=float) * 0.20
            if outside_columns else np.zeros(len(table), dtype=float)
        )
        design_loss = (
            total_loss
            + uncertainty_weight * 0.20 * uncertainty_loss
            + reliability_penalty
            + outside_penalty
        )
        table["target_loss"] = total_loss
        table["uncertainty_penalty"] = uncertainty_weight * 0.20 * uncertainty_loss
        table["design_loss"] = design_loss
        table["targets_satisfied"] = satisfied_count
        table["target_count"] = len(target_items)
        table["target_satisfaction_percent"] = satisfied_count / len(target_items) * 100.0

        recommendations = self._select_diverse(table, variable_items, recommendation_count)
        recommendations.insert(0, "recommendation_rank", np.arange(1, len(recommendations) + 1))
        metadata = {
            "format_version": 1,
            "artifact_type": "inverse_design",
            "application_version": __version__,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "method": method,
            "confidence_percent": float(confidence_percent),
            "candidates_evaluated": candidate_count,
            "uncertainty_weight": uncertainty_weight,
            "binder_closure": bool(binder_closure),
            "targets": [asdict(item) for item in target_items],
            "variables": [asdict(item) for item in variable_items],
            "predictors": predictors,
            "seed": int(seed),
            "recommendations": len(recommendations),
        }
        return InverseDesignResult(
            run_type="inverse_design",
            targets=target_items,
            variables=variable_items,
            predictors=tuple(predictors),
            method=method,
            confidence_percent=float(confidence_percent),
            candidates_evaluated=candidate_count,
            uncertainty_weight=uncertainty_weight,
            binder_closure=bool(binder_closure),
            recommendations=recommendations,
            surrogate_summary=surrogate_summary,
            artifacts=artifacts,
            metadata=metadata,
        )

    @staticmethod
    def pareto_figure(result: OptimizationRunResult) -> Figure:
        objectives = result.objectives
        population = result.final_population
        pareto = result.pareto_solutions
        figure = Figure(figsize=(10.8, 5.6), constrained_layout=True)
        if len(objectives) == 1:
            axis = figure.add_subplot(111)
            prefix = OptimizationService._slug(objectives[0].response)
            axis.hist(population[f"{prefix}_estimate"], bins=18, alpha=0.7)
            axis.axvline(pareto.iloc[0][f"{prefix}_estimate"], linestyle="--", linewidth=1.5)
            axis.set_xlabel(COLUMN_LABELS.get(objectives[0].response, objectives[0].response))
            axis.set_ylabel("Candidates (count)")
            axis.set_title("Objective distribution")
            axis.grid(True, axis="y", alpha=0.25)
            return figure

        first, second = objectives[:2]
        first_column = f"{OptimizationService._slug(first.response)}_estimate"
        second_column = f"{OptimizationService._slug(second.response)}_estimate"
        if len(objectives) == 2:
            axis = figure.add_subplot(111)
            feasible = population["feasible"].astype(bool)
            axis.scatter(
                population.loc[~feasible, first_column],
                population.loc[~feasible, second_column],
                marker="x", alpha=0.35, label="Constraint-limited"
            )
            axis.scatter(
                population.loc[feasible, first_column],
                population.loc[feasible, second_column],
                alpha=0.30, label="Feasible population"
            )
            plot = axis.scatter(
                pareto[first_column], pareto[second_column],
                c=pareto["compromise_score"], s=60, label="Pareto solutions"
            )
            figure.colorbar(plot, ax=axis, label="Compromise score (–)")
            if not pareto.empty:
                axis.scatter(
                    pareto.iloc[0][first_column], pareto.iloc[0][second_column],
                    marker="*", s=220, label="Recommended compromise"
                )
            axis.set_xlabel(COLUMN_LABELS.get(first.response, first.response))
            axis.set_ylabel(COLUMN_LABELS.get(second.response, second.response))
            axis.set_title("Pareto trade-off")
            axis.legend(loc="best")
            axis.grid(True, alpha=0.25)
            return figure

        third = objectives[2]
        third_column = f"{OptimizationService._slug(third.response)}_estimate"
        axis = figure.add_subplot(111, projection="3d")
        plot = axis.scatter(
            pareto[first_column], pareto[second_column], pareto[third_column],
            c=pareto["compromise_score"], s=55
        )
        figure.colorbar(plot, ax=axis, shrink=0.72, label="Compromise score (–)")
        axis.set_xlabel(COLUMN_LABELS.get(first.response, first.response))
        axis.set_ylabel(COLUMN_LABELS.get(second.response, second.response))
        axis.set_zlabel(COLUMN_LABELS.get(third.response, third.response))
        axis.set_title("Three-objective Pareto front")
        return figure

    @staticmethod
    def parallel_figure(result: OptimizationRunResult) -> Figure:
        pareto = result.pareto_solutions.head(40)
        figure = Figure(figsize=(11.0, 5.2), constrained_layout=True)
        axis = figure.add_subplot(111)
        if pareto.empty:
            axis.text(0.5, 0.5, "No solutions", ha="center", va="center")
            axis.set_axis_off()
            return figure
        columns: list[str] = []
        labels: list[str] = []
        for item in result.variables:
            columns.append(item.field)
            labels.append(COLUMN_LABELS.get(item.field, item.field))
        for item in result.objectives:
            columns.append(f"{OptimizationService._slug(item.response)}_estimate")
            labels.append(COLUMN_LABELS.get(item.response, item.response))
        matrix = pareto[columns].to_numpy(dtype=float)
        minimum = np.nanmin(matrix, axis=0)
        maximum = np.nanmax(matrix, axis=0)
        span = np.maximum(maximum - minimum, 1e-12)
        normalized = (matrix - minimum) / span
        x = np.arange(len(columns))
        scores = pareto["compromise_score"].to_numpy(dtype=float)
        for row, score in zip(normalized, scores):
            axis.plot(x, row, alpha=0.25 + 0.6 * max(0.0, min(1.0, score)))
        best = normalized[0]
        axis.plot(x, best, linewidth=3.0, marker="o", label="Recommended compromise")
        axis.set_xticks(x, labels, rotation=25, ha="right")
        axis.set_ylim(-0.05, 1.05)
        axis.set_ylabel("Normalized value (–)")
        axis.set_title("Pareto solution profiles")
        axis.grid(True, alpha=0.25)
        axis.legend(loc="best")
        return figure

    @staticmethod
    def inverse_figures(result: InverseDesignResult) -> dict[str, Figure]:
        table = result.recommendations.head(15)
        ranks = table["recommendation_rank"].to_numpy(dtype=int)

        score_figure = Figure(figsize=(6.6, 5.8), constrained_layout=True)
        score_axis = score_figure.add_subplot(111)
        score_axis.barh(
            ranks.astype(str), table["design_loss"].to_numpy(dtype=float),
            label="Design loss",
        )
        score_axis.invert_yaxis()
        score_axis.set_xlabel("Design loss (–)")
        score_axis.set_ylabel("Recommendation rank")
        score_axis.set_title("Ranked alternatives")

        ratios: list[np.ndarray] = []
        labels: list[str] = []
        for target in result.targets:
            prefix = OptimizationService._slug(target.response)
            values = table[f"{prefix}_estimate"].to_numpy(dtype=float)
            span = OptimizationService._response_span(result.artifacts[target.response])
            if target.relation == "At least":
                satisfaction = 1.0 - np.maximum(0.0, target.target - values) / span
            elif target.relation == "At most":
                satisfaction = 1.0 - np.maximum(0.0, values - target.target) / span
            else:
                satisfaction = 1.0 - np.abs(values - target.target) / span
            ratios.append(np.clip(satisfaction, 0.0, 1.0))
            labels.append(COLUMN_LABELS.get(target.response, target.response))

        heat_figure = Figure(figsize=(6.6, 5.8), constrained_layout=True)
        heat_axis = heat_figure.add_subplot(111)
        matrix = np.vstack(ratios)
        image = heat_axis.imshow(matrix, aspect="auto", vmin=0.0, vmax=1.0, cmap="RdYlGn")
        heat_axis.set_yticks(np.arange(len(labels)), labels)
        heat_axis.set_xticks(np.arange(len(table)), table["recommendation_rank"].astype(str))
        heat_axis.set_xlabel("Recommendation rank")
        heat_axis.set_title("Target attainment")
        heat_figure.colorbar(image, ax=heat_axis, label="Normalized attainment (–)")
        figures = {"Ranked alternatives": score_figure, "Target attainment": heat_figure}
        for figure in figures.values():
            apply_chart_style(figure)
        return figures

    @staticmethod
    def inverse_figure(result: InverseDesignResult) -> Figure:
        """Backward-compatible combined inverse-design figure."""
        table = result.recommendations.head(15)
        figure = Figure(figsize=(11.0, 5.2), constrained_layout=True)
        score_axis = figure.add_subplot(121)
        heat_axis = figure.add_subplot(122)
        ranks = table["recommendation_rank"].to_numpy(dtype=int)
        score_axis.barh(ranks.astype(str), table["design_loss"].to_numpy(dtype=float), label="Design loss")
        score_axis.invert_yaxis(); score_axis.set_xlabel("Design loss (–)")
        score_axis.set_ylabel("Recommendation rank"); score_axis.set_title("Ranked alternatives")
        ratios: list[np.ndarray] = []
        labels: list[str] = []
        for target in result.targets:
            prefix = OptimizationService._slug(target.response)
            values = table[f"{prefix}_estimate"].to_numpy(dtype=float)
            span = OptimizationService._response_span(result.artifacts[target.response])
            if target.relation == "At least":
                satisfaction = 1.0 - np.maximum(0.0, target.target - values) / span
            elif target.relation == "At most":
                satisfaction = 1.0 - np.maximum(0.0, values - target.target) / span
            else:
                satisfaction = 1.0 - np.abs(values - target.target) / span
            ratios.append(np.clip(satisfaction, 0.0, 1.0))
            labels.append(COLUMN_LABELS.get(target.response, target.response))
        matrix = np.vstack(ratios)
        image = heat_axis.imshow(matrix, aspect="auto", vmin=0.0, vmax=1.0, cmap="RdYlGn")
        heat_axis.set_yticks(np.arange(len(labels)), labels)
        heat_axis.set_xticks(np.arange(len(table)), table["recommendation_rank"].astype(str))
        heat_axis.set_xlabel("Recommendation rank"); heat_axis.set_title("Target attainment")
        figure.colorbar(image, ax=heat_axis, label="Normalized attainment (–)")
        apply_chart_style(figure)
        return figure

    @staticmethod
    def save_result(
        result: OptimizationRunResult | InverseDesignResult,
        directory: Path | str,
        name: str | None = None,
    ) -> Path:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        created = result.metadata.get("created_at_utc", datetime.now(timezone.utc).isoformat())
        timestamp = re.sub(r"[^0-9]", "", created)[:14]
        default_name = f"{result.run_type}_{timestamp}"
        stem = OptimizationService._slug(name or default_name)
        artifact_path = directory / f"{stem}.joblib"
        metadata_path = directory / f"{stem}.json"
        joblib.dump(result, artifact_path)
        metadata = dict(result.metadata)
        metadata["artifact_path"] = artifact_path.name
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        if isinstance(result, OptimizationRunResult):
            result.pareto_solutions.to_csv(directory / f"{stem}_solutions.csv", index=False)
        else:
            result.recommendations.to_csv(directory / f"{stem}_solutions.csv", index=False)
        result.surrogate_summary.to_csv(directory / f"{stem}_surrogates.csv", index=False)
        return artifact_path

    @staticmethod
    def load_result(path: Path | str) -> OptimizationRunResult | InverseDesignResult:
        result = joblib.load(Path(path))
        if not isinstance(result, (OptimizationRunResult, InverseDesignResult)):
            raise ValueError("The selected run file is not compatible.")
        return result

    @staticmethod
    def list_saved_results(directory: Path | str) -> pd.DataFrame:
        directory = Path(directory)
        rows: list[dict[str, Any]] = []
        if not directory.exists():
            return pd.DataFrame()
        for metadata_path in sorted(directory.glob("*.json")):
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            artifact_path = Path(metadata.get("artifact_path", metadata_path.with_suffix(".joblib")))
            if not artifact_path.is_absolute() or not artifact_path.exists():
                artifact_path = directory / artifact_path.name
            rows.append({
                "run_type": metadata.get("artifact_type", ""),
                "method": metadata.get("method", ""),
                "created_at_utc": metadata.get("created_at_utc", ""),
                "candidates_evaluated": metadata.get("candidates_evaluated", ""),
                "solutions": metadata.get("pareto_solutions", metadata.get("recommendations", "")),
                "artifact_path": str(artifact_path),
            })
        return pd.DataFrame(rows)

    @staticmethod
    def delete_result(path: Path | str) -> None:
        artifact_path = Path(path)
        stem = artifact_path.stem
        directory = artifact_path.parent
        for candidate in (
            artifact_path,
            directory / f"{stem}.json",
            directory / f"{stem}_solutions.csv",
            directory / f"{stem}_surrogates.csv",
        ):
            if candidate.exists():
                candidate.unlink()
