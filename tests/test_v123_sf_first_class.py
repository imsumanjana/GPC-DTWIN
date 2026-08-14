from __future__ import annotations

import numpy as np
import pandas as pd

from gpc_dtwin.columns import BINDER_PERCENT_COLUMNS, MODEL_DEFAULT_PREDICTORS
from gpc_dtwin.paths import REFERENCE_DATASET
from gpc_dtwin.services.analytics_service import AnalyticsService
from gpc_dtwin.services.data_service import DataService
from gpc_dtwin.services.digital_twin_service import DigitalTwinService
from gpc_dtwin.services.modeling_service import ModelingService


def _predictors() -> list[str]:
    return [
        "fa_percent_numeric",
        "ggbs_percent_numeric",
        "sf_percent_numeric",
        "aas_b_ratio",
        "mechanical_test_age_days",
        "curing_regime",
    ]


def test_fa_ggbs_sf_are_one_first_class_binder_group():
    assert BINDER_PERCENT_COLUMNS == [
        "fa_percent_numeric", "ggbs_percent_numeric", "sf_percent_numeric"
    ]
    assert all(field in MODEL_DEFAULT_PREDICTORS for field in BINDER_PERCENT_COLUMNS)


def test_reference_model_keeps_sf_at_10_percent_in_prediction_and_feature_influence():
    dataframe = DataService.load_csv(REFERENCE_DATASET)
    result = ModelingService().compare_models(
        dataframe,
        "compressive_strength_mpa",
        _predictors(),
        algorithms=["Ridge Regression"],
        include_review_records=True,
    )

    assert "sf_percent_numeric" in result.predictors
    assert "sf_percent_numeric" in set(result.feature_influence["predictor"])
    metadata = result.artifact["metadata"]
    assert np.isclose(float(metadata["input_defaults"]["sf_percent_numeric"]), 10.0)
    assert metadata["numeric_training_ranges"]["sf_percent_numeric"] == [10.0, 10.0]
    assert metadata["binder_percent_predictors"] == BINDER_PERCENT_COLUMNS
    assert np.isclose(float(metadata["binder_percent_defaults"]["sf_percent_numeric"]), 10.0)


def test_digital_twin_keeps_sf_as_predictor_and_scenario_input():
    dataframe = DataService.load_csv(REFERENCE_DATASET)
    ranking = ModelingService().compare_models(
        dataframe,
        "compressive_strength_mpa",
        _predictors(),
        algorithms=["Ridge Regression"],
        include_review_records=True,
    )
    twin = DigitalTwinService().build_twin(
        dataframe,
        "compressive_strength_mpa",
        _predictors(),
        method="Ridge Regression",
        include_review_records=True,
        ranking=ranking,
    )

    metadata = twin.artifact["metadata"]
    assert "sf_percent_numeric" in twin.predictors
    assert metadata["binder_percent_predictors"] == BINDER_PERCENT_COLUMNS
    assert metadata["binder_percent_training_ranges"]["sf_percent_numeric"] == [10.0, 10.0]
    scenario = dict(metadata["input_defaults"])
    scenario["sf_percent_numeric"] = 10.0
    prediction = DigitalTwinService.predict_scenario(twin.artifact, scenario)
    assert np.isfinite(float(prediction["predicted_mean"]))


def test_future_dataset_with_varying_sf_automatically_enables_sf_response_axis():
    dataframe = DataService.load_csv(REFERENCE_DATASET)
    mix_numbers = pd.to_numeric(
        dataframe["mix_id"].astype(str).str.extract(r"(\d+)", expand=False),
        errors="coerce",
    ).fillna(1).astype(int)
    sf = 5.0 + 5.0 * ((mix_numbers - 1) % 3)
    fa = pd.to_numeric(dataframe["fa_percent_numeric"], errors="coerce")
    dataframe["sf_percent_numeric"] = sf
    dataframe["ggbs_percent_numeric"] = 100.0 - fa - sf

    ranking = ModelingService().compare_models(
        dataframe,
        "compressive_strength_mpa",
        _predictors(),
        algorithms=["Ridge Regression"],
        include_review_records=True,
    )
    twin = DigitalTwinService().build_twin(
        dataframe,
        "compressive_strength_mpa",
        _predictors(),
        method="Ridge Regression",
        include_review_records=True,
        ranking=ranking,
    )
    candidates = DigitalTwinService.map_axis_candidates(twin.artifact)
    assert "fa_percent_numeric" in candidates
    assert "ggbs_percent_numeric" in candidates
    assert "sf_percent_numeric" in candidates


def test_analytics_binder_profile_shows_fa_ggbs_and_sf_together():
    dataframe = DataService.load_csv(REFERENCE_DATASET)
    figure = AnalyticsService().create_figure(dataframe, "binder_composition")
    axis = figure.axes[0]
    _handles, labels = axis.get_legend_handles_labels()
    assert labels == ["FA (%)", "GGBS (%)", "SF (%)"]
    sf_line = axis.lines[2]
    assert np.allclose(np.asarray(sf_line.get_ydata(), dtype=float), 10.0)


def test_reference_sf_is_visible_as_response_axis_and_supports_explicit_exploration_range():
    dataframe = DataService.load_csv(REFERENCE_DATASET)
    ranking = ModelingService().compare_models(
        dataframe,
        "compressive_strength_mpa",
        _predictors(),
        algorithms=["Ridge Regression"],
        include_review_records=True,
    )
    twin = DigitalTwinService().build_twin(
        dataframe,
        "compressive_strength_mpa",
        _predictors(),
        method="Ridge Regression",
        include_review_records=True,
        ranking=ranking,
    )
    candidates = DigitalTwinService.map_axis_candidates(twin.artifact)
    assert "sf_percent_numeric" in candidates
    surface = DigitalTwinService.response_map(
        twin.artifact,
        "sf_percent_numeric",
        "aas_b_ratio",
        resolution=15,
        x_range=(5.0, 15.0),
        balance_field="ggbs_percent_numeric",
    )
    assert surface["sf_percent_numeric"].min() == 5.0
    assert surface["sf_percent_numeric"].max() == 15.0
    assert surface.attrs["x_range_extrapolative"] is True
    assert surface["outside_training_range_fields"].astype(str).str.contains("sf_percent_numeric").any()
