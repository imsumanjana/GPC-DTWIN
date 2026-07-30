"""Dataset loading, compatibility conversion, and dataframe helpers."""

from __future__ import annotations
from pathlib import Path
import re
import pandas as pd

from gpc_dtwin.columns import DATA_COLUMNS, NUMERIC_COLUMNS


class DatasetSchemaError(ValueError):
    pass


class DataService:
    LEGACY_ALIASES = {
        "source_document": "dataset_origin",
        "source_table": "data_block",
        "source_page": "data_locator",
        "mix_proportion_reported": "mix_proportion_label",
        "reported_al_ratio": "activator_ratio_label",
        "upv_quality_reported": "upv_quality_label",
    }

    @staticmethod
    def load_csv(path: Path | str) -> pd.DataFrame:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(path)
        dataframe = pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
        return DataService.normalise(dataframe)

    @staticmethod
    def normalise(dataframe: pd.DataFrame) -> pd.DataFrame:
        dataframe = dataframe.copy()
        rename = {
            old: new for old, new in DataService.LEGACY_ALIASES.items()
            if old in dataframe.columns and new not in dataframe.columns
        }
        legacy_schema = bool(rename)
        if rename:
            dataframe = dataframe.rename(columns=rename)
        if legacy_schema and "dataset_origin" in dataframe.columns:
            dataframe["dataset_origin"] = "Imported legacy dataset"

        missing = [column for column in DATA_COLUMNS if column not in dataframe.columns]
        if missing:
            raise DatasetSchemaError("Missing required columns: " + ", ".join(missing))
        extra = [column for column in dataframe.columns if column not in DATA_COLUMNS]
        if extra:
            dataframe = dataframe.drop(columns=extra)

        result = dataframe.loc[:, DATA_COLUMNS].copy()
        for column in NUMERIC_COLUMNS:
            result[column] = pd.to_numeric(result[column], errors="coerce")
        for column in set(DATA_COLUMNS) - NUMERIC_COLUMNS:
            result[column] = result[column].fillna("").astype(str).str.strip()
        return result

    @staticmethod
    def display_copy(dataframe: pd.DataFrame) -> pd.DataFrame:
        return dataframe.copy().where(pd.notna(dataframe), "")

    @staticmethod
    def unique_values(dataframe: pd.DataFrame, column: str) -> list[str]:
        if column not in dataframe.columns:
            return []
        values = [
            value for value in dataframe[column].dropna().astype(str).str.strip().unique().tolist()
            if value
        ]
        if column == "mix_id":
            def key(value: str):
                match = re.search(r"\d+", value)
                return (int(match.group()) if match else 10**9, value)
            return sorted(values, key=key)
        return sorted(values)

    @staticmethod
    def record_group_counts(dataframe: pd.DataFrame) -> pd.Series:
        if dataframe.empty:
            return pd.Series(dtype=int)
        return dataframe["record_group"].fillna("UNSPECIFIED").value_counts()

    @staticmethod
    def filter_group(dataframe: pd.DataFrame, group: str | None) -> pd.DataFrame:
        if not group or group == "All records":
            return dataframe.copy()
        return dataframe[dataframe["record_group"] == group].copy()

    @staticmethod
    def write_template(destination: Path | str) -> Path:
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(columns=DATA_COLUMNS).to_csv(destination, index=False, encoding="utf-8-sig")
        return destination
