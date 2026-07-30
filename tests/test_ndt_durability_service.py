from __future__ import annotations

import pandas as pd

from gpc_dtwin.services.ndt_durability_service import NDTDurabilityService


def _dataset() -> pd.DataFrame:
    from gpc_dtwin.paths import REFERENCE_DATASET
    return pd.read_csv(REFERENCE_DATASET)


def test_ndt_matching_and_feature_set_comparison():
    dataframe = _dataset()
    service = NDTDurabilityService()
    matched = service.prepare_ndt_matched_data(dataframe, include_review_records=True)
    assert len(matched) == 10
    assert matched["measured_compressive_strength_mpa"].notna().all()
    assert matched["upv_m_s"].notna().all()

    result = service.compare_ndt_fusion(
        dataframe, algorithm="Ridge Regression", include_review_records=True
    )
    assert result.observations == 10
    assert len(result.rankings) == 5
    assert result.best_feature_set in result.artifacts
    assert result.predictions["feature_set"].nunique() == 5
    assert result.best_metrics["rmse"] >= 0


def test_ndt_prediction_and_model_library(tmp_path):
    service = NDTDurabilityService()
    result = service.compare_ndt_fusion(
        _dataset(), algorithm="Ridge Regression", include_review_records=True
    )
    artifact = result.artifacts[result.best_feature_set]
    estimate = service.predict_ndt_scenario(artifact, {
        "upv_m_s": 6429,
        "rebound_estimated_strength_mpa": 42.33,
        "fa_percent_numeric": 20,
        "ggbs_percent_numeric": 70,
        "sf_percent_numeric": 10,
    })
    assert estimate["predicted_compressive_strength_mpa"] > 0
    assert estimate["reliability_class"] in {"A", "B", "C", "D"}

    path = service.save_ndt_artifact(artifact, tmp_path)
    assert path.exists()
    assert path.with_suffix(".json").exists()
    loaded = service.load_ndt_artifact(path)
    assert loaded["metadata"]["feature_set"] == artifact["metadata"]["feature_set"]
    listing = service.list_saved_ndt_models(tmp_path)
    assert len(listing) == 1
    service.delete_artifact(path)
    assert not path.exists()


def test_durability_profile_and_figures():
    service = NDTDurabilityService()
    dataframe = _dataset()
    profile = service.durability_profile(dataframe)
    assert profile.records == 8
    assert profile.media == 2
    assert profile.mixes == 4
    assert profile.ranking["durability_score"].is_monotonic_decreasing
    assert profile.ranking["durability_score"].between(0, 100).all()
    assert profile.best_mix == "M3"

    figures = [
        service.durability_score_figure(profile),
        service.durability_initial_residual_figure(dataframe),
        service.durability_heatmap_figure(dataframe, "strength_retention_percent"),
        service.durability_heatmap_figure(dataframe, "mass_change_percent_derived"),
    ]
    assert all(len(figure.axes) >= 1 for figure in figures)


def test_durability_twin_scenario_sweep_and_persistence(tmp_path):
    service = NDTDurabilityService()
    result = service.build_durability_twin(
        _dataset(),
        response="residual_compressive_strength_mpa",
        method="Forest Ensemble",
        confidence_percent=95.0,
    )
    assert result.observations == 8
    assert result.artifact["metadata"]["artifact_type"] == "durability_twin"

    values = {
        "fa_percent_numeric": 20,
        "ggbs_percent_numeric": 70,
        "sf_percent_numeric": 10,
        "initial_compressive_strength_mpa": 47.3,
        "acid_type": "HCl",
        "acid_concentration_percent": 5,
        "acid_exposure_days": 28,
    }
    estimate = service.predict_durability_scenario(result.artifact, values)
    assert estimate["predicted_mean"] > 0
    assert estimate["lower_bound"] <= estimate["upper_bound"]

    sweep = service.durability_sweep(
        result.artifact, values, "ggbs_percent_numeric", resolution=25
    )
    assert len(sweep) == 25
    assert sweep["ggbs_percent_numeric"].is_monotonic_increasing
    figure = service.durability_sweep_figure(
        sweep, "ggbs_percent_numeric", "residual_compressive_strength_mpa"
    )
    assert len(figure.axes) == 1

    path = service.save_durability_artifact(result.artifact, tmp_path)
    assert path.exists()
    loaded = service.load_durability_artifact(path)
    assert loaded["metadata"]["artifact_type"] == "durability_twin"
    listing = service.list_saved_durability_models(tmp_path)
    assert len(listing) == 1
    service.delete_artifact(path)
    assert not path.exists()


def test_ndt_figures():
    service = NDTDurabilityService()
    result = service.compare_ndt_fusion(
        _dataset(), algorithm="Gradient Boosting", include_review_records=True
    )
    figures = [
        service.ndt_comparison_figure(result),
        service.ndt_observed_predicted_figure(result),
        service.ndt_residual_figure(result),
    ]
    assert all(len(figure.axes) == 1 for figure in figures)
