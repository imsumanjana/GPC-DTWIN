from pathlib import Path

import pandas as pd

from gpc_dtwin.services.data_service import DataService
from gpc_dtwin.services.statistics_service import StatisticsService

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data" / "reference" / "GPC_Reference_Dataset.csv"


def test_descriptive_and_correlation():
    dataframe = DataService.load_csv(DATASET)
    service = StatisticsService()
    descriptive = service.descriptive(
        dataframe, ["ggbs_percent_numeric", "compressive_strength_mpa"]
    )
    assert not descriptive.empty
    assert {"variable", "count", "mean", "std", "missing", "cv_percent"}.issubset(descriptive.columns)
    correlation = service.correlation(
        dataframe, ["ggbs_percent_numeric", "compressive_strength_mpa"], "spearman"
    )
    assert correlation.shape == (2, 2)


def test_anova_and_grouped_regression():
    dataframe = DataService.load_csv(DATASET)
    service = StatisticsService()
    anova = service.one_way_anova(dataframe, "compressive_strength_mpa", "record_group")
    assert anova.groups >= 2
    assert anova.observations > 10
    assert 0 <= anova.effect_size_eta_squared <= 1

    subset = dataframe[dataframe["record_group"].isin([
        "AMBIENT_7D_MECHANICAL", "AMBIENT_28D_MECHANICAL"
    ])].copy()
    regression = service.regression(
        subset,
        "compressive_strength_mpa",
        ["ggbs_percent_numeric", "mechanical_test_age_days"],
        degree=2,
    )
    assert regression.observations == 20
    assert regression.rmse >= 0
    assert regression.predictions.shape[0] == 20
    assert not regression.coefficients.empty
