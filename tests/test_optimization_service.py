from __future__ import annotations

import numpy as np
import pytest

from gpc_dtwin.paths import REFERENCE_DATASET
from gpc_dtwin.services.data_service import DataService
from gpc_dtwin.services.optimization_service import (
    ConstraintDefinition, ObjectiveDefinition, OptimizationRunResult,
    OptimizationService, TargetDefinition, VariableDefinition,
)


@pytest.fixture(scope="module")
def prepared_results():
    dataframe = DataService.load_csv(REFERENCE_DATASET)
    service = OptimizationService()
    variables = [
        VariableDefinition("fa_percent_numeric", 0.0, 90.0),
        VariableDefinition("ggbs_percent_numeric", 0.0, 90.0),
        VariableDefinition("sf_percent_numeric", 9.5, 10.5),
        VariableDefinition("aas_b_ratio", 0.40, 0.50),
    ]
    predictors = [
        "fa_percent_numeric", "ggbs_percent_numeric", "sf_percent_numeric", "aas_b_ratio"
    ]
    optimization = service.optimize(
        dataframe=dataframe,
        objectives=[
            ObjectiveDefinition("compressive_strength_mpa", "Maximize", 1.0),
            ObjectiveDefinition("slump_mm", "Maximize", 0.6),
        ],
        constraints=[
            ConstraintDefinition("compressive_strength_mpa", "At least", 20.0),
        ],
        variables=variables,
        predictors=predictors,
        method="Random Forest",
        population_size=16,
        generations=2,
        uncertainty_weight=0.25,
        binder_closure=True,
        include_review_records=True,
        seed=19,
    )
    inverse = service.inverse_design(
        dataframe=dataframe,
        targets=[
            TargetDefinition("compressive_strength_mpa", "At least", 35.0, 1.0),
            TargetDefinition("slump_mm", "At least", 55.0, 0.5),
        ],
        variables=variables,
        predictors=predictors,
        method="Random Forest",
        candidate_count=250,
        recommendation_count=8,
        uncertainty_weight=0.25,
        binder_closure=True,
        include_review_records=True,
        seed=23,
    )
    return service, optimization, inverse


def test_pareto_search_returns_closed_feasible_solutions(prepared_results):
    _, result, _ = prepared_results
    assert isinstance(result, OptimizationRunResult)
    assert result.candidates_evaluated == 48
    assert not result.pareto_solutions.empty
    totals = result.pareto_solutions[
        ["fa_percent_numeric", "ggbs_percent_numeric", "sf_percent_numeric"]
    ].sum(axis=1)
    assert np.allclose(totals.to_numpy(), 100.0, atol=1e-6)
    assert (result.pareto_solutions["pareto_rank"] == 0).all()
    assert result.surrogate_summary["response"].nunique() == 2


def test_inverse_design_ranks_diverse_recommendations(prepared_results):
    _, _, result = prepared_results
    assert len(result.recommendations) == 8
    assert result.recommendations["design_loss"].is_monotonic_increasing
    totals = result.recommendations[
        ["fa_percent_numeric", "ggbs_percent_numeric", "sf_percent_numeric"]
    ].sum(axis=1)
    assert np.allclose(totals.to_numpy(), 100.0, atol=1e-6)
    assert set(result.recommendations["reliability_class"]).issubset({"A", "B", "C", "D"})


def test_run_storage_and_figures(prepared_results, tmp_path):
    service, optimization, inverse = prepared_results
    optimization_path = service.save_result(optimization, tmp_path, "pareto_check")
    inverse_path = service.save_result(inverse, tmp_path, "inverse_check")
    assert optimization_path.exists()
    assert inverse_path.exists()
    listed = service.list_saved_results(tmp_path)
    assert len(listed) == 2
    loaded = service.load_result(optimization_path)
    assert isinstance(loaded, OptimizationRunResult)
    assert len(service.pareto_figure(loaded).axes) >= 1
    assert len(service.parallel_figure(loaded).axes) == 1
    assert len(service.inverse_figure(inverse).axes) >= 2
    service.delete_result(optimization_path)
    assert not optimization_path.exists()


def test_inverse_design_outputs_are_separate_figures(prepared_results):
    service, _, inverse = prepared_results
    figures = service.inverse_figures(inverse)
    assert set(figures) == {"Ranked alternatives", "Target attainment"}
    assert len(figures["Ranked alternatives"].axes) == 1
    assert len(figures["Target attainment"].axes) >= 2  # main plot and colour bar
