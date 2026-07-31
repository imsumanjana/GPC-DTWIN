"""Non-destructive-test fusion and durability assessment utilities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Callable

import joblib
import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold, LeaveOneGroupOut, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR

from gpc_dtwin import __version__
from gpc_dtwin.columns import COLUMN_LABELS
from gpc_dtwin.services.digital_twin_service import DigitalTwinService, TwinBuildResult


REVIEW_STATES = {"REQUIRES_REVIEW", "CONFLICTING"}

NDT_FEATURE_SETS: dict[str, tuple[str, ...]] = {
    "UPV only": ("upv_m_s",),
    "Rebound only": ("rebound_estimated_strength_mpa",),
    "UPV + Rebound": ("upv_m_s", "rebound_estimated_strength_mpa"),
    "Composition only": (
        "fa_percent_numeric", "ggbs_percent_numeric", "sf_percent_numeric"
    ),
    "Composition + NDT": (
        "fa_percent_numeric", "ggbs_percent_numeric", "sf_percent_numeric",
        "upv_m_s", "rebound_estimated_strength_mpa",
    ),
}

NDT_ALGORITHMS: dict[str, Callable[[], Any]] = {
    "Ridge Regression": lambda: Ridge(alpha=1.0),
    "Support Vector Regression": lambda: SVR(kernel="rbf", C=20.0, epsilon=0.08),
    "Random Forest": lambda: RandomForestRegressor(
        n_estimators=240, min_samples_leaf=1, random_state=42, n_jobs=1
    ),
    "Gradient Boosting": lambda: GradientBoostingRegressor(
        n_estimators=180, learning_rate=0.035, max_depth=2, loss="huber", random_state=42
    ),
}

DURABILITY_RESPONSES = [
    "residual_compressive_strength_mpa",
    "strength_loss_percent_derived",
    "mass_change_percent_derived",
    "strength_retention_percent",
]

DURABILITY_DEFAULT_PREDICTORS = [
    "fa_percent_numeric", "ggbs_percent_numeric", "sf_percent_numeric",
    "initial_compressive_strength_mpa", "acid_type",
    "acid_concentration_percent", "acid_exposure_days",
]


@dataclass
class NDTFusionResult:
    algorithm: str
    observations: int
    reference_group: str
    reference_age_days: float | None
    curing_keyword: str
    cv_method: str
    rankings: pd.DataFrame
    predictions: pd.DataFrame
    matched_data: pd.DataFrame
    best_feature_set: str
    best_metrics: dict[str, float]
    feature_influence: pd.DataFrame
    artifacts: dict[str, dict[str, Any]]


@dataclass
class DurabilityProfileResult:
    records: int
    media: int
    mixes: int
    strength_weight: float
    mass_weight: float
    mass_penalty: float
    ranking: pd.DataFrame
    best_mix: str
    best_score: float
    mean_retention: float
    maximum_strength_loss: float


class NDTDurabilityService:
    """Specialised analysis for NDT fusion and exposure-performance records."""

    @staticmethod
    def ndt_algorithm_names() -> list[str]:
        return list(NDT_ALGORITHMS)

    @staticmethod
    def ndt_feature_set_names() -> list[str]:
        return list(NDT_FEATURE_SETS)

    @staticmethod
    def durability_response_names() -> list[str]:
        return list(DURABILITY_RESPONSES)

    @staticmethod
    def _slug(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")

    @staticmethod
    def _filter_status(dataframe: pd.DataFrame, include_review_records: bool) -> pd.DataFrame:
        frame = dataframe.copy()
        if "data_status" not in frame.columns:
            return frame
        states = frame["data_status"].astype("string").str.upper()
        keep = states.ne("EXCLUDED")
        if not include_review_records:
            keep &= ~states.isin(REVIEW_STATES)
        return frame.loc[keep].copy()

    @staticmethod
    def available_reference_groups(dataframe: pd.DataFrame) -> list[str]:
        if "record_group" not in dataframe.columns or "compressive_strength_mpa" not in dataframe.columns:
            return []
        strength = pd.to_numeric(dataframe["compressive_strength_mpa"], errors="coerce")
        values = (
            dataframe.loc[strength.notna(), "record_group"]
            .dropna().astype(str).str.strip()
        )
        return sorted(value for value in values.unique().tolist() if value)

    @classmethod
    def prepare_ndt_matched_data(
        cls,
        dataframe: pd.DataFrame,
        reference_group: str = "AMBIENT_28D_MECHANICAL",
        reference_age_days: float | None = 28.0,
        curing_keyword: str = "Ambient",
        include_review_records: bool = True,
    ) -> pd.DataFrame:
        """Match destructive strength and NDT readings by mix identity."""
        required = {
            "mix_id", "compressive_strength_mpa", "upv_m_s",
            "rebound_estimated_strength_mpa",
        }
        missing = sorted(required.difference(dataframe.columns))
        if missing:
            raise ValueError("Required NDT fields are unavailable: " + ", ".join(missing))

        filtered = cls._filter_status(dataframe, include_review_records)
        mechanical = filtered[pd.to_numeric(
            filtered["compressive_strength_mpa"], errors="coerce"
        ).notna()].copy()

        if reference_group:
            if "record_group" not in mechanical.columns:
                raise ValueError("Record-group filtering is unavailable in this dataset.")
            mechanical = mechanical[
                mechanical["record_group"].astype(str).eq(reference_group)
            ].copy()

        if reference_age_days is not None and "mechanical_test_age_days" in mechanical.columns:
            ages = pd.to_numeric(mechanical["mechanical_test_age_days"], errors="coerce")
            mechanical = mechanical[np.isclose(ages, float(reference_age_days), atol=1e-6)].copy()

        keyword = curing_keyword.strip()
        if keyword and "curing_regime" in mechanical.columns:
            mechanical = mechanical[
                mechanical["curing_regime"].astype("string").str.contains(
                    keyword, case=False, na=False, regex=False
                )
            ].copy()

        if mechanical.empty:
            raise ValueError("No destructive-strength records match the selected reference condition.")

        ndt_mask = (
            pd.to_numeric(filtered["upv_m_s"], errors="coerce").notna()
            | pd.to_numeric(filtered["rebound_estimated_strength_mpa"], errors="coerce").notna()
        )
        ndt = filtered.loc[ndt_mask].copy()
        if ndt.empty:
            raise ValueError("No usable NDT records are available.")

        composition = [
            column for column in (
                "fa_percent_numeric", "ggbs_percent_numeric", "sf_percent_numeric"
            ) if column in filtered.columns
        ]
        for frame in (mechanical, ndt):
            for column in [
                "compressive_strength_mpa", "upv_m_s",
                "rebound_estimated_strength_mpa", *composition,
            ]:
                if column in frame.columns:
                    frame[column] = pd.to_numeric(frame[column], errors="coerce")

        mechanical_columns = ["mix_id", "compressive_strength_mpa", *composition]
        mechanical_grouped = (
            mechanical[mechanical_columns]
            .groupby("mix_id", as_index=False)
            .median(numeric_only=True)
            .rename(columns={"compressive_strength_mpa": "measured_compressive_strength_mpa"})
        )
        mechanical_counts = (
            mechanical.groupby("mix_id").size().rename("mechanical_records").reset_index()
        )
        mechanical_grouped = mechanical_grouped.merge(mechanical_counts, on="mix_id", how="left")

        ndt_columns = ["mix_id", "upv_m_s", "rebound_estimated_strength_mpa", *composition]
        ndt_grouped = ndt[ndt_columns].groupby("mix_id", as_index=False).median(numeric_only=True)
        ndt_counts = ndt.groupby("mix_id").size().rename("ndt_records").reset_index()
        ndt_grouped = ndt_grouped.merge(ndt_counts, on="mix_id", how="left")

        merged = mechanical_grouped.merge(
            ndt_grouped, on="mix_id", how="inner", suffixes=("_mechanical", "_ndt")
        )
        for column in composition:
            mechanical_name = f"{column}_mechanical"
            ndt_name = f"{column}_ndt"
            if mechanical_name in merged.columns and ndt_name in merged.columns:
                merged[column] = merged[mechanical_name].combine_first(merged[ndt_name])
                merged = merged.drop(columns=[mechanical_name, ndt_name])
            elif mechanical_name in merged.columns:
                merged = merged.rename(columns={mechanical_name: column})
            elif ndt_name in merged.columns:
                merged = merged.rename(columns={ndt_name: column})

        merged["reference_group"] = reference_group or "Condition-filtered records"
        merged["reference_age_days"] = reference_age_days
        merged["curing_keyword"] = keyword
        merged = merged.sort_values("mix_id", kind="stable").reset_index(drop=True)
        if len(merged) < 5:
            raise ValueError(
                "At least five matched mixes are required. Broaden the reference condition or "
                "include records marked for review."
            )
        return merged

    @staticmethod
    def _ndt_pipeline(features: list[str], algorithm: str) -> Pipeline:
        if algorithm not in NDT_ALGORITHMS:
            raise ValueError(f"Unsupported NDT algorithm: {algorithm}")
        return Pipeline([
            ("preprocess", ColumnTransformer([
                ("numeric", Pipeline([
                    ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
                    ("scale", StandardScaler()),
                ]), features),
            ], remainder="drop")),
            ("model", NDT_ALGORITHMS[algorithm]()),
        ])

    @staticmethod
    def _ndt_cross_validation(matched: pd.DataFrame):
        groups = matched["mix_id"].astype(str).to_numpy()
        unique_groups = len(np.unique(groups))
        if unique_groups >= 5:
            return LeaveOneGroupOut(), groups, "Leave-one-mix-out cross-validation"
        folds = min(5, len(matched))
        if folds < 2:
            raise ValueError("Insufficient matched records for cross-validation.")
        return KFold(n_splits=folds, shuffle=True, random_state=42), None, f"{folds}-fold cross-validation"

    @classmethod
    def compare_ndt_fusion(
        cls,
        dataframe: pd.DataFrame,
        reference_group: str = "AMBIENT_28D_MECHANICAL",
        reference_age_days: float | None = 28.0,
        curing_keyword: str = "Ambient",
        algorithm: str = "Ridge Regression",
        include_review_records: bool = True,
    ) -> NDTFusionResult:
        matched = cls.prepare_ndt_matched_data(
            dataframe,
            reference_group=reference_group,
            reference_age_days=reference_age_days,
            curing_keyword=curing_keyword,
            include_review_records=include_review_records,
        )
        y = matched["measured_compressive_strength_mpa"].to_numpy(dtype=float)
        cv, groups, cv_method = cls._ndt_cross_validation(matched)
        rankings: list[dict[str, Any]] = []
        prediction_frames: list[pd.DataFrame] = []
        artifacts: dict[str, dict[str, Any]] = {}

        for feature_set, requested_features in NDT_FEATURE_SETS.items():
            features = [feature for feature in requested_features if feature in matched.columns]
            if len(features) != len(requested_features):
                continue
            if any(pd.to_numeric(matched[feature], errors="coerce").notna().sum() < 3 for feature in features):
                continue
            x = matched[features].apply(pd.to_numeric, errors="coerce")
            model = cls._ndt_pipeline(features, algorithm)
            predictions = cross_val_predict(model, x, y, cv=cv, groups=groups)
            rmse = float(np.sqrt(mean_squared_error(y, predictions)))
            mae = float(mean_absolute_error(y, predictions))
            r2 = float(r2_score(y, predictions))
            bias = float(np.mean(predictions - y))
            span = max(float(np.max(y) - np.min(y)), 1e-9)
            nrmse = float(rmse / span * 100.0)

            model.fit(x, y)
            ranges = {
                feature: [
                    float(pd.to_numeric(x[feature], errors="coerce").min()),
                    float(pd.to_numeric(x[feature], errors="coerce").max()),
                ]
                for feature in features
            }
            defaults = {
                feature: float(pd.to_numeric(x[feature], errors="coerce").median())
                for feature in features
            }
            metadata = {
                "format_version": 1,
                "artifact_type": "ndt_fusion_model",
                "application_version": __version__,
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "algorithm": algorithm,
                "feature_set": feature_set,
                "features": features,
                "response": "measured_compressive_strength_mpa",
                "reference_group": reference_group,
                "reference_age_days": reference_age_days,
                "curing_keyword": curing_keyword,
                "observations": len(matched),
                "cv_method": cv_method,
                "metrics": {
                    "rmse": rmse, "mae": mae, "r2": r2,
                    "bias": bias, "normalized_rmse_percent": nrmse,
                },
                "input_defaults": defaults,
                "numeric_training_ranges": ranges,
            }
            artifacts[feature_set] = {"model": model, "metadata": metadata}
            rankings.append({
                "feature_set": feature_set,
                "features": ", ".join(COLUMN_LABELS.get(f, f) for f in features),
                "observations": len(matched),
                "rmse": rmse,
                "mae": mae,
                "r2": r2,
                "bias": bias,
                "normalized_rmse_percent": nrmse,
            })
            frame = matched[["mix_id", "measured_compressive_strength_mpa"]].copy()
            frame["feature_set"] = feature_set
            frame["predicted_compressive_strength_mpa"] = predictions
            frame["residual"] = y - predictions
            prediction_frames.append(frame)

        if not rankings:
            raise ValueError("No NDT feature set has enough usable values.")
        ranking_frame = pd.DataFrame(rankings).sort_values(
            ["rmse", "mae"], kind="stable"
        ).reset_index(drop=True)
        ranking_frame.insert(0, "rank", np.arange(1, len(ranking_frame) + 1))
        best_feature_set = str(ranking_frame.iloc[0]["feature_set"])
        best_metrics = {
            key: float(ranking_frame.iloc[0][key])
            for key in ("rmse", "mae", "r2", "bias", "normalized_rmse_percent")
        }

        best_artifact = artifacts[best_feature_set]
        best_features = list(best_artifact["metadata"]["features"])
        best_model = best_artifact["model"]
        best_x = matched[best_features].apply(pd.to_numeric, errors="coerce")
        try:
            influence = permutation_importance(
                best_model, best_x, y, n_repeats=30, random_state=42,
                scoring="neg_root_mean_squared_error",
            )
            feature_influence = pd.DataFrame({
                "predictor": best_features,
                "importance_mean": influence.importances_mean,
                "importance_std": influence.importances_std,
            }).sort_values("importance_mean", ascending=False).reset_index(drop=True)
        except Exception:
            feature_influence = pd.DataFrame(columns=[
                "predictor", "importance_mean", "importance_std"
            ])

        return NDTFusionResult(
            algorithm=algorithm,
            observations=len(matched),
            reference_group=reference_group,
            reference_age_days=reference_age_days,
            curing_keyword=curing_keyword,
            cv_method=cv_method,
            rankings=ranking_frame,
            predictions=pd.concat(prediction_frames, ignore_index=True),
            matched_data=matched,
            best_feature_set=best_feature_set,
            best_metrics=best_metrics,
            feature_influence=feature_influence,
            artifacts=artifacts,
        )

    @staticmethod
    def _validate_ndt_artifact(artifact: dict[str, Any]) -> None:
        if not isinstance(artifact, dict) or not {"model", "metadata"}.issubset(artifact):
            raise ValueError("The selected NDT model is not compatible.")
        metadata = artifact["metadata"]
        if metadata.get("artifact_type") != "ndt_fusion_model":
            raise ValueError("The selected file is not an NDT fusion model.")
        if not metadata.get("features"):
            raise ValueError("The selected NDT model has no input definition.")

    @classmethod
    def predict_ndt_scenario(cls, artifact: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
        cls._validate_ndt_artifact(artifact)
        metadata = artifact["metadata"]
        features = list(metadata["features"])
        defaults = metadata.get("input_defaults", {})
        row: dict[str, float] = {}
        missing: list[str] = []
        outside: list[str] = []
        for feature in features:
            value = values.get(feature, defaults.get(feature))
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                numeric = np.nan
            if not np.isfinite(numeric):
                missing.append(feature)
                numeric = float(defaults.get(feature, np.nan))
            row[feature] = numeric
            limits = metadata.get("numeric_training_ranges", {}).get(feature)
            if limits and np.isfinite(numeric) and (numeric < limits[0] or numeric > limits[1]):
                outside.append(feature)

        frame = pd.DataFrame([row], columns=features)
        prediction = float(artifact["model"].predict(frame)[0])
        nrmse = float(metadata.get("metrics", {}).get("normalized_rmse_percent", np.inf))
        if missing or len(outside) > 1 or nrmse > 50:
            reliability = "D"
            note = "Low support: missing inputs, multiple range violations, or high validation error."
        elif outside or nrmse > 30:
            reliability = "C"
            note = "Limited support: the scenario is near or beyond the calibrated range."
        elif nrmse > 15:
            reliability = "B"
            note = "Moderate support within the calibrated input range."
        else:
            reliability = "A"
            note = "Strong support within the calibrated input range."
        return {
            "predicted_compressive_strength_mpa": prediction,
            "reliability_class": reliability,
            "reliability_reason": note,
            "missing_fields": ", ".join(missing),
            "outside_training_range_fields": ", ".join(outside),
            "feature_set": metadata.get("feature_set", ""),
            "algorithm": metadata.get("algorithm", ""),
        }

    @classmethod
    def save_ndt_artifact(cls, artifact: dict[str, Any], directory: Path | str) -> Path:
        cls._validate_ndt_artifact(artifact)
        destination = Path(directory)
        destination.mkdir(parents=True, exist_ok=True)
        metadata = artifact["metadata"]
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        name = (
            f"ndt_{cls._slug(metadata.get('feature_set', 'model'))}_"
            f"{cls._slug(metadata.get('algorithm', 'regression'))}_{stamp}"
        )
        path = destination / f"{name}.joblib"
        joblib.dump(artifact, path)
        path.with_suffix(".json").write_text(
            json.dumps(metadata, indent=2, default=str), encoding="utf-8"
        )
        return path

    @classmethod
    def load_ndt_artifact(cls, path: Path | str) -> dict[str, Any]:
        artifact = joblib.load(Path(path))
        cls._validate_ndt_artifact(artifact)
        return artifact

    @staticmethod
    def list_saved_ndt_models(directory: Path | str) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        for path in sorted(Path(directory).glob("*.joblib"), reverse=True):
            try:
                artifact = joblib.load(path)
                metadata = artifact.get("metadata", {})
                if metadata.get("artifact_type") != "ndt_fusion_model":
                    continue
                metrics = metadata.get("metrics", {})
                rows.append({
                    "artifact_path": str(path),
                    "feature_set": metadata.get("feature_set", ""),
                    "algorithm": metadata.get("algorithm", ""),
                    "observations": metadata.get("observations", ""),
                    "rmse": metrics.get("rmse", np.nan),
                    "r2": metrics.get("r2", np.nan),
                    "created_at_utc": metadata.get("created_at_utc", ""),
                })
            except Exception:
                continue
        return pd.DataFrame(rows)

    @staticmethod
    def delete_artifact(path: Path | str) -> None:
        artifact_path = Path(path)
        artifact_path.unlink(missing_ok=True)
        artifact_path.with_suffix(".json").unlink(missing_ok=True)

    @classmethod
    def prepare_durability_records(
        cls,
        dataframe: pd.DataFrame,
        include_review_records: bool = False,
    ) -> pd.DataFrame:
        filtered = cls._filter_status(dataframe, include_review_records)
        required_any = [
            "initial_compressive_strength_mpa", "residual_compressive_strength_mpa",
            "strength_loss_percent_derived", "initial_mass_kg", "exposed_mass_kg",
            "mass_change_percent_derived",
        ]
        available = [column for column in required_any if column in filtered.columns]
        if not available:
            raise ValueError("No durability fields are available.")
        mask = pd.Series(False, index=filtered.index)
        for column in available:
            mask |= pd.to_numeric(filtered[column], errors="coerce").notna()
        durable = filtered.loc[mask].copy()
        if durable.empty:
            raise ValueError("No usable durability records are available.")

        numeric_columns = [
            "fa_percent_numeric", "ggbs_percent_numeric", "sf_percent_numeric",
            "acid_concentration_percent", "acid_exposure_days", "initial_mass_kg",
            "exposed_mass_kg", "mass_change_percent_derived",
            "initial_compressive_strength_mpa", "residual_compressive_strength_mpa",
            "strength_loss_percent_derived",
        ]
        for column in numeric_columns:
            if column in durable.columns:
                durable[column] = pd.to_numeric(durable[column], errors="coerce")

        if {
            "initial_compressive_strength_mpa", "residual_compressive_strength_mpa"
        }.issubset(durable.columns):
            initial = durable["initial_compressive_strength_mpa"]
            residual = durable["residual_compressive_strength_mpa"]
            derived_loss = np.where(initial.abs() > 1e-12, (initial - residual) / initial * 100, np.nan)
            if "strength_loss_percent_derived" not in durable.columns:
                durable["strength_loss_percent_derived"] = derived_loss
            else:
                durable["strength_loss_percent_derived"] = durable[
                    "strength_loss_percent_derived"
                ].fillna(pd.Series(derived_loss, index=durable.index))
            durable["strength_retention_percent"] = np.where(
                initial.abs() > 1e-12, residual / initial * 100, np.nan
            )
        else:
            durable["strength_retention_percent"] = 100.0 - durable.get(
                "strength_loss_percent_derived", pd.Series(np.nan, index=durable.index)
            )

        if {"initial_mass_kg", "exposed_mass_kg"}.issubset(durable.columns):
            initial_mass = durable["initial_mass_kg"]
            exposed_mass = durable["exposed_mass_kg"]
            derived_change = np.where(
                initial_mass.abs() > 1e-12,
                (exposed_mass - initial_mass) / initial_mass * 100,
                np.nan,
            )
            if "mass_change_percent_derived" not in durable.columns:
                durable["mass_change_percent_derived"] = derived_change
            else:
                durable["mass_change_percent_derived"] = durable[
                    "mass_change_percent_derived"
                ].fillna(pd.Series(derived_change, index=durable.index))

        durable["absolute_mass_change_percent"] = durable.get(
            "mass_change_percent_derived", pd.Series(np.nan, index=durable.index)
        ).abs()
        return durable.reset_index(drop=True)

    @classmethod
    def durability_profile(
        cls,
        dataframe: pd.DataFrame,
        strength_weight: float = 0.80,
        mass_weight: float = 0.20,
        mass_penalty: float = 10.0,
        include_review_records: bool = False,
    ) -> DurabilityProfileResult:
        durable = cls.prepare_durability_records(dataframe, include_review_records)
        if strength_weight < 0 or mass_weight < 0 or strength_weight + mass_weight <= 0:
            raise ValueError("Durability-score weights must be non-negative and not both zero.")
        total_weight = strength_weight + mass_weight
        strength_weight = strength_weight / total_weight
        mass_weight = mass_weight / total_weight
        mass_penalty = max(float(mass_penalty), 0.0)
        durable["mass_stability_score"] = (
            100.0 - durable["absolute_mass_change_percent"] * mass_penalty
        ).clip(lower=0.0, upper=100.0)
        durable["durability_score"] = (
            strength_weight * durable["strength_retention_percent"]
            + mass_weight * durable["mass_stability_score"]
        )

        group_columns = [column for column in ("mix_id", "acid_type") if column in durable.columns]
        if not group_columns:
            raise ValueError("Durability ranking requires a mix or exposure-medium field.")
        numeric = [
            "initial_compressive_strength_mpa", "residual_compressive_strength_mpa",
            "strength_loss_percent_derived", "strength_retention_percent",
            "mass_change_percent_derived", "absolute_mass_change_percent",
            "mass_stability_score", "durability_score",
        ]
        ranking = durable.groupby(group_columns, as_index=False)[numeric].mean(numeric_only=True)
        ranking = ranking.sort_values("durability_score", ascending=False, kind="stable").reset_index(drop=True)
        ranking.insert(0, "rank", np.arange(1, len(ranking) + 1))
        best_row = ranking.iloc[0]
        best_mix = str(best_row.get("mix_id", "—"))
        return DurabilityProfileResult(
            records=len(durable),
            media=int(durable.get("acid_type", pd.Series(dtype=str)).nunique()),
            mixes=int(durable.get("mix_id", pd.Series(dtype=str)).nunique()),
            strength_weight=strength_weight,
            mass_weight=mass_weight,
            mass_penalty=mass_penalty,
            ranking=ranking,
            best_mix=best_mix,
            best_score=float(best_row["durability_score"]),
            mean_retention=float(durable["strength_retention_percent"].mean()),
            maximum_strength_loss=float(durable["strength_loss_percent_derived"].max()),
        )

    @staticmethod
    def ndt_comparison_figure(result: NDTFusionResult) -> Figure:
        figure = Figure(figsize=(8.8, 5.6), constrained_layout=True)
        axis = figure.add_subplot(111)
        frame = result.rankings.sort_values("rmse", ascending=True)
        axis.barh(frame["feature_set"], frame["rmse"])
        axis.set_xlabel("Cross-validated RMSE (MPa)")
        axis.set_ylabel("Input set")
        axis.grid(True, axis="x", alpha=0.25)
        return figure

    @staticmethod
    def ndt_observed_predicted_figure(result: NDTFusionResult, feature_set: str | None = None) -> Figure:
        feature_set = feature_set or result.best_feature_set
        frame = result.predictions[result.predictions["feature_set"] == feature_set].copy()
        figure = Figure(figsize=(8.4, 5.8), constrained_layout=True)
        axis = figure.add_subplot(111)
        x = pd.to_numeric(frame["measured_compressive_strength_mpa"], errors="coerce")
        y = pd.to_numeric(frame["predicted_compressive_strength_mpa"], errors="coerce")
        axis.scatter(x, y)
        if len(frame):
            minimum = float(np.nanmin([x.min(), y.min()]))
            maximum = float(np.nanmax([x.max(), y.max()]))
            axis.plot([minimum, maximum], [minimum, maximum], linestyle="--", linewidth=1)
            for xv, yv, mix in zip(x, y, frame["mix_id"]):
                axis.annotate(str(mix), (xv, yv), xytext=(4, 5), textcoords="offset points", fontsize=8)
        axis.set_xlabel("Measured compressive strength (MPa)")
        axis.set_ylabel("Cross-validated estimate (MPa)")
        axis.set_title(feature_set)
        axis.grid(True, alpha=0.25)
        return figure

    @staticmethod
    def ndt_residual_figure(result: NDTFusionResult, feature_set: str | None = None) -> Figure:
        feature_set = feature_set or result.best_feature_set
        frame = result.predictions[result.predictions["feature_set"] == feature_set].copy()
        figure = Figure(figsize=(8.4, 5.8), constrained_layout=True)
        axis = figure.add_subplot(111)
        axis.scatter(frame["predicted_compressive_strength_mpa"], frame["residual"])
        axis.axhline(0.0, linestyle="--", linewidth=1)
        for _, row in frame.iterrows():
            axis.annotate(
                str(row["mix_id"]),
                (row["predicted_compressive_strength_mpa"], row["residual"]),
                xytext=(4, 5), textcoords="offset points", fontsize=8,
            )
        axis.set_xlabel("Cross-validated estimate (MPa)")
        axis.set_ylabel("Measured − estimated (MPa)")
        axis.set_title(feature_set)
        axis.grid(True, alpha=0.25)
        return figure

    @staticmethod
    def durability_score_figure(result: DurabilityProfileResult) -> Figure:
        frame = result.ranking.copy().sort_values("durability_score", ascending=True)
        figure = Figure(figsize=(9.2, 5.8), constrained_layout=True)
        axis = figure.add_subplot(111)
        labels = frame.get("mix_id", pd.Series("", index=frame.index)).astype(str)
        if "acid_type" in frame.columns:
            labels = labels + " · " + frame["acid_type"].astype(str)
        axis.barh(labels, frame["durability_score"])
        axis.set_xlabel("Configurable durability score")
        axis.set_xlim(0, 100)
        axis.grid(True, axis="x", alpha=0.25)
        return figure

    @classmethod
    def durability_initial_residual_figure(
        cls, dataframe: pd.DataFrame, include_review_records: bool = False
    ) -> Figure:
        durable = cls.prepare_durability_records(dataframe, include_review_records)
        figure = Figure(figsize=(9.2, 5.8), constrained_layout=True)
        axis = figure.add_subplot(111)
        labels = durable.get("mix_id", pd.Series("", index=durable.index)).astype(str)
        if "acid_type" in durable.columns:
            labels = labels + " · " + durable["acid_type"].astype(str)
        x = np.arange(len(durable))
        width = 0.36
        axis.bar(
            x - width / 2,
            durable["initial_compressive_strength_mpa"],
            width,
            label="Initial",
        )
        axis.bar(
            x + width / 2,
            durable["residual_compressive_strength_mpa"],
            width,
            label="Residual",
        )
        axis.set_xticks(x, labels, rotation=30, ha="right")
        axis.set_ylabel("Compressive strength (MPa)")
        axis.legend()
        axis.grid(True, axis="y", alpha=0.25)
        return figure

    @classmethod
    def durability_heatmap_figure(
        cls, dataframe: pd.DataFrame, metric: str = "strength_retention_percent",
        include_review_records: bool = False,
    ) -> Figure:
        durable = cls.prepare_durability_records(dataframe, include_review_records)
        if metric not in durable.columns:
            raise ValueError(f"Durability metric is unavailable: {metric}")
        if not {"mix_id", "acid_type"}.issubset(durable.columns):
            raise ValueError("Heatmap requires mix and exposure-medium fields.")
        pivot = durable.pivot_table(index="mix_id", columns="acid_type", values=metric, aggfunc="mean")
        figure = Figure(figsize=(8.6, 5.8), constrained_layout=True)
        axis = figure.add_subplot(111)
        image = axis.imshow(pivot.values.astype(float), aspect="auto")
        axis.set_xticks(range(len(pivot.columns)), pivot.columns)
        axis.set_yticks(range(len(pivot.index)), pivot.index)
        axis.set_xlabel("Exposure medium")
        axis.set_ylabel("Mix")
        for row in range(len(pivot.index)):
            for column in range(len(pivot.columns)):
                value = pivot.iat[row, column]
                if pd.notna(value):
                    axis.text(column, row, f"{value:.1f}", ha="center", va="center", fontsize=8)
        figure.colorbar(image, ax=axis, label=COLUMN_LABELS.get(metric, metric))
        return figure

    @classmethod
    def build_durability_twin(
        cls,
        dataframe: pd.DataFrame,
        response: str = "residual_compressive_strength_mpa",
        predictors: list[str] | None = None,
        method: str = "Gaussian Process",
        confidence_percent: float = 95.0,
        include_review_records: bool = False,
    ) -> TwinBuildResult:
        durable = cls.prepare_durability_records(dataframe, include_review_records)
        predictors = list(dict.fromkeys(predictors or DURABILITY_DEFAULT_PREDICTORS))
        missing = [column for column in [response, *predictors] if column not in durable.columns]
        if missing:
            raise ValueError("Durability model fields are unavailable: " + ", ".join(missing))
        result = DigitalTwinService().build_twin(
            durable,
            response=response,
            predictors=predictors,
            method=method,
            confidence_percent=confidence_percent,
            include_review_records=True,
            group_column="mix_id",
        )
        result.artifact["metadata"]["artifact_type"] = "durability_twin"
        result.artifact["metadata"]["domain"] = "durability"
        return result

    @staticmethod
    def save_durability_artifact(artifact: dict[str, Any], directory: Path | str) -> Path:
        metadata = artifact.get("metadata", {})
        if metadata.get("artifact_type") != "durability_twin":
            raise ValueError("The selected model is not a durability twin.")
        return DigitalTwinService.save_artifact(artifact, directory)

    @staticmethod
    def load_durability_artifact(path: Path | str) -> dict[str, Any]:
        artifact = DigitalTwinService.load_artifact(path)
        if artifact.get("metadata", {}).get("artifact_type") != "durability_twin":
            raise ValueError("The selected file is not a durability twin.")
        return artifact

    @staticmethod
    def list_saved_durability_models(directory: Path | str) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        for path in sorted(Path(directory).glob("*.joblib"), reverse=True):
            try:
                artifact = joblib.load(path)
                metadata = artifact.get("metadata", {})
                if metadata.get("artifact_type") != "durability_twin":
                    continue
                metrics = metadata.get("metrics", {})
                rows.append({
                    "artifact_path": str(path),
                    "response": metadata.get("response", ""),
                    "method": metadata.get("method", ""),
                    "observations": metadata.get("observations", ""),
                    "rmse": metrics.get("rmse", np.nan),
                    "coverage_percent": metrics.get("coverage_percent", np.nan),
                    "created_at_utc": metadata.get("created_at_utc", ""),
                })
            except Exception:
                continue
        return pd.DataFrame(rows)

    @staticmethod
    def _durability_support_limit(artifact: dict[str, Any]) -> tuple[str | None, str | None]:
        metrics = artifact.get("metadata", {}).get("metrics", {})
        normalized_rmse = float(metrics.get("normalized_rmse_percent", 0.0))
        r2 = float(metrics.get("r2", 0.0))
        if normalized_rmse > 40.0 or r2 < 0.0:
            return "D", "Global cross-validation indicates weak predictive support for this response."
        if normalized_rmse > 25.0 or r2 < 0.30:
            return "C", "Global cross-validation indicates limited predictive support for this response."
        return None, None

    @classmethod
    def predict_durability_scenario(cls, artifact: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
        if artifact.get("metadata", {}).get("artifact_type") != "durability_twin":
            raise ValueError("The active model is not a durability twin.")
        result = DigitalTwinService.predict_scenario(artifact, values)
        limit, reason = cls._durability_support_limit(artifact)
        order = {"A": 1, "B": 2, "C": 3, "D": 4}
        if limit and order.get(str(result.get("reliability_class", "D")), 4) < order[limit]:
            result["reliability_class"] = limit
            result["reliability_reason"] = reason
        return result

    @classmethod
    def durability_sweep(
        cls, artifact: dict[str, Any], values: dict[str, Any], axis: str, resolution: int = 60
    ) -> pd.DataFrame:
        metadata = artifact.get("metadata", {})
        if metadata.get("artifact_type") != "durability_twin":
            raise ValueError("The active model is not a durability twin.")
        ranges = metadata.get("numeric_training_ranges", {})
        if axis not in ranges:
            raise ValueError("The selected sweep field has no numeric training range.")
        low, high = [float(value) for value in ranges[axis]]
        if np.isclose(low, high):
            raise ValueError("The selected sweep field has only one calibrated value.")
        resolution = int(np.clip(resolution, 15, 250))
        axis_values = np.linspace(low, high, resolution)
        rows = []
        defaults = metadata.get("input_defaults", {})
        for value in axis_values:
            row = {predictor: values.get(predictor, defaults.get(predictor))
                   for predictor in metadata.get("predictors", [])}
            row[axis] = float(value)
            rows.append(row)
        frame = pd.DataFrame(rows)
        estimates = DigitalTwinService.predict_dataframe(artifact, frame)
        limit, reason = cls._durability_support_limit(artifact)
        if limit:
            order = {"A": 1, "B": 2, "C": 3, "D": 4}
            mask = estimates["reliability_class"].astype(str).map(order).fillna(4) < order[limit]
            estimates.loc[mask, "reliability_class"] = limit
            estimates.loc[mask, "reliability_reason"] = reason
        estimates.insert(0, axis, axis_values)
        return estimates

    @staticmethod
    def durability_sweep_figure(
        sweep: pd.DataFrame, axis: str, response: str
    ) -> Figure:
        figure = Figure(figsize=(8.7, 5.8), constrained_layout=True)
        plot = figure.add_subplot(111)
        x = pd.to_numeric(sweep[axis], errors="coerce")
        mean = pd.to_numeric(sweep["predicted_mean"], errors="coerce")
        lower = pd.to_numeric(sweep["lower_bound"], errors="coerce")
        upper = pd.to_numeric(sweep["upper_bound"], errors="coerce")
        plot.plot(x, mean, linewidth=2, label="Estimate")
        plot.fill_between(x, lower, upper, alpha=0.22, label="Prediction interval")
        plot.set_xlabel(COLUMN_LABELS.get(axis, axis))
        plot.set_ylabel(COLUMN_LABELS.get(response, response))
        plot.grid(True, alpha=0.25)
        plot.legend()
        return figure
