"""Shared application state and signals."""

from __future__ import annotations
from pathlib import Path
import pandas as pd
from PyQt6.QtCore import QObject, pyqtSignal

from .columns import VERIFICATION_STATES
from .database import SQLiteRepository
from .paths import DATABASE_PATH, REFERENCE_DATASET
from .services.audit_service import AuditService
from .services.data_service import DataService


class ApplicationContext(QObject):
    data_changed = pyqtSignal()
    audit_changed = pyqtSignal()
    message = pyqtSignal(str)

    def __init__(self, database_path: Path | str = DATABASE_PATH,
                 reference_dataset: Path | str = REFERENCE_DATASET):
        super().__init__()
        self.database_path = Path(database_path)
        self.reference_dataset = Path(reference_dataset)
        self.repository = SQLiteRepository(self.database_path)
        self.dataframe = pd.DataFrame()
        self.audit_issues = pd.DataFrame()
        self.last_import_path: Path | None = None

    def bootstrap(self) -> None:
        self.repository.initialize()
        if self.repository.count() == 0:
            if not self.reference_dataset.exists():
                raise FileNotFoundError(
                    f"Bundled reference dataset was not found: {self.reference_dataset}"
                )
            self.import_csv(self.reference_dataset, emit=False)
            self.message.emit("Reference dataset loaded into the project database.")
        else:
            self.reload(emit=False)
        self.run_audit(emit=False)

    def import_csv(self, path: Path | str, emit: bool = True) -> None:
        path = Path(path)
        dataframe = DataService.load_csv(path)
        self.repository.replace_records(dataframe)
        self.last_import_path = path
        self.reload(emit=False)
        self.run_audit(emit=False)
        if emit:
            self.data_changed.emit()
            self.audit_changed.emit()
            self.message.emit(f"Imported {len(dataframe)} records from {path.name}.")

    def reload(self, emit: bool = True) -> None:
        self.dataframe = self.repository.load_records()
        if emit:
            self.data_changed.emit()

    def run_audit(self, emit: bool = True) -> pd.DataFrame:
        self.audit_issues = AuditService().run(self.dataframe)
        if emit:
            self.audit_changed.emit()
            self.message.emit(f"Quality check completed with {len(self.audit_issues)} findings.")
        return self.audit_issues

    def update_status(self, record_id: str, status: str) -> None:
        if status not in VERIFICATION_STATES:
            raise ValueError(f"Unsupported data state: {status}")
        self.repository.update_data_status(record_id, status)
        self.reload(emit=False)
        self.run_audit(emit=False)
        self.data_changed.emit()
        self.audit_changed.emit()
        self.message.emit(f"{record_id} updated to {status}.")

    def export_csv(self, destination: Path | str) -> Path:
        path = self.repository.export_csv(destination)
        self.message.emit(f"Project data exported to {path.name}.")
        return path
