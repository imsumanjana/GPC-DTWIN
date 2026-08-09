"""Canonical dataset schema, labels, and analysis groups."""

DATA_COLUMNS = [
    "record_id", "record_group", "dataset_origin", "data_block", "data_locator",
    "mix_id", "mix_proportion_label", "fa_percent_numeric", "ggbs_percent_numeric",
    "sf_percent_numeric", "coarse_aggregate_kg_m3", "fine_aggregate_kg_m3",
    "fly_ash_kg_m3", "ggbs_kg_m3", "sf_kg_m3", "naoh_kg_m3",
    "na2sio3_kg_m3", "naoh_molarity_M", "superplasticizer_percent",
    "activator_ratio_label", "aas_b_ratio", "curing_regime", "curing_temperature_C",
    "curing_duration_hours", "mechanical_test_age_days", "acid_type",
    "acid_concentration_percent", "acid_exposure_days", "slump_mm",
    "workability_class", "compressive_strength_mpa", "split_tensile_strength_mpa",
    "flexural_strength_mpa", "upv_m_s", "upv_quality_label",
    "rebound_estimated_strength_mpa", "initial_mass_kg", "exposed_mass_kg",
    "mass_change_percent_derived", "initial_compressive_strength_mpa",
    "residual_compressive_strength_mpa", "strength_loss_percent_derived",
    "data_status", "notes",
]

NUMERIC_COLUMNS = {
    "fa_percent_numeric", "ggbs_percent_numeric", "sf_percent_numeric",
    "coarse_aggregate_kg_m3", "fine_aggregate_kg_m3", "fly_ash_kg_m3",
    "ggbs_kg_m3", "sf_kg_m3", "naoh_kg_m3", "na2sio3_kg_m3",
    "naoh_molarity_M", "superplasticizer_percent", "aas_b_ratio",
    "curing_temperature_C", "curing_duration_hours", "mechanical_test_age_days",
    "acid_concentration_percent", "acid_exposure_days", "slump_mm",
    "compressive_strength_mpa", "split_tensile_strength_mpa",
    "flexural_strength_mpa", "upv_m_s", "rebound_estimated_strength_mpa",
    "initial_mass_kg", "exposed_mass_kg", "mass_change_percent_derived",
    "initial_compressive_strength_mpa", "residual_compressive_strength_mpa",
    "strength_loss_percent_derived",
}

NONNEGATIVE_COLUMNS = NUMERIC_COLUMNS - {"mass_change_percent_derived"}

REQUIRED_ID_COLUMNS = {
    "record_id", "record_group", "dataset_origin", "data_block", "data_locator", "mix_id"
}

VERIFICATION_STATES = [
    "IMPORTED", "IMPORTED_WITH_DERIVED_VALUES", "VERIFIED",
    "VERIFIED_WITH_ASSUMPTION", "REQUIRES_REVIEW", "CONFLICTING", "EXCLUDED",
]

ESSENTIAL_COLUMNS = [
    "record_id", "record_group", "mix_id", "mix_proportion_label",
    "fa_percent_numeric", "ggbs_percent_numeric", "sf_percent_numeric",
    "aas_b_ratio", "curing_regime", "mechanical_test_age_days", "acid_type",
    "slump_mm", "compressive_strength_mpa", "split_tensile_strength_mpa",
    "flexural_strength_mpa", "upv_m_s", "rebound_estimated_strength_mpa",
    "residual_compressive_strength_mpa", "strength_loss_percent_derived", "data_status",
]

COLUMN_LABELS = {
    "record_id": "Record ID", "record_group": "Record group",
    "dataset_origin": "Dataset origin", "data_block": "Data block",
    "data_locator": "Data locator", "mix_id": "Mix ID",
    "mix_proportion_label": "FA:GGBS:SF", "fa_percent_numeric": "FA (%)",
    "ggbs_percent_numeric": "GGBS (%)", "sf_percent_numeric": "SF (%)",
    "coarse_aggregate_kg_m3": "Coarse aggregate (kg/m³)",
    "fine_aggregate_kg_m3": "Fine aggregate (kg/m³)",
    "fly_ash_kg_m3": "Fly ash (kg/m³)", "ggbs_kg_m3": "GGBS (kg/m³)",
    "sf_kg_m3": "Silica fume (kg/m³)", "naoh_kg_m3": "NaOH (kg/m³)",
    "na2sio3_kg_m3": "Na₂SiO₃ (kg/m³)", "naoh_molarity_M": "NaOH molarity (M)",
    "superplasticizer_percent": "Superplasticizer (%)",
    "activator_ratio_label": "Activator ratio", "aas_b_ratio": "AAS:B ratio (–)",
    "curing_regime": "Curing regime", "curing_temperature_C": "Curing temperature (°C)",
    "curing_duration_hours": "Curing duration (h)",
    "mechanical_test_age_days": "Test age (days)", "acid_type": "Exposure medium",
    "acid_concentration_percent": "Exposure concentration (%)",
    "acid_exposure_days": "Exposure duration (days)", "slump_mm": "Slump (mm)",
    "workability_class": "Workability class",
    "compressive_strength_mpa": "Compressive strength (MPa)",
    "split_tensile_strength_mpa": "Split tensile strength (MPa)",
    "flexural_strength_mpa": "Flexural strength (MPa)", "upv_m_s": "UPV (m/s)",
    "upv_quality_label": "UPV quality",
    "rebound_estimated_strength_mpa": "Rebound strength (MPa)",
    "initial_mass_kg": "Initial mass (kg)", "exposed_mass_kg": "Exposed mass (kg)",
    "mass_change_percent_derived": "Mass change (%)",
    "initial_compressive_strength_mpa": "Initial strength (MPa)",
    "residual_compressive_strength_mpa": "Residual strength (MPa)",
    "strength_loss_percent_derived": "Strength loss (%)", "data_status": "Data status",
    "notes": "Notes",
    "rank": "Rank", "algorithm": "Algorithm", "rmse": "RMSE", "mae": "MAE",
    "r2": "R²", "mape_percent": "MAPE (%)", "fit_seconds": "Evaluation time (s)",
    "cv_rmse_mean": "Fold RMSE mean", "cv_rmse_std": "Fold RMSE SD",
    "cv_mae_mean": "Fold MAE mean", "cv_mae_std": "Fold MAE SD",
    "cv_r2_mean": "Fold R² mean", "cv_r2_std": "Fold R² SD",
    "rmse_gap_percent": "RMSE gap (%)", "mae_gap_percent": "MAE gap (%)",
    "cv_rmse_variation_percent": "Fold RMSE variation (%)",
    "status": "Status", "status_reason": "Status basis",
    "predictor": "Predictor", "predictor_label": "Predictor",
    "importance_mean": "Importance", "importance_std": "Importance spread",
    "created_at_utc": "Created (UTC)", "observations": "Records",
    "artifact_path": "Model file", "predicted_response": "Prediction",
    "observed_response": "Observed", "residual": "Residual",
    "prediction_input_missing_count": "Missing inputs",
    "input_completeness_percent": "Input completeness (%)",
    "outside_training_range_count": "Outside-range inputs",
    "outside_training_range_fields": "Outside-range fields",

    "method": "Prediction model", "model_rank": "Model rank", "model_status": "Model status", "confidence_percent": "Confidence (%)",
    "coverage_percent": "Coverage (%)", "predicted_mean": "Estimated response",
    "prediction_std": "Prediction uncertainty", "lower_bound": "Lower bound",
    "upper_bound": "Upper bound", "interval_width": "Interval width",
    "normalized_uncertainty_percent": "Relative uncertainty (%)",
    "nearest_training_distance": "Nearest-data distance",
    "reliability_class": "Reliability class", "reliability_reason": "Reliability note",
    "within_interval": "Within interval",
    "feature_set": "Input set",
    "features": "Inputs",
    "bias": "Bias",
    "normalized_rmse_percent": "Normalized RMSE (%)",
    "measured_compressive_strength_mpa": "Measured compressive strength (MPa)",
    "predicted_compressive_strength_mpa": "Estimated compressive strength (MPa)",
    "mechanical_records": "Reference records",
    "ndt_records": "NDT records",
    "reference_group": "Reference group",
    "reference_age_days": "Reference age (days)",
    "curing_keyword": "Curing filter",
    "strength_retention_percent": "Strength retention (%)",
    "absolute_mass_change_percent": "Absolute mass change (%)",
    "mass_stability_score": "Mass-stability score",
    "durability_score": "Durability score",

    "solution_rank": "Solution rank",
    "recommendation_rank": "Recommendation rank",
    "run_type": "Run type",
    "solutions": "Solutions",
    "candidates_evaluated": "Candidates evaluated",
    "constraint_violation": "Constraint violation",
    "feasible": "Feasible",
    "pareto_rank": "Pareto rank",
    "crowding_distance": "Crowding distance",
    "compromise_score": "Compromise score",
    "target_loss": "Target loss",
    "uncertainty_penalty": "Uncertainty penalty",
    "design_loss": "Design loss",
    "targets_satisfied": "Targets satisfied",
    "target_count": "Target count",
    "target_satisfaction_percent": "Target satisfaction (%)",
    "response": "Response",
    "response_label": "Response",
    "strategy": "Acquisition strategy",
    "direction": "Direction",
    "recommendations": "Recommendations",
    "recommendation_id": "Recommendation ID",
    "candidate_id": "Candidate ID",
    "candidate_rank": "Candidate rank",
    "acquisition_score": "Acquisition score",
    "expected_improvement": "Expected improvement",
    "novelty_score": "Novelty score",
    "existing_design_distance": "Existing-design distance",
    "metric": "Metric",
    "before_update": "Before update",
    "after_update": "After update",
    "change": "Change",
    "preference": "Interpretation",
    "observations_before": "Records before",
    "observations_after": "Records after",
    "records_added": "Records added",
}


# Canonical engineering units used by charts, colour bars, and exported figure labels.
# A blank string denotes a categorical/dimensionless quantity for which no physical unit applies.
COLUMN_UNITS = {
    "fa_percent_numeric": "%", "ggbs_percent_numeric": "%", "sf_percent_numeric": "%",
    "coarse_aggregate_kg_m3": "kg/m³", "fine_aggregate_kg_m3": "kg/m³",
    "fly_ash_kg_m3": "kg/m³", "ggbs_kg_m3": "kg/m³", "sf_kg_m3": "kg/m³",
    "naoh_kg_m3": "kg/m³", "na2sio3_kg_m3": "kg/m³",
    "naoh_molarity_M": "M", "superplasticizer_percent": "%",
    "aas_b_ratio": "–", "curing_temperature_C": "°C",
    "curing_duration_hours": "h", "mechanical_test_age_days": "days",
    "acid_concentration_percent": "%", "acid_exposure_days": "days",
    "slump_mm": "mm", "compressive_strength_mpa": "MPa",
    "split_tensile_strength_mpa": "MPa", "flexural_strength_mpa": "MPa",
    "upv_m_s": "m/s", "rebound_estimated_strength_mpa": "MPa",
    "initial_mass_kg": "kg", "exposed_mass_kg": "kg",
    "mass_change_percent_derived": "%", "initial_compressive_strength_mpa": "MPa",
    "residual_compressive_strength_mpa": "MPa", "strength_loss_percent_derived": "%",
    "strength_retention_percent": "%", "absolute_mass_change_percent": "%",
    "reference_age_days": "days",
}


def column_unit(column: str) -> str:
    """Return the canonical physical unit for a dataset field, if one is defined."""
    return COLUMN_UNITS.get(str(column), "")


def quantity_label(prefix: str, column: str, *, dimensionless_marker: bool = False) -> str:
    """Build a figure label such as ``Observed compressive strength (MPa)``.

    The helper is intentionally used for derived chart quantities (prediction, residual, RMSE,
    interval width) whose unit is inherited from the selected response.
    """
    unit = column_unit(column)
    if unit and unit != "–":
        return f"{prefix} ({unit})"
    if unit == "–" and dimensionless_marker:
        return f"{prefix} (–)"
    return prefix

ANALYSIS_NUMERIC_COLUMNS = [
    "fa_percent_numeric", "ggbs_percent_numeric", "sf_percent_numeric", "aas_b_ratio",
    "mechanical_test_age_days", "slump_mm", "compressive_strength_mpa",
    "split_tensile_strength_mpa", "flexural_strength_mpa", "upv_m_s",
    "rebound_estimated_strength_mpa", "mass_change_percent_derived",
    "residual_compressive_strength_mpa", "strength_loss_percent_derived",
]

ANALYSIS_FACTOR_COLUMNS = [
    "record_group", "mix_id", "curing_regime", "acid_type", "workability_class", "data_status"
]

MODEL_RESPONSE_COLUMNS = [
    "slump_mm", "compressive_strength_mpa", "split_tensile_strength_mpa",
    "flexural_strength_mpa", "upv_m_s", "rebound_estimated_strength_mpa",
    "mass_change_percent_derived", "residual_compressive_strength_mpa",
    "strength_loss_percent_derived",
]

MODEL_NUMERIC_PREDICTORS = {
    "fa_percent_numeric", "ggbs_percent_numeric", "sf_percent_numeric",
    "coarse_aggregate_kg_m3", "fine_aggregate_kg_m3", "fly_ash_kg_m3",
    "ggbs_kg_m3", "sf_kg_m3", "naoh_kg_m3", "na2sio3_kg_m3",
    "naoh_molarity_M", "superplasticizer_percent", "aas_b_ratio",
    "curing_temperature_C", "curing_duration_hours", "mechanical_test_age_days",
    "acid_concentration_percent", "acid_exposure_days", "slump_mm",
    "compressive_strength_mpa", "split_tensile_strength_mpa",
    "flexural_strength_mpa", "upv_m_s", "rebound_estimated_strength_mpa",
    "initial_mass_kg", "exposed_mass_kg", "mass_change_percent_derived",
    "initial_compressive_strength_mpa", "residual_compressive_strength_mpa",
    "strength_loss_percent_derived",
}

MODEL_PREDICTOR_COLUMNS = [
    "fa_percent_numeric", "ggbs_percent_numeric", "sf_percent_numeric",
    "coarse_aggregate_kg_m3", "fine_aggregate_kg_m3", "naoh_molarity_M",
    "superplasticizer_percent", "aas_b_ratio", "curing_regime",
    "curing_temperature_C", "curing_duration_hours", "mechanical_test_age_days",
    "acid_type", "acid_concentration_percent", "acid_exposure_days",
    "slump_mm", "workability_class", "upv_m_s",
    "rebound_estimated_strength_mpa", "initial_mass_kg",
    "initial_compressive_strength_mpa",
]

MODEL_DEFAULT_PREDICTORS = [
    "fa_percent_numeric", "ggbs_percent_numeric", "sf_percent_numeric",
    "aas_b_ratio", "mechanical_test_age_days", "curing_temperature_C",
    "curing_duration_hours", "curing_regime",
]
