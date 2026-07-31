"""Reusable interface components."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QScrollArea, QSizePolicy, QStyle,
    QToolButton, QVBoxLayout, QWidget,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure


class CompactToolbar(QScrollArea):
    """Single-row toolbar that scrolls horizontally rather than wrapping."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CompactToolbarScroll")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWidgetResizable(True)
        self.setFixedHeight(56)

        self.content = QFrame()
        self.content.setObjectName("CompactToolbar")
        self.content.setSizePolicy(
            QSizePolicy.Policy.MinimumExpanding,
            QSizePolicy.Policy.Fixed,
        )
        self.row = QHBoxLayout(self.content)
        self.row.setContentsMargins(10, 7, 10, 7)
        self.row.setSpacing(7)
        self.setWidget(self.content)

    def add_metric(self, label: str, pill: QWidget) -> None:
        caption = QLabel(label)
        caption.setObjectName("CompactToolbarLabel")
        caption.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        self.row.addWidget(caption)
        self.row.addWidget(pill)

    def add_widget(self, widget: QWidget, stretch: int = 0) -> None:
        self.row.addWidget(widget, stretch)

    def add_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("CompactToolbarLabel")
        self.row.addWidget(label)
        return label

    def add_stretch(self, stretch: int = 1) -> None:
        self.row.addStretch(stretch)

    def add_action(
        self,
        icon: QStyle.StandardPixmap,
        tooltip: str,
        slot,
        *,
        accent: bool = False,
    ) -> QToolButton:
        button = QToolButton(self.content)
        button.setObjectName("CompactToolbarButton")
        button.setProperty("accent", accent)
        button.setIcon(button.style().standardIcon(icon))
        button.setIconSize(QSize(18, 18))
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)
        button.setFixedSize(34, 32)
        button.clicked.connect(slot)
        self.row.addWidget(button)
        return button

    def finalize(self) -> None:
        self.content.adjustSize()
        self.content.setMinimumWidth(max(self.content.sizeHint().width(), 420))


class MetricCard(QFrame):
    def __init__(self, icon: str, label: str, value: str = "—", detail: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("MetricCard")
        self.setMinimumHeight(126)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
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
        title_label.setWordWrap(True)
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
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)
        root.addWidget(SectionHeader(title, description))
        self.canvas = FigureCanvasQTAgg(Figure(figsize=(5, 5), constrained_layout=True))
        self.canvas.setMinimumSize(360, 360)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root.addWidget(self.canvas, 1)

    def set_figure(self, figure: Figure) -> None:
        layout = self.layout()
        layout.removeWidget(self.canvas)
        self.canvas.setParent(None)
        self.canvas.deleteLater()
        self.canvas = FigureCanvasQTAgg(figure)
        self.canvas.setMinimumSize(360, 360)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
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
