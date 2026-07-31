from __future__ import annotations

from pathlib import Path

import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter, QStyle,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from gpc_dtwin.columns import COLUMN_LABELS, MODEL_RESPONSE_COLUMNS
from gpc_dtwin.ui.export_preview_dialog import (
    QualityNavigationToolbar, open_figure_export_dialog,
)
from gpc_dtwin.paths import EXPORT_DIR
from gpc_dtwin.services.data_service import DataService
from gpc_dtwin.services.digital_twin_service import DigitalTwinService
from gpc_dtwin.services.visualization_3d_service import (
    CAMERA_PRESETS,
    SpecimenFieldResult,
    Surface3DResult,
    Visualization3DService,
)
from gpc_dtwin.ui.scrolling import scrollable_panel
from gpc_dtwin.ui.widgets import CompactToolbar, SectionHeader, ValuePill


class Visualization3DPage(QWidget):
    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.context = context
        self.service = Visualization3DService()
        self.surface_result: Surface3DResult | None = None
        self.specimen_result: SpecimenFieldResult | None = None
        self.surface_figure = self._placeholder_figure(
            "Build a response surface to open the interactive 3D view."
        )
        self.specimen_figure = self._placeholder_figure(
            "Select a mix and property to create an estimated specimen field."
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 24)
        root.setSpacing(14)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._surface_tab(), "Response surface")
        self.tabs.addTab(self._specimen_tab(), "Specimen field")
        root.addWidget(self.tabs, 1)

        self.context.data_changed.connect(self.refresh)
        self.refresh()

    @staticmethod
    def _placeholder_figure(message: str) -> Figure:
        figure = Figure(figsize=(8, 5), constrained_layout=True)
        axis = figure.add_subplot(111)
        axis.set_axis_off()
        axis.text(
            0.5,
            0.5,
            message,
            ha="center",
            va="center",
            fontsize=13,
            alpha=0.72,
            wrap=True,
        )
        return figure

    def _surface_tab(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        controls = QFrame()
        controls.setObjectName("Card")
        controls.setMinimumWidth(330)
        controls.setMaximumWidth(405)
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(18, 18, 18, 18)
        controls_layout.setSpacing(12)
        controls_layout.addWidget(
            SectionHeader(
                "Surface controls",
                "Select the response, two numeric axes, and uncertainty method.",
            )
        )

        form = QFormLayout()
        self.surface_response_combo = QComboBox()
        self.surface_response_combo.currentIndexChanged.connect(self._refresh_surface_axes)
        self.surface_x_combo = QComboBox()
        self.surface_y_combo = QComboBox()
        self.surface_method_combo = QComboBox()
        self.surface_method_combo.addItems(DigitalTwinService.method_names())
        self.surface_confidence_combo = QComboBox()
        for value in (90.0, 95.0, 99.0):
            self.surface_confidence_combo.addItem(f"{value:.0f}%", value)
        self.surface_confidence_combo.setCurrentIndex(1)
        self.surface_mode_combo = QComboBox()
        self.surface_mode_combo.addItems(self.service.surface_modes())
        self.surface_resolution_spin = QSpinBox()
        self.surface_resolution_spin.setRange(15, 80)
        self.surface_resolution_spin.setValue(35)
        self.surface_resolution_spin.setSuffix(" × ")
        form.addRow("Response", self.surface_response_combo)
        form.addRow("X axis", self.surface_x_combo)
        form.addRow("Y axis", self.surface_y_combo)
        form.addRow("Method", self.surface_method_combo)
        form.addRow("Confidence", self.surface_confidence_combo)
        form.addRow("Surface", self.surface_mode_combo)
        form.addRow("Grid", self.surface_resolution_spin)
        controls_layout.addLayout(form)

        self.surface_overlay_check = QCheckBox("Overlay available observations")
        self.surface_overlay_check.setChecked(True)
        self.surface_wireframe_check = QCheckBox("Show surface mesh")
        self.surface_projection_check = QCheckBox("Show base projection")
        self.surface_projection_check.setChecked(True)
        self.surface_review_check = QCheckBox("Include records marked for review")
        controls_layout.addWidget(self.surface_overlay_check)
        controls_layout.addWidget(self.surface_wireframe_check)
        controls_layout.addWidget(self.surface_projection_check)
        controls_layout.addWidget(self.surface_review_check)

        build_button = QPushButton("Build 3D surface")
        build_button.setObjectName("PrimaryButton")
        build_button.clicked.connect(self.build_surface)
        controls_layout.addWidget(build_button)
        controls_layout.addSpacing(4)
        controls_layout.addWidget(SectionHeader("Camera", "Apply a preset or enter view angles."))

        camera_form = QFormLayout()
        self.surface_camera_combo = QComboBox()
        self.surface_camera_combo.addItems(CAMERA_PRESETS.keys())
        self.surface_elevation_spin = QDoubleSpinBox()
        self.surface_elevation_spin.setRange(-90.0, 90.0)
        self.surface_elevation_spin.setDecimals(1)
        self.surface_azimuth_spin = QDoubleSpinBox()
        self.surface_azimuth_spin.setRange(-180.0, 180.0)
        self.surface_azimuth_spin.setDecimals(1)
        self._set_camera_values(
            self.surface_camera_combo,
            self.surface_elevation_spin,
            self.surface_azimuth_spin,
        )
        self.surface_camera_combo.currentTextChanged.connect(
            lambda _text: self._set_camera_values(
                self.surface_camera_combo,
                self.surface_elevation_spin,
                self.surface_azimuth_spin,
            )
        )
        camera_form.addRow("Preset", self.surface_camera_combo)
        camera_form.addRow("Elevation", self.surface_elevation_spin)
        camera_form.addRow("Azimuth", self.surface_azimuth_spin)
        controls_layout.addLayout(camera_form)
        apply_camera = QPushButton("Apply view")
        apply_camera.clicked.connect(self.render_surface)
        controls_layout.addWidget(apply_camera)
        controls_layout.addStretch()
        controls_scroll = scrollable_panel(controls, minimum_width=350)
        controls_scroll.setMaximumWidth(445)
        splitter.addWidget(controls_scroll)

        view = QWidget()
        view_layout = QVBoxLayout(view)
        view_layout.setContentsMargins(0, 0, 0, 0)
        view_layout.setSpacing(10)

        self.surface_min_pill = ValuePill()
        self.surface_max_pill = ValuePill()
        self.surface_uncertainty_pill = ValuePill()
        self.surface_support_pill = ValuePill()
        self.surface_nodes_pill = ValuePill()
        self.surface_r2_pill = ValuePill()
        toolbar = CompactToolbar()
        for label, pill in (
            ("Minimum", self.surface_min_pill),
            ("Maximum", self.surface_max_pill),
            ("Mean uncertainty", self.surface_uncertainty_pill),
            ("A–B region", self.surface_support_pill),
            ("Grid nodes", self.surface_nodes_pill),
            ("CV R²", self.surface_r2_pill),
        ):
            toolbar.add_metric(label, pill)
        toolbar.add_stretch()
        toolbar.add_action(
            QStyle.StandardPixmap.SP_DialogSaveButton,
            "Export response grid",
            self.export_surface_grid,
        )
        toolbar.add_action(
            QStyle.StandardPixmap.SP_FileDialogDetailedView,
            "Export 3D surface figure",
            self.export_surface_figure,
        )
        toolbar.finalize()
        view_layout.addWidget(toolbar)

        self.surface_detail_label = QLabel("No surface is active.")
        self.surface_detail_label.setObjectName("Muted")
        self.surface_detail_label.setWordWrap(True)
        view_layout.addWidget(self.surface_detail_label)

        self.surface_card = QFrame()
        self.surface_card.setObjectName("Card")
        self.surface_chart_layout = QVBoxLayout(self.surface_card)
        self.surface_chart_layout.setContentsMargins(10, 10, 10, 10)
        self.surface_canvas = FigureCanvasQTAgg(self.surface_figure)
        self.surface_toolbar = QualityNavigationToolbar(self.surface_canvas, self.surface_card)
        self.surface_chart_layout.addWidget(self.surface_toolbar)
        self.surface_chart_layout.addWidget(self.surface_canvas, 1)
        view_layout.addWidget(self.surface_card, 1)

        splitter.addWidget(view)
        splitter.setSizes([360, 1080])
        layout.addWidget(splitter)
        return page

    def _specimen_tab(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        controls = QFrame()
        controls.setObjectName("Card")
        controls.setMinimumWidth(330)
        controls.setMaximumWidth(405)
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(18, 18, 18, 18)
        controls_layout.setSpacing(12)
        controls_layout.addWidget(
            SectionHeader(
                "Specimen controls",
                "Create a normalized material-state field inside a 150 mm cube.",
            )
        )

        form = QFormLayout()
        self.specimen_mix_combo = QComboBox()
        self.specimen_property_combo = QComboBox()
        for field in self.service.specimen_properties():
            self.specimen_property_combo.addItem(COLUMN_LABELS.get(field, field), field)
        self.specimen_resolution_spin = QSpinBox()
        self.specimen_resolution_spin.setRange(7, 18)
        self.specimen_resolution_spin.setValue(11)
        self.specimen_resolution_spin.setSuffix(" nodes/axis")
        self.specimen_cutaway_combo = QComboBox()
        self.specimen_cutaway_combo.addItems(self.service.cutaway_modes())
        self.specimen_cutaway_combo.setCurrentText("Octant cutaway")
        self.specimen_colormap_combo = QComboBox()
        self.specimen_colormap_combo.addItems(
            ["plasma", "viridis", "magma", "inferno", "cividis", "turbo"]
        )
        form.addRow("Mix", self.specimen_mix_combo)
        form.addRow("Property", self.specimen_property_combo)
        form.addRow("Resolution", self.specimen_resolution_spin)
        form.addRow("View", self.specimen_cutaway_combo)
        form.addRow("Colour scale", self.specimen_colormap_combo)
        controls_layout.addLayout(form)

        generate_button = QPushButton("Create specimen field")
        generate_button.setObjectName("PrimaryButton")
        generate_button.clicked.connect(self.generate_specimen_field)
        controls_layout.addWidget(generate_button)
        controls_layout.addSpacing(4)
        controls_layout.addWidget(SectionHeader("Camera", "Apply a preset or enter view angles."))

        camera_form = QFormLayout()
        self.specimen_camera_combo = QComboBox()
        self.specimen_camera_combo.addItems(CAMERA_PRESETS.keys())
        self.specimen_elevation_spin = QDoubleSpinBox()
        self.specimen_elevation_spin.setRange(-90.0, 90.0)
        self.specimen_elevation_spin.setDecimals(1)
        self.specimen_azimuth_spin = QDoubleSpinBox()
        self.specimen_azimuth_spin.setRange(-180.0, 180.0)
        self.specimen_azimuth_spin.setDecimals(1)
        self._set_camera_values(
            self.specimen_camera_combo,
            self.specimen_elevation_spin,
            self.specimen_azimuth_spin,
        )
        self.specimen_camera_combo.currentTextChanged.connect(
            lambda _text: self._set_camera_values(
                self.specimen_camera_combo,
                self.specimen_elevation_spin,
                self.specimen_azimuth_spin,
            )
        )
        camera_form.addRow("Preset", self.specimen_camera_combo)
        camera_form.addRow("Elevation", self.specimen_elevation_spin)
        camera_form.addRow("Azimuth", self.specimen_azimuth_spin)
        controls_layout.addLayout(camera_form)
        apply_camera = QPushButton("Apply view")
        apply_camera.clicked.connect(self.render_specimen)
        controls_layout.addWidget(apply_camera)
        controls_layout.addStretch()
        controls_scroll = scrollable_panel(controls, minimum_width=350)
        controls_scroll.setMaximumWidth(445)
        splitter.addWidget(controls_scroll)

        view = QWidget()
        view_layout = QVBoxLayout(view)
        view_layout.setContentsMargins(0, 0, 0, 0)
        view_layout.setSpacing(10)

        note = QFrame()
        note.setObjectName("InfoCard")
        note_layout = QHBoxLayout(note)
        note_layout.setContentsMargins(14, 11, 14, 11)
        note_label = QLabel(
            "The specimen field is an estimated visual representation derived from aggregate "
            "property values. It is not a spatial scan or internal tomography result."
        )
        note_label.setObjectName("Muted")
        note_label.setWordWrap(True)
        note_layout.addWidget(note_label)
        view_layout.addWidget(note)

        self.specimen_base_pill = ValuePill()
        self.specimen_mean_pill = ValuePill()
        self.specimen_range_pill = ValuePill()
        self.specimen_cv_pill = ValuePill()
        self.specimen_uniformity_pill = ValuePill()
        self.specimen_records_pill = ValuePill()
        toolbar = CompactToolbar()
        for label, pill in (
            ("Aggregate value", self.specimen_base_pill),
            ("Field mean", self.specimen_mean_pill),
            ("Field range", self.specimen_range_pill),
            ("Field CV", self.specimen_cv_pill),
            ("Uniformity", self.specimen_uniformity_pill),
            ("Source records", self.specimen_records_pill),
        ):
            toolbar.add_metric(label, pill)
        toolbar.add_stretch()
        toolbar.add_action(
            QStyle.StandardPixmap.SP_DialogSaveButton,
            "Export specimen field data",
            self.export_specimen_field,
        )
        toolbar.add_action(
            QStyle.StandardPixmap.SP_FileDialogDetailedView,
            "Export specimen-field figure",
            self.export_specimen_figure,
        )
        toolbar.finalize()
        view_layout.addWidget(toolbar)

        self.specimen_detail_label = QLabel("No specimen field is active.")
        self.specimen_detail_label.setObjectName("Muted")
        self.specimen_detail_label.setWordWrap(True)
        view_layout.addWidget(self.specimen_detail_label)

        self.specimen_card = QFrame()
        self.specimen_card.setObjectName("Card")
        self.specimen_chart_layout = QVBoxLayout(self.specimen_card)
        self.specimen_chart_layout.setContentsMargins(10, 10, 10, 10)
        self.specimen_canvas = FigureCanvasQTAgg(self.specimen_figure)
        self.specimen_toolbar = QualityNavigationToolbar(self.specimen_canvas, self.specimen_card)
        self.specimen_chart_layout.addWidget(self.specimen_toolbar)
        self.specimen_chart_layout.addWidget(self.specimen_canvas, 1)
        view_layout.addWidget(self.specimen_card, 1)

        splitter.addWidget(view)
        splitter.setSizes([360, 1080])
        layout.addWidget(splitter)
        return page

    def refresh(self) -> None:
        dataframe = self.context.dataframe
        current_response = self.surface_response_combo.currentData()
        self.surface_response_combo.blockSignals(True)
        self.surface_response_combo.clear()
        for field in MODEL_RESPONSE_COLUMNS:
            if field in dataframe.columns and pd.to_numeric(
                dataframe[field], errors="coerce"
            ).notna().sum() >= 8:
                self.surface_response_combo.addItem(COLUMN_LABELS.get(field, field), field)
        index = self.surface_response_combo.findData(current_response)
        if index >= 0:
            self.surface_response_combo.setCurrentIndex(index)
        elif self.surface_response_combo.findData("compressive_strength_mpa") >= 0:
            self.surface_response_combo.setCurrentIndex(
                self.surface_response_combo.findData("compressive_strength_mpa")
            )
        self.surface_response_combo.blockSignals(False)
        self._refresh_surface_axes()

        current_mix = self.specimen_mix_combo.currentText()
        self.specimen_mix_combo.blockSignals(True)
        self.specimen_mix_combo.clear()
        self.specimen_mix_combo.addItems(DataService.unique_values(dataframe, "mix_id"))
        mix_index = self.specimen_mix_combo.findText(current_mix)
        self.specimen_mix_combo.setCurrentIndex(mix_index if mix_index >= 0 else 0)
        self.specimen_mix_combo.blockSignals(False)

    def _refresh_surface_axes(self, *_args) -> None:
        response = self.surface_response_combo.currentData()
        if not response:
            return
        axes = self.service.available_numeric_axes(self.context.dataframe, response)
        old_x = self.surface_x_combo.currentData()
        old_y = self.surface_y_combo.currentData()
        for combo in (self.surface_x_combo, self.surface_y_combo):
            combo.blockSignals(True)
            combo.clear()
            for field in axes:
                combo.addItem(COLUMN_LABELS.get(field, field), field)
            combo.blockSignals(False)
        self._select_combo_data(
            self.surface_x_combo,
            old_x if old_x in axes else "ggbs_percent_numeric",
        )
        preferred_y = old_y if old_y in axes and old_y != self.surface_x_combo.currentData() else "aas_b_ratio"
        self._select_combo_data(self.surface_y_combo, preferred_y)
        if self.surface_x_combo.currentData() == self.surface_y_combo.currentData() and self.surface_y_combo.count() > 1:
            self.surface_y_combo.setCurrentIndex(1)

    @staticmethod
    def _select_combo_data(combo: QComboBox, value: object) -> None:
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else (0 if combo.count() else -1))

    @staticmethod
    def _set_camera_values(
        combo: QComboBox,
        elevation_spin: QDoubleSpinBox,
        azimuth_spin: QDoubleSpinBox,
    ) -> None:
        elevation, azimuth = CAMERA_PRESETS.get(combo.currentText(), CAMERA_PRESETS["Isometric"])
        elevation_spin.setValue(elevation)
        azimuth_spin.setValue(azimuth)

    def build_surface(self) -> None:
        response = self.surface_response_combo.currentData()
        x_field = self.surface_x_combo.currentData()
        y_field = self.surface_y_combo.currentData()
        if not all((response, x_field, y_field)):
            QMessageBox.warning(self, "Surface unavailable", "Select a response and two axes.")
            return
        self.setCursor(Qt.CursorShape.WaitCursor)
        try:
            self.surface_result = self.service.build_surface(
                self.context.dataframe,
                response=response,
                x_field=x_field,
                y_field=y_field,
                method=self.surface_method_combo.currentText(),
                confidence_percent=float(self.surface_confidence_combo.currentData()),
                resolution=self.surface_resolution_spin.value(),
                include_review_records=self.surface_review_check.isChecked(),
                mode=self.surface_mode_combo.currentText(),
            )
            self._show_surface_metrics()
            self.render_surface()
            self.context.message.emit("3D response surface created.")
            omitted = self.surface_result.twin_result.omitted_predictors
            if omitted:
                QMessageBox.warning(
                    self,
                    "Parameters excluded",
                    "The 3D response surface was created after automatically excluding "
                    "parameters without usable values for the selected response:\n\n"
                    + "\n".join(
                        f"• {COLUMN_LABELS.get(field, field)}" for field in omitted
                    ),
                )
        except Exception as error:
            QMessageBox.critical(self, "Surface generation failed", str(error))
        finally:
            self.unsetCursor()

    def _show_surface_metrics(self) -> None:
        if self.surface_result is None:
            return
        summary = self.surface_result.summary
        metrics = self.surface_result.twin_result.metrics
        self.surface_min_pill.set_value(f"{summary['minimum_estimate']:.3f}")
        self.surface_max_pill.set_value(f"{summary['maximum_estimate']:.3f}")
        self.surface_uncertainty_pill.set_value(
            f"{summary['mean_uncertainty_percent']:.1f}%",
            "success" if summary["mean_uncertainty_percent"] <= 15 else "warning",
        )
        self.surface_support_pill.set_value(
            f"{summary['supported_area_percent']:.1f}%",
            "success" if summary["supported_area_percent"] >= 70 else "warning",
        )
        self.surface_nodes_pill.set_value(int(summary["map_nodes"]))
        self.surface_r2_pill.set_value(
            f"{metrics['r2']:.3f}",
            "success" if metrics["r2"] >= 0.5 else "warning",
        )
        self.surface_detail_label.setText(
            f"{self.surface_result.twin_result.method} · "
            f"{self.surface_result.twin_result.confidence_percent:.0f}% interval · "
            f"{self.surface_result.twin_result.observations} fitted records · "
            f"{self.surface_result.twin_result.cv_method}."
        )

    def render_surface(self) -> None:
        if self.surface_result is None:
            return
        if self.surface_result.mode != self.surface_mode_combo.currentText():
            self.build_surface()
            return
        try:
            self.surface_figure = self.service.surface_figure(
                self.surface_result,
                show_overlay=self.surface_overlay_check.isChecked(),
                show_wireframe=self.surface_wireframe_check.isChecked(),
                show_projection=self.surface_projection_check.isChecked(),
                elevation=self.surface_elevation_spin.value(),
                azimuth=self.surface_azimuth_spin.value(),
            )
            self.surface_canvas, self.surface_toolbar = self._replace_canvas(
                self.surface_chart_layout,
                self.surface_canvas,
                self.surface_toolbar,
                self.surface_figure,
                self.surface_card,
            )
        except Exception as error:
            QMessageBox.critical(self, "3D view failed", str(error))

    def generate_specimen_field(self) -> None:
        mix_id = self.specimen_mix_combo.currentText()
        property_field = self.specimen_property_combo.currentData()
        if not mix_id or not property_field:
            QMessageBox.warning(self, "Specimen field unavailable", "Select a mix and property.")
            return
        self.setCursor(Qt.CursorShape.WaitCursor)
        try:
            self.specimen_result = self.service.specimen_field(
                self.context.dataframe,
                mix_id=mix_id,
                property_field=property_field,
                resolution=self.specimen_resolution_spin.value(),
            )
            self._show_specimen_metrics()
            self.render_specimen()
            self.context.message.emit("Estimated specimen field created.")
        except Exception as error:
            QMessageBox.critical(self, "Specimen field failed", str(error))
        finally:
            self.unsetCursor()

    def _show_specimen_metrics(self) -> None:
        if self.specimen_result is None:
            return
        summary = self.specimen_result.summary
        self.specimen_base_pill.set_value(f"{self.specimen_result.base_value:.3f}")
        self.specimen_mean_pill.set_value(f"{summary['mean']:.3f}")
        self.specimen_range_pill.set_value(
            f"{summary['minimum']:.3f}–{summary['maximum']:.3f}"
        )
        self.specimen_cv_pill.set_value(f"{summary['coefficient_of_variation_percent']:.2f}%")
        self.specimen_uniformity_pill.set_value(
            f"{self.specimen_result.uniformity_index * 100.0:.1f}%",
            "success" if self.specimen_result.uniformity_index >= 0.65 else "warning",
        )
        self.specimen_records_pill.set_value(self.specimen_result.source_records)
        self.specimen_detail_label.setText(
            f"{self.specimen_result.mix_id} · {self.specimen_result.property_label} · "
            f"{int(summary['field_nodes'])} field nodes."
        )

    def render_specimen(self) -> None:
        if self.specimen_result is None:
            return
        try:
            self.specimen_figure = self.service.specimen_figure(
                self.specimen_result,
                cutaway_mode=self.specimen_cutaway_combo.currentText(),
                elevation=self.specimen_elevation_spin.value(),
                azimuth=self.specimen_azimuth_spin.value(),
                colormap=self.specimen_colormap_combo.currentText(),
            )
            self.specimen_canvas, self.specimen_toolbar = self._replace_canvas(
                self.specimen_chart_layout,
                self.specimen_canvas,
                self.specimen_toolbar,
                self.specimen_figure,
                self.specimen_card,
            )
        except Exception as error:
            QMessageBox.critical(self, "Specimen view failed", str(error))

    @staticmethod
    def _replace_canvas(
        layout: QVBoxLayout,
        old_canvas: FigureCanvasQTAgg,
        old_toolbar: QualityNavigationToolbar,
        figure: Figure,
        parent: QWidget,
    ) -> tuple[FigureCanvasQTAgg, QualityNavigationToolbar]:
        layout.removeWidget(old_toolbar)
        old_toolbar.setParent(None)
        old_toolbar.deleteLater()
        layout.removeWidget(old_canvas)
        old_canvas.setParent(None)
        old_canvas.deleteLater()
        canvas = FigureCanvasQTAgg(figure)
        toolbar = QualityNavigationToolbar(canvas, parent)
        layout.addWidget(toolbar)
        layout.addWidget(canvas, 1)
        canvas.draw_idle()
        return canvas, toolbar

    def export_surface_grid(self) -> None:
        if self.surface_result is None:
            QMessageBox.information(self, "Nothing to export", "Build a response surface first.")
            return
        default = EXPORT_DIR / "GPC_DTwin_3D_Response_Grid.csv"
        path, _ = QFileDialog.getSaveFileName(self, "Export response grid", str(default), "CSV data (*.csv)")
        if not path:
            return
        try:
            destination = self.service.export_dataframe(self.surface_result.surface, path)
            self.context.message.emit(f"Response grid exported to {destination.name}.")
        except Exception as error:
            QMessageBox.critical(self, "Export failed", str(error))

    def export_specimen_field(self) -> None:
        if self.specimen_result is None:
            QMessageBox.information(self, "Nothing to export", "Create a specimen field first.")
            return
        default = EXPORT_DIR / "GPC_DTwin_Specimen_Field.csv"
        path, _ = QFileDialog.getSaveFileName(self, "Export specimen field", str(default), "CSV data (*.csv)")
        if not path:
            return
        try:
            destination = self.service.export_dataframe(self.specimen_result.field, path)
            self.context.message.emit(f"Specimen field exported to {destination.name}.")
        except Exception as error:
            QMessageBox.critical(self, "Export failed", str(error))

    def export_surface_figure(self) -> None:
        self._export_figure(self.surface_figure, "GPC_DTwin_3D_Response_Surface.png")

    def export_specimen_figure(self) -> None:
        self._export_figure(self.specimen_figure, "GPC_DTwin_Specimen_Field.png")

    def _export_figure(self, figure: Figure, filename: str) -> None:
        open_figure_export_dialog(
            self, figure, suggested_name=str(EXPORT_DIR / filename)
        )

