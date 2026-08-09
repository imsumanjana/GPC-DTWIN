from __future__ import annotations

from pathlib import Path

import pandas as pd

from gpc_dtwin.columns import DATA_COLUMNS
from gpc_dtwin.paths import REFERENCE_DATASET
from gpc_dtwin.services.active_learning_service import (
    ActiveLearningService, LearningVariable,
)
from gpc_dtwin.services.data_service import DataService


def _run():
    dataframe = DataService.load_csv(REFERENCE_DATASET)
    service = ActiveLearningService()
    variables = [
        LearningVariable("fa_percent_numeric", 0.0, 90.0),
        LearningVariable("ggbs_percent_numeric", 0.0, 90.0),
        LearningVariable("sf_percent_numeric", 9.0, 11.0),
        LearningVariable("aas_b_ratio", 0.40, 0.50),
    ]
    result = service.recommend(
        dataframe=dataframe,
        response="compressive_strength_mpa",
        predictors=[
            "fa_percent_numeric", "ggbs_percent_numeric",
            "sf_percent_numeric", "aas_b_ratio",
        ],
        variables=variables,
        method="Random Forest",
        strategy="Balanced exploration",
        direction="Maximize",
        candidate_count=90,
        recommendation_count=5,
        binder_closure=True,
        include_review_records=True,
        seed=17,
    )
    return dataframe, service, result


def test_active_learning_recommendations_and_plan():
    _, service, result = _run()
    assert len(result.recommendations) == 5
    assert {
        "predicted_mean", "prediction_std", "lower_bound", "upper_bound",
        "existing_design_distance", "novelty_score", "expected_improvement",
        "acquisition_score", "reliability_class",
    }.issubset(result.recommendations.columns)
    closure = result.recommendations[
        ["fa_percent_numeric", "ggbs_percent_numeric", "sf_percent_numeric"]
    ].sum(axis=1)
    assert (closure.sub(100.0).abs() < 1e-6).all()
    assert result.recommendations["acquisition_score"].between(0.0, 1.0).all()

    plan = service.experiment_plan(result)
    assert list(plan.columns) == DATA_COLUMNS
    assert len(plan) == 5
    assert plan["compressive_strength_mpa"].eq("").all()
    assert plan["compressive_strength_mpa"].dtype == object
    assert plan["record_id"].is_unique
    assert plan["notes"].str.contains("Estimated", case=False).all()


def test_active_learning_update_and_storage(tmp_path):
    dataframe, service, result = _run()
    plan = service.experiment_plan(result).iloc[[0]].copy()
    plan.loc[:, "compressive_strength_mpa"] = float(
        result.recommendations.iloc[0]["predicted_mean"]
    )
    plan.loc[:, "data_status"] = "VERIFIED"
    updated_data = pd.concat([dataframe, DataService.normalise(plan)], ignore_index=True)

    comparison = service.compare_update(result, updated_data)
    summary = comparison.updated_summary.iloc[0]
    assert int(summary["records_added"]) == 1
    assert len(comparison.comparison) == 7

    artifact = service.save_result(result, tmp_path, name="active_learning_test")
    loaded = service.load_result(artifact)
    assert loaded.response == result.response
    listed = service.list_saved_results(tmp_path)
    assert len(listed) == 1
    service.delete_result(artifact)
    assert service.list_saved_results(tmp_path).empty


def test_active_learning_figures_are_square():
    dataframe, service, result = _run()
    plan = service.experiment_plan(result).iloc[[0]].copy()
    plan.loc[:, "compressive_strength_mpa"] = float(
        result.recommendations.iloc[0]["predicted_mean"]
    )
    plan.loc[:, "data_status"] = "VERIFIED"
    updated_data = pd.concat([dataframe, DataService.normalise(plan)], ignore_index=True)
    update = service.compare_update(result, updated_data)

    figures = [
        service.acquisition_figure(result),
        service.recommendation_figure(result),
        service.update_figure(update),
    ]
    for figure in figures:
        width, height = figure.get_size_inches()
        assert width == height


def test_active_learning_priority_outputs_are_separate_figures():
    _, service, result = _run()
    figures = service.recommendation_figures(result)
    assert set(figures) == {"Response intervals", "Priority scores"}
    assert all(len(figure.axes) == 1 for figure in figures.values())
