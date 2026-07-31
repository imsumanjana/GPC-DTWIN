"""Consistent workspace sizing and interaction defaults."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg

from PyQt6.QtWidgets import (
    QAbstractItemView, QComboBox, QFormLayout, QPushButton, QSplitter,
    QTabWidget, QTableView, QWidget,
)


def polish_workspace(page: QWidget) -> None:
    """Apply readable defaults without forcing content into the available area."""
    for form in page.findChildren(QFormLayout):
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setHorizontalSpacing(max(form.horizontalSpacing(), 12))
        form.setVerticalSpacing(max(form.verticalSpacing(), 9))

    for table in page.findChildren(QTableView):
        table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setDefaultSectionSize(30)
        table.horizontalHeader().setMinimumSectionSize(72)

    for tabs in page.findChildren(QTabWidget):
        tabs.tabBar().setUsesScrollButtons(True)
        tabs.tabBar().setElideMode(Qt.TextElideMode.ElideRight)
        tabs.setDocumentMode(True)

    for splitter in page.findChildren(QSplitter):
        splitter.setChildrenCollapsible(False)
        splitter.setOpaqueResize(True)
        splitter.setHandleWidth(6)

    for button in page.findChildren(QPushButton):
        if button.minimumHeight() < 32:
            button.setMinimumHeight(32)

    for combo in page.findChildren(QComboBox):
        if combo.minimumWidth() < 140:
            combo.setMinimumWidth(140)

    # Charts keep a readable natural area. The surrounding workspace or figure
    # tab supplies scrollbars on smaller displays instead of crushing the plot.
    for canvas in page.findChildren(FigureCanvasQTAgg):
        if canvas.minimumWidth() < 520 or canvas.minimumHeight() < 420:
            canvas.setMinimumSize(max(canvas.minimumWidth(), 520), max(canvas.minimumHeight(), 420))
