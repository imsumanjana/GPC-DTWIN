"""Shared application state and signals."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil

import pandas as pd
from PyQt6.QtCore import QObject, pyqtSignal

from .columns import VERIFICATION_STATES
from .database import SQLiteRepository
from .paths import (
    BACKUP_DIR, DATABASE_PATH, LEGACY_DATABASE_PATHS, REFERENCE_DATASET,
    ensure_user_directories,
)
from .services.audit_service import AuditService
from .services.data_service import DataService


class ApplicationContext(QObject):
    data_changed = pyqtSignal()
    audit_changed = pyqtSignal()
    message = pyqtSignal(str)
    model_comparison_changed = pyqtSignal()
    active_twin_changed = pyqtSignal()

    def __init__(self, database_path: Path | str = DATABASE_PATH,
                 reference_dataset: Path | str = REFERENCE_DATASET):
        super().__init__()
        self.database_path = Path(database_path)
        self.reference_dataset = Path(reference_dataset)
        self.repository = SQLiteRepository(self.database_path)
        self.dataframe = pd.DataFrame()
        self.audit_issues = pd.DataFrame()
        self.last_import_path: Path | None = None
        self.last_backup_path: Path | None = None
        self.model_comparison = None
        self.active_twin_artifact: dict | None = None

    def clear_model_state(self, emit: bool = True) -> None:
        """Invalidate model/twin state whenever the active experimental data change."""
        had_comparison = self.model_comparison is not None
        had_twin = self.active_twin_artifact is not None
        self.model_comparison = None
        self.active_twin_artifact = None
        if emit and had_comparison:
            self.model_comparison_changed.emit()
        if emit and had_twin:
            self.active_twin_changed.emit()

    def set_model_comparison(self, result) -> None:
        self.model_comparison = result
        self.model_comparison_changed.emit()

    def set_active_twin(self, artifact: dict | None) -> None:
        self.active_twin_artifact = artifact
        self.active_twin_changed.emit()

    def matching_model_comparison(
        self,
        response: str,
        predictors: list[str],
        include_review_records: bool = False,
        group_column: str = "mix_id",
    ):
        result = self.model_comparison
        if result is None:
            return None
        metadata = result.artifact.get("metadata", {})
        if metadata.get("response") != response:
            return None
        if set(metadata.get("predictors", [])) != set(predictors):
            return None
        if bool(metadata.get("include_review_records", False)) != bool(include_review_records):
            return None
        if str(metadata.get("group_column", "mix_id")) != str(group_column):
            return None
        return result

    def bootstrap(self) -> None:
        ensure_user_directories()
        self._migrate_legacy_database()
        self.repository.initialize()
        if self.repository.count() == 0:
            if not self.reference_dataset.exists():
                raise FileNotFoundError(
                    f"Bundled reference dataset was not found: {self.reference_dataset}"
                )
            self.import_csv(self.reference_dataset, emit=False, create_backup=False)
            self.message.emit("Reference dataset loaded into the local database.")
        else:
            self.reload(emit=False)
        self.run_audit(emit=False)

    def _migrate_legacy_database(self) -> None:
        if self.database_path.exists():
            return
        for candidate in LEGACY_DATABASE_PATHS:
            if candidate.resolve() == self.database_path.resolve() or not candidate.is_file():
                continue
            try:
                SQLiteRepository.validate_database(candidate)
                self.database_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(candidate, self.database_path)
                return
            except Exception:
                continue

    @staticmethod
    def _backup_name(prefix: str = "gpc_dtwin") -> str:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{prefix}_{stamp}.sqlite3"

    def backup_database(self, destination: Path | str | None = None, emit: bool = True) -> Path:
        destination = Path(destination) if destination else BACKUP_DIR / self._backup_name()
        path = self.repository.backup(destination)
        self.last_backup_path = path
        if emit:
            self.message.emit(f"Database backup created: {path.name}.")
        return path

    def restore_database(self, source: Path | str, emit: bool = True) -> Path:
        source = Path(source)
        if self.repository.count() > 0:
            self.backup_database(emit=False)
        path = self.repository.restore(source)
        self.clear_model_state(emit=False)
        self.reload(emit=False)
        self.run_audit(emit=False)
        if emit:
            self.data_changed.emit()
            self.audit_changed.emit()
            self.message.emit(f"Database restored from {source.name}.")
        return path

    def import_csv(
        self, path: Path | str, emit: bool = True, create_backup: bool = True
    ) -> None:
        path = Path(path)
        dataframe = DataService.load_csv(path)
        if create_backup and self.database_path.exists() and self.repository.count() > 0:
            self.backup_database(emit=False)
        self.repository.replace_records(dataframe)
        self.clear_model_state(emit=False)
        self.last_import_path = path
        self.reload(emit=False)
        self.run_audit(emit=False)
        if emit:
            self.data_changed.emit()
            self.audit_changed.emit()
            self.message.emit(f"Imported {len(dataframe)} records from {path.name}.")

    def append_csv(self, path: Path | str, emit: bool = True) -> int:
        """Append compatible completed records without replacing the active dataset."""
        path = Path(path)
        dataframe = DataService.load_csv(path)
        appended = self.repository.append_records(dataframe)
        self.clear_model_state(emit=False)
        self.last_import_path = path
        self.reload(emit=False)
        self.run_audit(emit=False)
        if emit:
            self.data_changed.emit()
            self.audit_changed.emit()
            self.message.emit(f"Appended {appended} records from {path.name}.")
        return appended

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
        self.clear_model_state(emit=False)
        self.reload(emit=False)
        self.run_audit(emit=False)
        self.data_changed.emit()
        self.audit_changed.emit()
        self.message.emit(f"{record_id} updated to {status}.")

    def export_csv(self, destination: Path | str) -> Path:
        path = self.repository.export_csv(destination)
        self.message.emit(f"Project data exported to {path.name}.")
        return path
