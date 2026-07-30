"""Reusable scrolling containers that preserve natural interface dimensions."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame, QLayout, QScrollArea, QSizePolicy, QWidget,
)


class ResponsiveScrollArea(QScrollArea):
    """A frameless area that adds scrollbars instead of squeezing its content."""

    def __init__(self, widget: QWidget | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("ResponsiveScrollArea")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        if widget is not None:
            self.set_content(widget)

    def set_content(self, widget: QWidget) -> None:
        layout = widget.layout()
        if layout is not None:
            layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setWidget(widget)


def scrollable_page(page: QWidget, minimum_width: int = 980) -> ResponsiveScrollArea:
    """Wrap a page so small windows scroll rather than compressing its blocks."""
    page.setMinimumWidth(minimum_width)
    return ResponsiveScrollArea(page)


def scrollable_panel(panel: QWidget, minimum_width: int = 0) -> ResponsiveScrollArea:
    """Wrap a dense control panel while preserving its natural vertical height."""
    if minimum_width > 0:
        panel.setMinimumWidth(minimum_width)
    area = ResponsiveScrollArea(panel)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    return area
