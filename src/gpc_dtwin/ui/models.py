"""Qt table model backed by a pandas DataFrame."""

from __future__ import annotations

import math

import pandas as pd
from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt

from gpc_dtwin.columns import COLUMN_LABELS


class DataFrameModel(QAbstractTableModel):
    def __init__(self, dataframe: pd.DataFrame | None = None, parent=None):
        super().__init__(parent)
        self._dataframe = dataframe.copy() if dataframe is not None else pd.DataFrame()

    @property
    def dataframe(self) -> pd.DataFrame:
        return self._dataframe

    def set_dataframe(self, dataframe: pd.DataFrame) -> None:
        self.beginResetModel()
        self._dataframe = dataframe.copy()
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._dataframe.index)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._dataframe.columns)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        value = self._dataframe.iat[index.row(), index.column()]
        if role == Qt.ItemDataRole.UserRole:
            return "" if pd.isna(value) else value
        if role == Qt.ItemDataRole.DisplayRole:
            if pd.isna(value):
                return ""
            if isinstance(value, float):
                if math.isclose(value, round(value), abs_tol=1e-10):
                    return str(int(round(value)))
                return f"{value:.4f}".rstrip("0").rstrip(".")
            return str(value)
        if role == Qt.ItemDataRole.TextAlignmentRole and isinstance(value, (int, float)):
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        return None

    def headerData(self, section: int, orientation: Qt.Orientation,
                   role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            column = str(self._dataframe.columns[section])
            return COLUMN_LABELS.get(column, column.replace("_", " ").title())
        return str(section + 1)

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:
        if self._dataframe.empty or column >= len(self._dataframe.columns):
            return
        self.layoutAboutToBeChanged.emit()
        name = self._dataframe.columns[column]
        self._dataframe = self._dataframe.sort_values(
            by=name,
            ascending=order == Qt.SortOrder.AscendingOrder,
            na_position="last",
            kind="stable",
        ).reset_index(drop=True)
        self.layoutChanged.emit()
