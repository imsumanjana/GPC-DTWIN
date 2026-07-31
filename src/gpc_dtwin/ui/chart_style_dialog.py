"""Icon-driven application-wide chart appearance and preset controls."""

from __future__ import annotations

from collections.abc import Iterable
import json
import re

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from PyQt6.QtCore import QEvent, QObject, QSettings, Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QColorDialog, QComboBox, QDialog, QDoubleSpinBox,
    QFontComboBox, QFormLayout, QFrame, QHBoxLayout, QInputDialog, QLabel,
    QMessageBox, QPushButton, QScrollArea, QSpinBox, QTabWidget, QToolButton,
    QVBoxLayout, QWidget,
)

from gpc_dtwin.chart_presets import BUILT_IN_PRESETS, preset_style
from gpc_dtwin.chart_style import ChartStyle, apply_chart_style, style_for_figure
from gpc_dtwin.ui.export_preview_dialog import ExportPreviewDialog


STYLE_SETTINGS_KEY = "charts/style_json"  # retained for settings compatibility
APPLICATION_STYLE_KEY = "charts/application_style_json"
CUSTOM_PRESETS_KEY = "charts/custom_presets_json"
WORKSPACE_STYLE_PREFIX = "charts/workspace/"
CHART_STYLE_PREFIX = "charts/chart/"



def _available_qt_event_types(*names: str) -> frozenset:
    """Return only event enum members provided by the active Qt binding."""
    return frozenset(
        event_type
        for name in names
        if (event_type := getattr(QEvent.Type, name, None)) is not None
    )


_CANVAS_REPOSITION_EVENT_TYPES = _available_qt_event_types(
    "Resize",
    "Show",
    "Polish",
    "ParentChange",
)


class _ColorButton(QPushButton):
    def __init__(self, value: str, parent=None):
        super().__init__(parent)
        self._value = value
        self.clicked.connect(self._choose)
        self._refresh()

    def _choose(self) -> None:
        color = QColorDialog.getColor(parent=self)
        if color.isValid():
            self._value = color.name()
            self._refresh()

    def _refresh(self) -> None:
        self.setText(self._value)
        light = self._value.lower() in {"#ffffff", "#fffffe", "#f7f7f7"}
        self.setStyleSheet(
            f"background:{self._value}; color:{'#000000' if light else '#ffffff'};"
        )

    def value(self) -> str:
        return self._value

    def set_value(self, value: str) -> None:
        self._value = value
        self._refresh()


def _double(minimum: float, maximum: float, value: float, step: float = 0.1) -> QDoubleSpinBox:
    box = QDoubleSpinBox()
    box.setRange(minimum, maximum)
    box.setSingleStep(step)
    box.setDecimals(3)
    box.setValue(value)
    return box


def _spin(minimum: int, maximum: int, value: int) -> QSpinBox:
    box = QSpinBox()
    box.setRange(minimum, maximum)
    box.setValue(value)
    return box


class ChartStyleDialog(QDialog):
    """A tabbed publication-graphics editor opened only from a chart icon."""

    def __init__(self, style: ChartStyle, figure=None, settings: QSettings | None = None, parent=None):
        super().__init__(parent)
        self.figure = figure
        self.settings = settings or QSettings()
        self._scope = "current"
        self.setWindowTitle("Chart appearance")
        self.resize(700, 650)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)
        heading = QLabel("Chart appearance")
        heading.setObjectName("SectionTitle")
        detail = QLabel(
            "Use a preset or refine typography, legends, series, axes, colours, layout, and export appearance."
        )
        detail.setObjectName("Muted")
        detail.setWordWrap(True)
        root.addWidget(heading)
        root.addWidget(detail)

        preset_row = QHBoxLayout()
        self.preset_combo = QComboBox()
        self.preset_combo.setObjectName("PresetCombo")
        self._refresh_presets()
        load_preset = QPushButton("Apply preset")
        load_preset.clicked.connect(self._load_selected_preset)
        save_preset = QPushButton("Save preset")
        save_preset.clicked.connect(self._save_preset)
        delete_preset = QPushButton("Delete preset")
        delete_preset.clicked.connect(self._delete_preset)
        preset_row.addWidget(QLabel("Preset"))
        preset_row.addWidget(self.preset_combo, 1)
        preset_row.addWidget(load_preset)
        preset_row.addWidget(save_preset)
        preset_row.addWidget(delete_preset)
        root.addLayout(preset_row)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._typography_tab(), "Typography")
        self.tabs.addTab(self._legend_tab(), "Legend")
        self.tabs.addTab(self._series_tab(), "Lines & markers")
        self.tabs.addTab(self._axes_tab(), "Axes & ticks")
        self.tabs.addTab(self._colour_tab(), "Colour & layout")
        self.tabs.addTab(self._export_tab(), "Export")
        root.addWidget(self.tabs, 1)

        actions = QHBoxLayout()
        reset = QPushButton("Reset controls")
        reset.clicked.connect(lambda: self.set_style(ChartStyle()))
        reset_saved = QPushButton("Reset saved styles")
        reset_saved.setToolTip("Remove saved chart, workspace, and application overrides")
        reset_saved.clicked.connect(self._request_reset_all)
        inherit = QPushButton("Use workspace style")
        inherit.setToolTip("Remove this chart's saved override and inherit its workspace or application style")
        inherit.clicked.connect(lambda: self._accept_scope("inherit"))
        actions.addWidget(reset)
        actions.addWidget(reset_saved)
        actions.addWidget(inherit)
        actions.addStretch()
        apply_current = QPushButton("Apply to chart")
        apply_current.setObjectName("PrimaryButton")
        apply_current.clicked.connect(lambda: self._accept_scope("current"))
        apply_workspace = QPushButton("Apply to workspace")
        apply_workspace.clicked.connect(lambda: self._accept_scope("workspace"))
        apply_application = QPushButton("Apply to application")
        apply_application.clicked.connect(lambda: self._accept_scope("application"))
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        for button in (apply_current, apply_workspace, apply_application, cancel):
            actions.addWidget(button)
        root.addLayout(actions)
        self.set_style(style)

    def _tab_host(self, form: QFormLayout) -> QScrollArea:
        host = QWidget()
        host.setLayout(form)
        area = QScrollArea()
        area.setFrameShape(QFrame.Shape.NoFrame)
        area.setWidgetResizable(True)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        area.setWidget(host)
        return area

    def _typography_tab(self) -> QScrollArea:
        form = QFormLayout()
        self.font_family = QFontComboBox()
        self.title_visible = QCheckBox("Show chart title")
        self.title_size = _spin(7, 36, 15)
        self.label_size = _spin(7, 30, 12)
        self.tick_size = _spin(6, 26, 10)
        self.legend_size = _spin(6, 26, 10)
        self.annotation_size = _spin(6, 26, 10)
        self.title_bold = QCheckBox("Bold title")
        self.label_bold = QCheckBox("Bold axis labels")
        self.tick_bold = QCheckBox("Bold tick labels")
        self.legend_bold = QCheckBox("Bold legend")
        self.annotation_bold = QCheckBox("Bold annotations")
        self.title_alignment = QComboBox()
        self.title_alignment.addItems(["left", "center", "right"])
        self.title_pad = _double(0, 40, 8, 0.5)
        self.label_pad = _double(0, 40, 6, 0.5)
        form.addRow("Font family", self.font_family)
        form.addRow(self.title_visible)
        form.addRow("Title size", self.title_size)
        form.addRow("Axis-label size", self.label_size)
        form.addRow("Tick-label size", self.tick_size)
        form.addRow("Legend size", self.legend_size)
        form.addRow("Annotation size", self.annotation_size)
        form.addRow("Title alignment", self.title_alignment)
        form.addRow("Title padding", self.title_pad)
        form.addRow("Label padding", self.label_pad)
        for control in (
            self.title_bold, self.label_bold, self.tick_bold,
            self.legend_bold, self.annotation_bold,
        ):
            form.addRow(control)
        return self._tab_host(form)

    def _legend_tab(self) -> QScrollArea:
        form = QFormLayout()
        self.legend_visible = QCheckBox("Show legend where applicable")
        self.legend_location = QComboBox()
        positions = [
            "best", "upper right", "upper left", "lower left", "lower right",
            "right", "center left", "center right", "lower center", "upper center",
            "center", "outside right", "outside left", "outside top", "outside bottom", "custom",
        ]
        self.legend_location.addItems(positions)
        self.legend_columns = _spin(1, 8, 1)
        self.legend_frame = QCheckBox("Show legend frame")
        self.legend_alpha = _double(0, 1, 0.9, 0.05)
        self.legend_border_width = _double(0, 5, 0.8, 0.1)
        self.legend_anchor_x = _double(-2, 3, 1.02, 0.02)
        self.legend_anchor_y = _double(-2, 3, 1.00, 0.02)
        self.legend_face_color = _ColorButton("#ffffff")
        self.legend_edge_color = _ColorButton("#404040")
        form.addRow(self.legend_visible)
        form.addRow("Position", self.legend_location)
        form.addRow("Columns", self.legend_columns)
        form.addRow(self.legend_frame)
        form.addRow("Frame opacity", self.legend_alpha)
        form.addRow("Border width", self.legend_border_width)
        form.addRow("Custom anchor X", self.legend_anchor_x)
        form.addRow("Custom anchor Y", self.legend_anchor_y)
        form.addRow("Frame colour", self.legend_face_color)
        form.addRow("Border colour", self.legend_edge_color)
        self.legend_location.currentTextChanged.connect(self._update_anchor_controls)
        return self._tab_host(form)

    def _series_tab(self) -> QScrollArea:
        form = QFormLayout()
        self.line_width = _double(0.1, 10, 1.8, 0.1)
        self.line_style = QComboBox()
        for label, value in (("Preserve", "preserve"), ("Solid", "-"), ("Dashed", "--"), ("Dotted", ":"), ("Dash-dot", "-.")):
            self.line_style.addItem(label, value)
        self.marker_style = QComboBox()
        for label, value in (("Preserve", "preserve"), ("None", "none"), ("Circle", "o"), ("Square", "s"), ("Triangle", "^"), ("Diamond", "D"), ("Plus", "+"), ("Cross", "x")):
            self.marker_style.addItem(label, value)
        self.marker_size = _double(0.5, 30, 6, 0.5)
        self.marker_edge = _double(0, 8, 0.8, 0.1)
        self.series_alpha = _double(0.05, 1, 0.9, 0.05)
        self.series_palette = QComboBox()
        self.series_palette.addItems(["Preserve", "Colour blind", "Classic", "Pastel", "High contrast", "Monochrome"])
        self.override_series_color = QCheckBox("Use one series colour")
        self.series_color = _ColorButton("#1f77b4")
        form.addRow("Line width", self.line_width)
        form.addRow("Line style", self.line_style)
        form.addRow("Marker", self.marker_style)
        form.addRow("Marker size", self.marker_size)
        form.addRow("Marker-edge width", self.marker_edge)
        form.addRow("Series opacity", self.series_alpha)
        form.addRow("Series palette", self.series_palette)
        form.addRow(self.override_series_color)
        form.addRow("Override colour", self.series_color)
        return self._tab_host(form)

    def _axes_tab(self) -> QScrollArea:
        form = QFormLayout()
        self.spine_width = _double(0, 6, 1, 0.1)
        self.tick_width = _double(0.1, 6, 1, 0.1)
        self.tick_length = _double(0, 20, 4, 0.5)
        self.tick_direction = QComboBox()
        for label, value in (("Out", "out"), ("In", "in"), ("In and out", "inout")):
            self.tick_direction.addItem(label, value)
        self.x_rotation = _spin(-180, 180, 0)
        self.y_rotation = _spin(-180, 180, 0)
        self.minor_ticks = QCheckBox("Show minor ticks")
        self.axes_margin_x = _double(0, 1, 0.05, 0.01)
        self.axes_margin_y = _double(0, 1, 0.05, 0.01)
        self.major_grid = QCheckBox("Show major grid")
        self.minor_grid = QCheckBox("Show minor grid")
        self.grid_style = QComboBox()
        for label, value in (("Solid", "-"), ("Dashed", "--"), ("Dotted", ":"), ("Dash-dot", "-.")):
            self.grid_style.addItem(label, value)
        self.grid_width = _double(0.1, 6, 0.6, 0.1)
        self.grid_alpha = _double(0, 1, 0.25, 0.05)
        form.addRow("Axis-spine width", self.spine_width)
        form.addRow("Tick width", self.tick_width)
        form.addRow("Tick length", self.tick_length)
        form.addRow("Tick direction", self.tick_direction)
        form.addRow("Horizontal tick rotation", self.x_rotation)
        form.addRow("Vertical tick rotation", self.y_rotation)
        form.addRow(self.minor_ticks)
        form.addRow("Horizontal margin", self.axes_margin_x)
        form.addRow("Vertical margin", self.axes_margin_y)
        form.addRow(self.major_grid)
        form.addRow(self.minor_grid)
        form.addRow("Grid style", self.grid_style)
        form.addRow("Grid width", self.grid_width)
        form.addRow("Grid opacity", self.grid_alpha)
        return self._tab_host(form)

    def _colour_tab(self) -> QScrollArea:
        form = QFormLayout()
        self.figure_background = _ColorButton("#ffffff")
        self.axes_background = _ColorButton("#ffffff")
        self.text_color = _ColorButton("#111111")
        self.axis_color = _ColorButton("#202020")
        self.grid_color = _ColorButton("#8a8a8a")
        self.colormap = QComboBox()
        self.colormap.addItems([
            "Preserve", "viridis", "plasma", "inferno", "magma", "cividis", "turbo",
            "coolwarm", "RdYlGn_r", "Greys", "Blues", "Spectral",
        ])
        self.colorbar_visible = QCheckBox("Show colour bar where applicable")
        self.layout_padding = _double(0, 0.5, 0.04, 0.01)
        form.addRow("Figure background", self.figure_background)
        form.addRow("Plot background", self.axes_background)
        form.addRow("Text colour", self.text_color)
        form.addRow("Axis and tick colour", self.axis_color)
        form.addRow("Grid colour", self.grid_color)
        form.addRow("Colour map", self.colormap)
        form.addRow(self.colorbar_visible)
        form.addRow("Layout padding", self.layout_padding)
        return self._tab_host(form)

    def _export_tab(self) -> QScrollArea:
        form = QFormLayout()
        note = QLabel(
            "Exports use a square 6 × 6 inch canvas. Choose 150, 300, 600, 1200, or 2400 dpi in the export popup."
        )
        note.setObjectName("Muted")
        note.setWordWrap(True)
        preview = QPushButton("Preview export")
        preview.setEnabled(self.figure is not None)
        preview.clicked.connect(self._preview_export)
        form.addRow(note)
        form.addRow("Preview", preview)
        return self._tab_host(form)

    def _request_reset_all(self) -> None:
        answer = QMessageBox.question(
            self, "Reset saved chart styles",
            "Remove saved chart, workspace, and application style overrides? Custom presets will be retained.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._accept_scope("reset_all")

    def _preview_export(self) -> None:
        if self.figure is None:
            return
        apply_chart_style(self.figure, self.style(), redraw=True)
        ExportPreviewDialog(self.figure, self, suggested_name="GPC_DTwin_Figure.png").exec()

    def _custom_presets(self) -> dict[str, dict]:
        raw = str(self.settings.value(CUSTOM_PRESETS_KEY, ""))
        try:
            parsed = json.loads(raw) if raw else {}
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _refresh_presets(self, selected: str | None = None) -> None:
        current = selected or (self.preset_combo.currentText() if hasattr(self, "preset_combo") else "")
        if hasattr(self, "preset_combo"):
            self.preset_combo.clear()
        else:
            return
        self.preset_combo.addItems(list(BUILT_IN_PRESETS))
        custom = self._custom_presets()
        for name in sorted(custom):
            self.preset_combo.addItem(f"Custom · {name}", name)
        index = self.preset_combo.findText(current)
        self.preset_combo.setCurrentIndex(max(index, 0))

    def _load_selected_preset(self) -> None:
        text = self.preset_combo.currentText()
        data = self.preset_combo.currentData()
        if text in BUILT_IN_PRESETS:
            self.set_style(preset_style(text))
            return
        custom = self._custom_presets().get(str(data or ""))
        if isinstance(custom, dict):
            self.set_style(ChartStyle.from_dict(custom))

    def _save_preset(self) -> None:
        name, accepted = QInputDialog.getText(self, "Save chart preset", "Preset name")
        name = name.strip()
        if not accepted or not name:
            return
        custom = self._custom_presets()
        custom[name] = self.style().to_dict()
        self.settings.setValue(CUSTOM_PRESETS_KEY, json.dumps(custom, sort_keys=True))
        self.settings.sync()
        self._refresh_presets(f"Custom · {name}")

    def _delete_preset(self) -> None:
        name = self.preset_combo.currentData()
        if not name:
            QMessageBox.information(self, "Preset", "Built-in presets cannot be deleted.")
            return
        custom = self._custom_presets()
        if str(name) in custom:
            del custom[str(name)]
            self.settings.setValue(CUSTOM_PRESETS_KEY, json.dumps(custom, sort_keys=True))
            self.settings.sync()
            self._refresh_presets()

    def _update_anchor_controls(self) -> None:
        enabled = self.legend_location.currentText() == "custom"
        self.legend_anchor_x.setEnabled(enabled)
        self.legend_anchor_y.setEnabled(enabled)

    def _accept_scope(self, scope: str) -> None:
        self._scope = scope
        self.accept()

    def selected_scope(self) -> str:
        return self._scope

    def style(self) -> ChartStyle:
        return ChartStyle(
            font_family=self.font_family.currentFont().family() or "Times New Roman",
            title_size=self.title_size.value(), label_size=self.label_size.value(),
            tick_size=self.tick_size.value(), legend_size=self.legend_size.value(),
            annotation_size=self.annotation_size.value(), title_bold=self.title_bold.isChecked(),
            label_bold=self.label_bold.isChecked(), tick_bold=self.tick_bold.isChecked(),
            legend_bold=self.legend_bold.isChecked(), annotation_bold=self.annotation_bold.isChecked(),
            title_visible=self.title_visible.isChecked(), title_alignment=self.title_alignment.currentText(),
            title_pad=self.title_pad.value(), label_pad=self.label_pad.value(),
            legend_visible=self.legend_visible.isChecked(), legend_location=self.legend_location.currentText(),
            legend_columns=self.legend_columns.value(), legend_frame=self.legend_frame.isChecked(),
            legend_frame_alpha=self.legend_alpha.value(), legend_border_width=self.legend_border_width.value(),
            legend_anchor_x=self.legend_anchor_x.value(), legend_anchor_y=self.legend_anchor_y.value(),
            legend_face_color=self.legend_face_color.value(), legend_edge_color=self.legend_edge_color.value(),
            line_width=self.line_width.value(), line_style=str(self.line_style.currentData()),
            marker_style=str(self.marker_style.currentData()), marker_size=self.marker_size.value(),
            marker_edge_width=self.marker_edge.value(), series_alpha=self.series_alpha.value(),
            series_color=self.series_color.value() if self.override_series_color.isChecked() else "",
            series_palette=self.series_palette.currentText(), spine_width=self.spine_width.value(),
            tick_width=self.tick_width.value(), tick_length=self.tick_length.value(),
            tick_direction=str(self.tick_direction.currentData()), x_tick_rotation=self.x_rotation.value(),
            y_tick_rotation=self.y_rotation.value(), minor_ticks=self.minor_ticks.isChecked(),
            axes_margin_x=self.axes_margin_x.value(), axes_margin_y=self.axes_margin_y.value(),
            major_grid=self.major_grid.isChecked(), minor_grid=self.minor_grid.isChecked(),
            grid_style=str(self.grid_style.currentData()), grid_width=self.grid_width.value(),
            grid_alpha=self.grid_alpha.value(), figure_background=self.figure_background.value(),
            axes_background=self.axes_background.value(), text_color=self.text_color.value(),
            axis_color=self.axis_color.value(), grid_color=self.grid_color.value(),
            colormap=self.colormap.currentText(), colorbar_visible=self.colorbar_visible.isChecked(),
            layout_padding=self.layout_padding.value(),
        )

    def set_style(self, style: ChartStyle) -> None:
        self.font_family.setCurrentFont(QFont(style.font_family))
        for widget, value in (
            (self.title_size, style.title_size), (self.label_size, style.label_size),
            (self.tick_size, style.tick_size), (self.legend_size, style.legend_size),
            (self.annotation_size, style.annotation_size), (self.title_pad, style.title_pad),
            (self.label_pad, style.label_pad), (self.legend_columns, style.legend_columns),
            (self.legend_alpha, style.legend_frame_alpha), (self.legend_border_width, style.legend_border_width),
            (self.legend_anchor_x, style.legend_anchor_x), (self.legend_anchor_y, style.legend_anchor_y),
            (self.line_width, style.line_width), (self.marker_size, style.marker_size),
            (self.marker_edge, style.marker_edge_width), (self.series_alpha, style.series_alpha),
            (self.spine_width, style.spine_width), (self.tick_width, style.tick_width),
            (self.tick_length, style.tick_length), (self.x_rotation, style.x_tick_rotation),
            (self.y_rotation, style.y_tick_rotation), (self.axes_margin_x, style.axes_margin_x),
            (self.axes_margin_y, style.axes_margin_y), (self.grid_width, style.grid_width),
            (self.grid_alpha, style.grid_alpha), (self.layout_padding, style.layout_padding),
        ):
            widget.setValue(value)
        for widget, value in (
            (self.title_visible, style.title_visible), (self.title_bold, style.title_bold),
            (self.label_bold, style.label_bold), (self.tick_bold, style.tick_bold),
            (self.legend_bold, style.legend_bold), (self.annotation_bold, style.annotation_bold),
            (self.legend_visible, style.legend_visible), (self.legend_frame, style.legend_frame),
            (self.override_series_color, bool(style.series_color)), (self.minor_ticks, style.minor_ticks),
            (self.major_grid, style.major_grid), (self.minor_grid, style.minor_grid),
            (self.colorbar_visible, style.colorbar_visible),
        ):
            widget.setChecked(value)
        for combo, value, by_data in (
            (self.title_alignment, style.title_alignment, False),
            (self.legend_location, style.legend_location, False),
            (self.line_style, style.line_style, True),
            (self.marker_style, style.marker_style, True),
            (self.series_palette, style.series_palette, False),
            (self.tick_direction, style.tick_direction, True),
            (self.grid_style, style.grid_style, True),
            (self.colormap, style.colormap, False),
        ):
            index = combo.findData(value) if by_data else combo.findText(value)
            combo.setCurrentIndex(max(index, 0))
        self.series_color.set_value(style.series_color or "#1f77b4")
        self.legend_face_color.set_value(style.legend_face_color)
        self.legend_edge_color.set_value(style.legend_edge_color)
        self.figure_background.set_value(style.figure_background)
        self.axes_background.set_value(style.axes_background)
        self.text_color.set_value(style.text_color)
        self.axis_color.set_value(style.axis_color)
        self.grid_color.set_value(style.grid_color)
        self._update_anchor_controls()


class ChartStyleOverlayManager(QObject):
    """Attach one palette icon and persist chart, workspace, and application styles.

    New chart canvases are found by a lightweight timer rather than an application-wide
    native event filter. This avoids callbacks into deleted Qt/Matplotlib widgets during
    shutdown and materially reduces the risk of Windows access-violation exits.
    """

    def __init__(self, roots: Iterable[QWidget], settings: QSettings, parent=None):
        super().__init__(parent)
        self.roots = list(roots)
        self.settings = settings
        self._shutting_down = False
        raw = str(settings.value(APPLICATION_STYLE_KEY, settings.value(STYLE_SETTINGS_KEY, "")))
        self.default_style = ChartStyle.from_json(raw)
        self.scan_timer = QTimer(self)
        self.scan_timer.setInterval(400)
        self.scan_timer.timeout.connect(self._scan_canvases)
        self.scan_timer.start()
        self._scan_canvases()

    def _belongs_to_managed_root(self, obj: QObject) -> bool:
        current: QObject | None = obj
        while current is not None:
            if current in self.roots:
                return True
            current = current.parent()
        return False

    def _scan_canvases(self) -> None:
        if self._shutting_down:
            return
        for root in tuple(self.roots):
            if root is None:
                continue
            try:
                canvases = root.findChildren(FigureCanvasQTAgg)
            except RuntimeError:
                # The Python wrapper may outlive the native Qt object briefly.
                continue
            for canvas in canvases:
                if getattr(canvas, "_gpc_style_button", None) is None:
                    self._attach(canvas)
                else:
                    self._position_button(canvas)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if self._shutting_down:
            return False
        if isinstance(watched, FigureCanvasQTAgg):
            if event.type() in _CANVAS_REPOSITION_EVENT_TYPES:
                try:
                    self._position_button(watched)
                except RuntimeError:
                    # Ignore events delivered while the native canvas is closing.
                    return False
        return False

    def _page_root(self, canvas: FigureCanvasQTAgg) -> QWidget | None:
        current: QObject | None = canvas
        while current is not None:
            if current in self.roots:
                return current if isinstance(current, QWidget) else None
            current = current.parent()
        return None

    @staticmethod
    def _workspace_id(root: QWidget | None) -> str:
        return root.__class__.__name__ if root is not None else "Workspace"

    def _chart_id(self, canvas: FigureCanvasQTAgg) -> str:
        existing = str(canvas.property("gpcChartKey") or "").strip()
        if existing:
            return re.sub(r"[^A-Za-z0-9_.-]+", "_", existing)
        if canvas.objectName():
            return re.sub(r"[^A-Za-z0-9_.-]+", "_", canvas.objectName())
        title = next((axis.get_title() for axis in canvas.figure.axes if axis.get_title()), "")
        if title:
            return re.sub(r"[^A-Za-z0-9_.-]+", "_", title.strip().lower())[:80]
        root = self._page_root(canvas)
        canvases = root.findChildren(FigureCanvasQTAgg) if root is not None else [canvas]
        try:
            index = canvases.index(canvas)
        except ValueError:
            index = 0
        return f"chart_{index + 1}"

    def _workspace_key(self, root: QWidget | None) -> str:
        return f"{WORKSPACE_STYLE_PREFIX}{self._workspace_id(root)}"

    def _chart_key(self, canvas: FigureCanvasQTAgg) -> str:
        root = self._page_root(canvas)
        return f"{CHART_STYLE_PREFIX}{self._workspace_id(root)}/{self._chart_id(canvas)}"

    def _effective_style(self, canvas: FigureCanvasQTAgg) -> ChartStyle:
        chart_key = self._chart_key(canvas)
        if self.settings.contains(chart_key):
            return ChartStyle.from_json(str(self.settings.value(chart_key, "")))
        workspace_key = self._workspace_key(self._page_root(canvas))
        if self.settings.contains(workspace_key):
            return ChartStyle.from_json(str(self.settings.value(workspace_key, "")))
        return self.default_style

    def _attach(self, canvas: FigureCanvasQTAgg) -> None:
        if self._shutting_down or getattr(canvas, "_gpc_style_button", None) is not None:
            return
        apply_chart_style(canvas.figure, self._effective_style(canvas))
        button = QToolButton(canvas)
        button.setObjectName("ChartStyleButton")
        button.setText("🎨")
        button.setToolTip("Chart appearance")
        button.setFixedSize(30, 30)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(lambda checked=False, target=canvas: self._open(target))
        setattr(canvas, "_gpc_style_button", button)
        canvas.installEventFilter(self)
        self._position_button(canvas)
        button.show()
        button.raise_()
        canvas.draw_idle()

    @staticmethod
    def _position_button(canvas: FigureCanvasQTAgg) -> None:
        try:
            button = getattr(canvas, "_gpc_style_button", None)
            if button is None:
                return
            margin = 8
            button.move(max(canvas.width() - button.width() - margin, margin), margin)
            button.raise_()
        except RuntimeError:
            # A deleted Qt wrapper must never propagate into the event loop.
            return

    def _all_canvases(self) -> list[FigureCanvasQTAgg]:
        if self._shutting_down:
            return []
        return [target for root in self.roots for target in root.findChildren(FigureCanvasQTAgg)]

    def _open(self, canvas: FigureCanvasQTAgg) -> None:
        if self._shutting_down or not self._belongs_to_managed_root(canvas):
            return
        dialog = ChartStyleDialog(
            style_for_figure(canvas.figure), canvas.figure, self.settings, canvas.window()
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        scope = dialog.selected_scope()
        root = self._page_root(canvas)
        if scope == "reset_all":
            for key in list(self.settings.allKeys()):
                if key == STYLE_SETTINGS_KEY or key == APPLICATION_STYLE_KEY or key.startswith(WORKSPACE_STYLE_PREFIX) or key.startswith(CHART_STYLE_PREFIX):
                    self.settings.remove(key)
            self.default_style = ChartStyle()
            style = self.default_style
            targets = self._all_canvases()
        elif scope == "inherit":
            self.settings.remove(self._chart_key(canvas))
            style = self._effective_style(canvas)
            targets = [canvas]
        else:
            style = dialog.style()
            if scope == "current":
                self.settings.setValue(self._chart_key(canvas), style.to_json())
                targets = [canvas]
            elif scope == "workspace":
                self.settings.setValue(self._workspace_key(root), style.to_json())
                targets = list(root.findChildren(FigureCanvasQTAgg)) if root is not None else [canvas]
            else:
                self.default_style = style
                self.settings.setValue(APPLICATION_STYLE_KEY, style.to_json())
                self.settings.setValue(STYLE_SETTINGS_KEY, style.to_json())
                targets = self._all_canvases()
        self.settings.sync()
        for target in targets:
            if self._belongs_to_managed_root(target):
                apply_chart_style(target.figure, style, redraw=True)

    def shutdown(self) -> None:
        """Stop canvas discovery and detach filters before native Qt teardown."""
        if self._shutting_down:
            return
        self._shutting_down = True
        self.scan_timer.stop()
        for canvas in self._all_canvases_for_shutdown():
            try:
                canvas.removeEventFilter(self)
                button = getattr(canvas, "_gpc_style_button", None)
                if button is not None:
                    button.hide()
                setattr(canvas, "_gpc_style_button", None)
            except RuntimeError:
                pass
        self.roots.clear()

    def _all_canvases_for_shutdown(self) -> list[FigureCanvasQTAgg]:
        canvases: list[FigureCanvasQTAgg] = []
        for root in tuple(self.roots):
            try:
                canvases.extend(root.findChildren(FigureCanvasQTAgg))
            except RuntimeError:
                continue
        return canvases
