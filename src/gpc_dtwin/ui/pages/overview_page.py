from __future__ import annotations

import pandas as pd
from PyQt6.QtWidgets import QGridLayout, QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from gpc_dtwin.services.analytics_service import AnalyticsService
from gpc_dtwin.services.audit_service import AuditService
from gpc_dtwin.ui.widgets import ChartCard, MetricCard, SectionHeader


class OverviewPage(QWidget):
    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.context = context
        self.analytics = AnalyticsService()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        self.root = QVBoxLayout(content)
        self.root.setContentsMargins(24, 22, 24, 24)
        self.root.setSpacing(16)
        self.root.addWidget(SectionHeader(
            "Dataset overview",
            "A concise view of records, test coverage, quality status, and material performance."
        ))

        cards = QGridLayout()
        cards.setHorizontalSpacing(12)
        cards.setVerticalSpacing(12)
        self.record_card = MetricCard("R", "Records")
        self.mix_card = MetricCard("M", "Mixes")
        self.group_card = MetricCard("T", "Test groups")
        self.review_card = MetricCard("!", "Records requiring review")
        self.finding_card = MetricCard("Q", "Quality findings")
        self.verified_card = MetricCard("✓", "Verified records")
        for index, card in enumerate([
            self.record_card, self.mix_card, self.group_card,
            self.review_card, self.finding_card, self.verified_card,
        ]):
            cards.addWidget(card, index // 3, index % 3)
        self.root.addLayout(cards)

        charts = QHBoxLayout()
        self.strength_chart = ChartCard(
            "Strength profile", "Ambient 28-day compressive strength across GGBS content."
        )
        self.heatmap_chart = ChartCard(
            "Performance map", "Normalised mechanical and non-destructive properties."
        )
        charts.addWidget(self.strength_chart, 1)
        charts.addWidget(self.heatmap_chart, 1)
        self.root.addLayout(charts)
        self.root.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

        self.context.data_changed.connect(self.refresh)
        self.context.audit_changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        df = self.context.dataframe
        issues = self.context.audit_issues
        mixes = df["mix_id"].nunique() if "mix_id" in df.columns else 0
        groups = df["record_group"].nunique() if "record_group" in df.columns else 0
        status = df.get("data_status", pd.Series(dtype=str)).fillna("").astype(str)
        review_count = int(status.str.contains("REVIEW|CONFLICT", case=False, regex=True).sum())
        verified_count = int(status.str.startswith("VERIFIED").sum())
        summary = AuditService.summary(issues)

        self.record_card.set_value(len(df), f"{len(df.columns)} fields")
        self.mix_card.set_value(mixes, "Distinct material compositions")
        self.group_card.set_value(groups, "Available measurement groups")
        self.review_card.set_value(review_count, "Resolve before combined analysis")
        self.finding_card.set_value(summary.total, f"{summary.critical} critical · {summary.warning} warning")
        self.verified_card.set_value(verified_count, "Reviewed and accepted records")

        self.strength_chart.set_figure(self.analytics.create_figure(df, "compressive_28d"))
        self.heatmap_chart.set_figure(self.analytics.create_figure(df, "property_heatmap"))
