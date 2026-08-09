from pathlib import Path

from gpc_dtwin.services.data_service import DataService
from gpc_dtwin.services.modeling_service import ModelingService

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data" / "reference" / "GPC_Reference_Dataset.csv"


def test_model_comparison_prediction_and_persistence(tmp_path):
    dataframe = DataService.load_csv(DATASET)
    subset = dataframe[dataframe["record_group"].isin([
        "AMBIENT_7D_MECHANICAL", "AMBIENT_28D_MECHANICAL"
    ])].copy()
    service = ModelingService()
    result = service.compare_models(
        subset,
        response="compressive_strength_mpa",
        predictors=["ggbs_percent_numeric", "mechanical_test_age_days"],
        algorithms=[
            "Linear Regression", "Ridge Regression", "Random Forest", "Gradient Boosting"
        ],
        include_review_records=True,
    )
    assert result.observations == 20
    assert len(result.rankings) == 4
    assert result.best_algorithm in set(result.rankings["algorithm"])
    assert result.rankings.iloc[0]["rmse"] >= 0
    assert result.rankings.iloc[0]["status"] == "Recommended"
    assert {"cv_rmse_mean", "cv_rmse_std", "status", "status_reason"}.issubset(result.rankings.columns)
    assert len(result.predictions) == 20
    assert not result.feature_influence.empty

    batch = service.predict_dataframe(result.artifact, subset)
    assert len(batch) == len(subset)
    assert "predicted_response" in batch.columns
    assert batch["predicted_response"].notna().all()

    scenario = service.predict_scenario(result.artifact, {
        "ggbs_percent_numeric": 70,
        "mechanical_test_age_days": 28,
    })
    assert isinstance(scenario, float)

    saved = service.save_artifact(result.artifact, tmp_path)
    assert saved.exists()
    assert saved.with_suffix(".json").exists()
    library = service.list_saved_models(tmp_path)
    assert len(library) == 1
    loaded = service.load_artifact(saved)
    loaded_prediction = service.predict_scenario(loaded, {
        "ggbs_percent_numeric": 70,
        "mechanical_test_age_days": 28,
    })
    assert abs(loaded_prediction - scenario) < 1e-10

    service.delete_artifact(saved)
    assert not saved.exists()
    assert not saved.with_suffix(".json").exists()


def test_model_diagnostics_are_available_as_separate_figures():
    dataframe = DataService.load_csv(DATASET)
    subset = dataframe[dataframe["record_group"].isin([
        "AMBIENT_7D_MECHANICAL", "AMBIENT_28D_MECHANICAL"
    ])].copy()
    service = ModelingService()
    result = service.compare_models(
        subset,
        response="compressive_strength_mpa",
        predictors=["ggbs_percent_numeric", "mechanical_test_age_days"],
        algorithms=["Linear Regression", "Ridge Regression"],
        include_review_records=True,
    )
    figures = service.diagnostic_figures(result, result.best_algorithm)
    assert set(figures) == {"Observed vs predicted", "Residuals"}
    assert all(len(figure.axes) == 1 for figure in figures.values())


def test_model_comparison_omits_response_incompatible_predictors():
    dataframe = DataService.load_csv(DATASET)
    service = ModelingService()
    result = service.compare_models(
        dataframe,
        response="compressive_strength_mpa",
        predictors=[
            "ggbs_percent_numeric",
            "mechanical_test_age_days",
            "acid_type",
            "acid_concentration_percent",
            "acid_exposure_days",
            "initial_mass_kg",
            "initial_compressive_strength_mpa",
        ],
        algorithms=["Ridge Regression", "Random Forest"],
        include_review_records=True,
    )

    assert "ggbs_percent_numeric" in result.predictors
    assert "mechanical_test_age_days" in result.predictors
    assert set(result.omitted_predictors) >= {
        "acid_type",
        "acid_concentration_percent",
        "acid_exposure_days",
        "initial_mass_kg",
        "initial_compressive_strength_mpa",
    }
    assert result.artifact["metadata"]["omitted_predictors"]
    assert len(result.rankings) == 2


def test_predictor_availability_is_response_specific():
    dataframe = DataService.load_csv(DATASET)
    available, unavailable = ModelingService.predictor_availability(
        dataframe,
        "compressive_strength_mpa",
        [
            "ggbs_percent_numeric",
            "mechanical_test_age_days",
            "acid_type",
            "acid_concentration_percent",
        ],
        include_review_records=True,
    )
    assert "ggbs_percent_numeric" in available
    assert "mechanical_test_age_days" in available
    assert "acid_type" in unavailable
    assert "acid_concentration_percent" in unavailable
