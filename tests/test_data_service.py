from pathlib import Path

import pandas as pd

from gpc_dtwin.columns import DATA_COLUMNS
from gpc_dtwin.services.data_service import DataService

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data" / "reference" / "GPC_Reference_Dataset.csv"


def test_reference_dataset_shape_and_schema():
    dataframe = DataService.load_csv(DATASET)
    assert dataframe.shape == (72, 44)
    assert list(dataframe.columns) == DATA_COLUMNS
    assert dataframe["record_id"].is_unique
    assert dataframe["mix_id"].nunique() == 10
    assert set(dataframe["data_status"]) == {
        "IMPORTED", "IMPORTED_WITH_DERIVED_VALUES", "REQUIRES_REVIEW"
    }
    labels = dataframe[["mix_id", "mix_proportion_label"]].drop_duplicates().set_index("mix_id")
    assert labels.loc["M6", "mix_proportion_label"] == "50:40:10"
    assert labels.loc["M10", "mix_proportion_label"] == "90:0:10"


def test_dataset_has_generic_provenance():
    dataframe = pd.read_csv(DATASET, encoding="utf-8-sig")
    assert dataframe["dataset_origin"].eq("Bundled reference dataset").all()
