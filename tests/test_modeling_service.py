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
