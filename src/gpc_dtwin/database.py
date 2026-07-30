"""SQLite persistence for canonical project records."""

from __future__ import annotations
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
import pandas as pd

from .columns import DATA_COLUMNS, NUMERIC_COLUMNS


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


class SQLiteRepository:
    def __init__(self, database_path: Path | str):
        self.database_path = Path(database_path)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        definitions = []
        for column in DATA_COLUMNS:
            sql_type = "REAL" if column in NUMERIC_COLUMNS else "TEXT"
            if column == "record_id":
                definitions.append(f'{_quote(column)} TEXT PRIMARY KEY')
            else:
                definitions.append(f'{_quote(column)} {sql_type}')
        schema = f"""
        CREATE TABLE IF NOT EXISTS material_records (
            {', '.join(definitions)}
        );
        CREATE TABLE IF NOT EXISTS app_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
        with self.connect() as connection:
            connection.executescript(schema)

    def count(self) -> int:
        self.initialize()
        with self.connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM material_records").fetchone()
            return int(row["count"])

    def replace_records(self, dataframe: pd.DataFrame) -> None:
        self.initialize()
        missing = [column for column in DATA_COLUMNS if column not in dataframe.columns]
        if missing:
            raise ValueError("Dataset is missing columns: " + ", ".join(missing))
        ordered = dataframe.loc[:, DATA_COLUMNS].copy()
        placeholders = ", ".join("?" for _ in DATA_COLUMNS)
        columns_sql = ", ".join(_quote(column) for column in DATA_COLUMNS)
        insert_sql = f"INSERT INTO material_records ({columns_sql}) VALUES ({placeholders})"
        records = []
        for values in ordered.itertuples(index=False, name=None):
            row = []
            for value in values:
                if pd.isna(value) or value == "":
                    row.append(None)
                else:
                    row.append(value.item() if hasattr(value, "item") else value)
            records.append(tuple(row))
        with self.connect() as connection:
            connection.execute("DELETE FROM material_records")
            connection.executemany(insert_sql, records)


    def append_records(self, dataframe: pd.DataFrame) -> int:
        """Append compatible records while rejecting duplicate record identifiers."""
        self.initialize()
        missing = [column for column in DATA_COLUMNS if column not in dataframe.columns]
        if missing:
            raise ValueError("Dataset is missing columns: " + ", ".join(missing))
        ordered = dataframe.loc[:, DATA_COLUMNS].copy()
        identifiers = ordered["record_id"].astype("string").str.strip()
        if identifiers.eq("").any() or identifiers.isna().any():
            raise ValueError("Every appended record requires a record_id.")
        if identifiers.duplicated().any():
            duplicates = sorted(identifiers[identifiers.duplicated()].unique().tolist())
            raise ValueError("Duplicate record IDs in the selected CSV: " + ", ".join(duplicates))

        placeholders = ", ".join("?" for _ in DATA_COLUMNS)
        columns_sql = ", ".join(_quote(column) for column in DATA_COLUMNS)
        insert_sql = f"INSERT INTO material_records ({columns_sql}) VALUES ({placeholders})"
        records = []
        for values in ordered.itertuples(index=False, name=None):
            row = []
            for value in values:
                if pd.isna(value) or value == "":
                    row.append(None)
                else:
                    row.append(value.item() if hasattr(value, "item") else value)
            records.append(tuple(row))
        try:
            with self.connect() as connection:
                connection.executemany(insert_sql, records)
        except sqlite3.IntegrityError as error:
            raise ValueError(
                "One or more record IDs already exist in the active dataset."
            ) from error
        return len(records)

    def load_records(self) -> pd.DataFrame:
        self.initialize()
        columns_sql = ", ".join(_quote(column) for column in DATA_COLUMNS)
        with self.connect() as connection:
            dataframe = pd.read_sql_query(
                f"SELECT {columns_sql} FROM material_records ORDER BY record_id", connection
            )
        for column in NUMERIC_COLUMNS:
            dataframe[column] = pd.to_numeric(dataframe[column], errors="coerce")
        return dataframe.loc[:, DATA_COLUMNS]

    def update_data_status(self, record_id: str, status: str) -> None:
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE material_records SET data_status = ? WHERE record_id = ?",
                (status, record_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"Record not found: {record_id}")

    def export_csv(self, destination: Path | str) -> Path:
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        self.load_records().to_csv(destination, index=False, encoding="utf-8-sig")
        return destination
