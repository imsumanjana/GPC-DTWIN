from __future__ import annotations

import pandas as pd
from matplotlib.figure import Figure
from PyQt6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from gpc_dtwin.services.audit_service import AuditService
from gpc_dtwin.services.data_service import DataService
from gpc_dtwin.ui.widgets import ChartCard, MetricCard, SectionHeader


class DashboardPage(QWidget):
    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.context = context

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)

        content = QWidget()
        self.layout_root = QVBoxLayout(content)
        self.layout_root.setContentsMargins(24, 22, 24, 30)
        self.layout_root.setSpacing(18)
        scroll.setWidget(content)

        self.layout_root.addWidget(SectionHeader(
            "Research data overview",
            "A live summary of the current SQLite project database and deterministic audit state."
        ))

        cards = QGridLayout()
        cards.setHorizontalSpacing(14)
        cards.setVerticalSpacing(14)
        self.records = MetricCard("R", "Experimental records", "0", "All test-condition rows")
        self.mixes = MetricCard("M", "Distinct mixes", "0", "M1–M10 design space")
        self.conflicts = MetricCard("!", "Conflict-flagged records", "0", "Require laboratory confirmation")
        self.audit = MetricCard("A", "Audit findings", "0", "Critical, warning, and information")
        for index, card in enumerate([self.records, self.mixes, self.conflicts, self.audit]):
            cards.addWidget(card, index // 4, index % 4)
        self.layout_root.addLayout(cards)

        charts = QHBoxLayout()
        charts.setSpacing(14)
        self.group_chart = ChartCard("Test-group coverage", "Number of structured records per experimental category.")
        self.status_chart = ChartCard("Data-status distribution", "Current source and verification states.")
        charts.addWidget(self.group_chart, 1)
        charts.addWidget(self.status_chart, 1)
        self.layout_root.addLayout(charts)

        self.performance_chart = ChartCard(
            "28-day ambient compressive strength",
            "The dedicated mechanical-properties table is used for this overview."
        )
        self.layout_root.addWidget(self.performance_chart)
        self.layout_root.addStretch()

        self.context.data_changed.connect(self.refresh)
        self.context.audit_changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        df = self.context.dataframe
        issues = self.context.audit_issues
        self.records.set_value(len(df))
        self.mixes.set_value(df["mix_id"].nunique() if not df.empty else 0)
        conflict_count = int(df["data_status"].fillna("").astype(str).str.contains(
            "CONFLICT", case=False
        ).sum()) if not df.empty else 0
        self.conflicts.set_value(conflict_count)
        summary = AuditService.summary(issues)
        self.audit.set_value(summary.total, f"{summary.critical} critical · {summary.warning} warning")

        self.group_chart.set_figure(self._group_figure(df))
        self.status_chart.set_figure(self._status_figure(df))
        self.performance_chart.set_figure(self._performance_figure(df))

    @staticmethod
    def _group_figure(df: pd.DataFrame) -> Figure:
        figure = Figure(figsize=(5.2, 3.2), constrained_layout=True)
        axis = figure.add_subplot(111)
        counts = DataService.record_group_counts(df)
        labels = [label.replace("_", " ").title() for label in counts.index]
        axis.barh(labels[::-1], counts.values[::-1])
        axis.set_xlabel("Records (count)")
        axis.grid(axis="x", alpha=0.22)
        axis.tick_params(axis="y", labelsize=8)
        return figure

    @staticmethod
    def _status_figure(df: pd.DataFrame) -> Figure:
        figure = Figure(figsize=(5.2, 3.2), constrained_layout=True)
        axis = figure.add_subplot(111)
        if df.empty:
            axis.text(0.5, 0.5, "No records", ha="center", va="center")
            return figure
        status = df["data_status"].fillna("UNSPECIFIED").astype(str)
        status = status.str.replace(";", ";\n", regex=False)
        counts = status.value_counts().head(8)
        axis.barh(counts.index[::-1], counts.values[::-1])
        axis.set_xlabel("Records (count)")
        axis.grid(axis="x", alpha=0.22)
        axis.tick_params(axis="y", labelsize=8)
        return figure

    @staticmethod
    def _performance_figure(df: pd.DataFrame) -> Figure:
        figure = Figure(figsize=(9, 3.5), constrained_layout=True)
        axis = figure.add_subplot(111)
        if df.empty:
            axis.text(0.5, 0.5, "No records", ha="center", va="center")
            return figure
        data = df[df["record_group"] == "AMBIENT_28D_MECHANICAL"].copy()
        data["compressive_strength_mpa"] = pd.to_numeric(data["compressive_strength_mpa"], errors="coerce")
        data = data.sort_values("mix_id", key=lambda s: s.str.extract(r"(\d+)")[0].astype(int))
        axis.plot(data["mix_id"], data["compressive_strength_mpa"], marker="o")
        axis.set_ylabel("Compressive strength (MPa)")
        axis.set_xlabel("Mix")
        axis.grid(True, alpha=0.22)
        return figure
