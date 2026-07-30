from pathlib import Path

from gpc_dtwin.database import SQLiteRepository
from gpc_dtwin.services.data_service import DataService

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data" / "reference" / "GPC_Reference_Dataset.csv"


def test_sqlite_round_trip_and_status_update(tmp_path):
    dataframe = DataService.load_csv(DATASET)
    repository = SQLiteRepository(tmp_path / "test.sqlite3")
    repository.replace_records(dataframe)
    loaded = repository.load_records()
    assert loaded.shape == dataframe.shape
    assert loaded["record_id"].tolist() == dataframe["record_id"].tolist()
    first_id = loaded.iloc[0]["record_id"]
    repository.update_data_status(first_id, "VERIFIED")
    refreshed = repository.load_records()
    assert refreshed.loc[refreshed["record_id"] == first_id, "data_status"].iloc[0] == "VERIFIED"
