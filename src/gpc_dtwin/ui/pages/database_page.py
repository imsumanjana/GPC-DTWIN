from __future__ import annotations

from PyQt6.QtCore import QSortFilterProxyModel, Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,     QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QTableView, QVBoxLayout, QWidget
)

from gpc_dtwin.columns import ESSENTIAL_COLUMNS, VERIFICATION_STATES
from gpc_dtwin.services.data_service import DataService
from gpc_dtwin.ui.models import DataFrameModel
from gpc_dtwin.ui.widgets import SectionHeader


class RecordFilterProxy(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.search_text = ""
        self.mix_value = "All"
        self.group_value = "All"
        self.status_value = "All"
        self.setDynamicSortFilter(True)

    def filterAcceptsRow(self, source_row, source_parent):
        model = self.sourceModel()
        df = model.dataframe
        if source_row >= len(df):
            return False
        row = df.iloc[source_row]
        if self.mix_value != "All" and str(row.get("mix_id", "")) != self.mix_value:
            return False
        if self.group_value != "All" and str(row.get("record_group", "")) != self.group_value:
            return False
        if self.status_value != "All" and str(row.get("data_status", "")) != self.status_value:
            return False
        if self.search_text:
            searchable = " ".join(str(value) for value in row.values).lower()
            if self.search_text.lower() not in searchable:
                return False
        return True

    def update_filters(self, search: str, mix: str, group: str, status: str) -> None:
        self.search_text = search.strip()
        self.mix_value = mix
        self.group_value = group
        self.status_value = status
        self.invalidateFilter()


class DatabasePage(QWidget):
    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.context = context
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 24)
        root.setSpacing(14)
        root.addWidget(SectionHeader(
            "Data explorer",
            "Search, filter, review, and export the active material-test dataset."
        ))

        controls = QFrame()
        controls.setObjectName("Card")
        layout = QHBoxLayout(controls)
        layout.setContentsMargins(14, 12, 14, 12)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search any visible field…")
        self.search.setClearButtonEnabled(True)
        self.mix = QComboBox()
        self.group = QComboBox()
        self.status = QComboBox()
        for label, widget in (("Mix", self.mix), ("Group", self.group), ("Status", self.status)):
            layout.addWidget(QLabel(label))
            layout.addWidget(widget)
        layout.insertWidget(0, self.search, 1)
        self.compact = QPushButton("Essential fields")
        self.compact.setCheckable(True)
        self.compact.setChecked(True)
        layout.addWidget(self.compact)
        root.addWidget(controls)

        self.model = DataFrameModel()
        self.proxy = RecordFilterProxy(self)
        self.proxy.setSourceModel(self.model)
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setWordWrap(False)
        root.addWidget(self.table, 1)

        actions = QHBoxLayout()
        self.count_label = QLabel()
        self.count_label.setObjectName("Muted")
        actions.addWidget(self.count_label)
        actions.addStretch()
        self.state_combo = QComboBox()
        self.state_combo.addItems(VERIFICATION_STATES)
        update_button = QPushButton("Update selected record")
        update_button.setObjectName("PrimaryButton")
        update_button.clicked.connect(self.update_selected)
        actions.addWidget(self.state_combo)
        actions.addWidget(update_button)
        root.addLayout(actions)

        self.search.textChanged.connect(self.apply_filters)
        self.mix.currentTextChanged.connect(self.apply_filters)
        self.group.currentTextChanged.connect(self.apply_filters)
        self.status.currentTextChanged.connect(self.apply_filters)
        self.compact.toggled.connect(self.apply_column_view)
        self.proxy.rowsInserted.connect(self.update_count)
        self.proxy.rowsRemoved.connect(self.update_count)
        self.context.data_changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        df = self.context.dataframe.copy()
        self.model.set_dataframe(df)
        self._populate(self.mix, DataService.unique_values(df, "mix_id"))
        self._populate(self.group, DataService.unique_values(df, "record_group"))
        self._populate(self.status, DataService.unique_values(df, "data_status"))
        self.apply_filters()
        self.apply_column_view()
        self.table.resizeColumnsToContents()
        for column in range(self.table.model().columnCount()):
            self.table.setColumnWidth(column, min(self.table.columnWidth(column), 230))

    @staticmethod
    def _populate(combo: QComboBox, values: list[str]) -> None:
        current = combo.currentText()
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("All")
        combo.addItems(values)
        index = combo.findText(current)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.blockSignals(False)

    def apply_filters(self) -> None:
        self.proxy.update_filters(
            self.search.text(), self.mix.currentText() or "All",
            self.group.currentText() or "All", self.status.currentText() or "All",
        )
        self.update_count()

    def apply_column_view(self) -> None:
        df = self.model.dataframe
        essential = set(ESSENTIAL_COLUMNS)
        for index, column in enumerate(df.columns):
            self.table.setColumnHidden(index, self.compact.isChecked() and column not in essential)

    def update_count(self) -> None:
        self.count_label.setText(f"{self.proxy.rowCount()} of {self.model.rowCount()} records")

    def update_selected(self) -> None:
        selection = self.table.selectionModel().selectedRows()
        if not selection:
            QMessageBox.information(self, "Select a record", "Select one row before updating its status.")
            return
        source_index = self.proxy.mapToSource(selection[0])
        record_id = str(self.model.dataframe.iloc[source_index.row()].get("record_id", ""))
        if not record_id:
            QMessageBox.warning(self, "Invalid record", "The selected row has no record identifier.")
            return
        try:
            self.context.update_status(record_id, self.state_combo.currentText())
        except Exception as error:
            QMessageBox.critical(self, "Update failed", str(error))
