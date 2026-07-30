"""Reusable interface components."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure


class MetricCard(QFrame):
    def __init__(self, icon: str, label: str, value: str = "—", detail: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("MetricCard")
        self.setMinimumHeight(126)
        root = QHBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(14)

        icon_label = QLabel(icon)
        icon_label.setObjectName("MetricIcon")
        icon_label.setFixedSize(42, 42)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignTop)

        texts = QVBoxLayout()
        texts.setSpacing(3)
        self.value_label = QLabel(value)
        self.value_label.setObjectName("MetricValue")
        self.label_label = QLabel(label)
        self.label_label.setObjectName("MetricLabel")
        self.detail_label = QLabel(detail)
        self.detail_label.setObjectName("Muted")
        self.detail_label.setWordWrap(True)
        texts.addWidget(self.value_label)
        texts.addWidget(self.label_label)
        texts.addWidget(self.detail_label)
        texts.addStretch()
        root.addLayout(texts, 1)

    def set_value(self, value: object, detail: str | None = None) -> None:
        self.value_label.setText(str(value))
        if detail is not None:
            self.detail_label.setText(detail)


class SectionHeader(QWidget):
    def __init__(self, title: str, description: str = "", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")
        layout.addWidget(title_label)
        if description:
            description_label = QLabel(description)
            description_label.setObjectName("SectionDescription")
            description_label.setWordWrap(True)
            layout.addWidget(description_label)


class ChartCard(QFrame):
    def __init__(self, title: str, description: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)
        root.addWidget(SectionHeader(title, description))
        self.canvas = FigureCanvasQTAgg(Figure(figsize=(5, 3), constrained_layout=True))
        self.canvas.setMinimumHeight(260)
        root.addWidget(self.canvas, 1)

    def set_figure(self, figure: Figure) -> None:
        layout = self.layout()
        layout.removeWidget(self.canvas)
        self.canvas.setParent(None)
        self.canvas.deleteLater()
        self.canvas = FigureCanvasQTAgg(figure)
        self.canvas.setMinimumHeight(260)
        layout.addWidget(self.canvas, 1)
        self.canvas.draw_idle()


class ValuePill(QLabel):
    def __init__(self, text: str = "—", tone: str = "neutral", parent=None):
        super().__init__(text, parent)
        self.setProperty("tone", tone)
        self.setObjectName("ValuePill")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_value(self, text: object, tone: str = "neutral") -> None:
        self.setText(str(text))
        self.setProperty("tone", tone)
        self.style().unpolish(self)
        self.style().polish(self)
