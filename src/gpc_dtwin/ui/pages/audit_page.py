from __future__ import annotations

from PyQt6.QtWidgets import (
    QAbstractItemView,     QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QTableView, QVBoxLayout, QWidget
)

from gpc_dtwin.services.audit_service import AuditService
from gpc_dtwin.ui.models import DataFrameModel
from gpc_dtwin.ui.widgets import MetricCard, SectionHeader


class AuditPage(QWidget):
    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.context = context
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 24)
        root.setSpacing(14)

        heading = QHBoxLayout()
        heading.addWidget(SectionHeader(
            "Quality check",
            "Repeatable checks for identity, composition, ranges, completeness, provenance, and calculations."
        ), 1)
        run_button = QPushButton("Run quality check")
        run_button.setObjectName("PrimaryButton")
        run_button.clicked.connect(self.context.run_audit)
        heading.addWidget(run_button)
        root.addLayout(heading)

        metrics = QGridLayout()
        self.total = MetricCard("Q", "Total findings")
        self.critical = MetricCard("×", "Critical")
        self.warning = MetricCard("!", "Warnings")
        self.info = MetricCard("i", "Information")
        for index, card in enumerate([self.total, self.critical, self.warning, self.info]):
            metrics.addWidget(card, 0, index)
        root.addLayout(metrics)

        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        self.model = DataFrameModel()
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        card_layout.addWidget(self.table)
        root.addWidget(card, 1)

        self.context.audit_changed.connect(self.refresh)
        self.context.data_changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        issues = self.context.audit_issues
        summary = AuditService.summary(issues)
        self.total.set_value(summary.total, "All quality findings")
        self.critical.set_value(summary.critical, "Requires correction")
        self.warning.set_value(summary.warning, "Requires review")
        self.info.set_value(summary.information, "Context or missing metadata")
        self.model.set_dataframe(issues)
        self.table.resizeColumnsToContents()
        for column in range(self.model.columnCount()):
            self.table.setColumnWidth(column, min(self.table.columnWidth(column), 340))
