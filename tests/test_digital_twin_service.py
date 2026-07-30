from pathlib import Path

import numpy as np

from gpc_dtwin.paths import REFERENCE_DATASET
from gpc_dtwin.services.data_service import DataService
from gpc_dtwin.services.digital_twin_service import DigitalTwinService


def _build_result():
    dataframe = DataService.load_csv(REFERENCE_DATASET)
    service = DigitalTwinService()
    result = service.build_twin(
        dataframe,
        response="compressive_strength_mpa",
        predictors=[
            "fa_percent_numeric",
            "ggbs_percent_numeric",
            "aas_b_ratio",
            "mechanical_test_age_days",
            "curing_regime",
        ],
        method="Gaussian Process",
        confidence_percent=95.0,
        include_review_records=True,
    )
    return dataframe, service, result


def test_gaussian_twin_builds_with_calibration_and_intervals():
    _, _, result = _build_result()
    assert result.observations >= 8
    assert result.method == "Gaussian Process"
    assert np.isfinite(result.metrics["rmse"])
    assert 0 <= result.metrics["coverage_percent"] <= 100
    required = {
        "observed_response", "predicted_mean", "prediction_std",
        "lower_bound", "upper_bound", "within_interval",
    }
    assert required.issubset(result.calibration.columns)
    assert (result.calibration["upper_bound"] >= result.calibration["lower_bound"]).all()


def test_twin_predicts_scenarios_batches_and_response_maps():
    dataframe, service, result = _build_result()
    metadata = result.artifact["metadata"]
    scenario = service.predict_scenario(result.artifact, metadata["input_defaults"])
    assert np.isfinite(float(scenario["predicted_mean"]))
    assert scenario["reliability_class"] in {"A", "B", "C", "D"}
    assert float(scenario["upper_bound"]) >= float(scenario["lower_bound"])

    batch = service.predict_dataframe(result.artifact, dataframe.head(6))
    assert len(batch) == 6
    assert {"predicted_mean", "reliability_class", "nearest_training_distance"}.issubset(batch.columns)

    surface = service.response_map(
        result.artifact, "ggbs_percent_numeric", "aas_b_ratio", resolution=18
    )
    assert len(surface) == 18 * 18
    assert surface["reliability_class"].isin(["A", "B", "C", "D"]).all()
    figure = service.response_map_figure(
        surface, "ggbs_percent_numeric", "aas_b_ratio", "Compressive strength (MPa)"
    )
    assert len(figure.axes) >= 3


def test_twin_artifact_round_trip(tmp_path: Path):
    _, service, result = _build_result()
    path = service.save_artifact(result.artifact, tmp_path)
    assert path.exists()
    loaded = service.load_artifact(path)
    assert loaded["metadata"]["method"] == "Gaussian Process"
    listing = service.list_saved_twins(tmp_path)
    assert len(listing) == 1
    service.delete_artifact(path)
    assert not path.exists()
    assert not path.with_suffix(".json").exists()
