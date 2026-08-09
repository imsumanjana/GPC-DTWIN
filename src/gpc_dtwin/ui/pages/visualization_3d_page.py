from __future__ import annotations

from pathlib import Path

import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QFrame,
    QHBoxLayout, QLabel, QMessageBox, QPushButton, QSpinBox, QSplitter, QStyle,
    QTabWidget, QVBoxLayout, QWidget,
)

from gpc_dtwin.columns import COLUMN_LABELS
from gpc_dtwin.paths import EXPORT_DIR
from gpc_dtwin.services.data_service import DataService
from gpc_dtwin.services.visualization_3d_service import (
    CAMERA_PRESETS, SpecimenFieldResult, Surface3DResult, Visualization3DService,
)
from gpc_dtwin.ui.export_preview_dialog import (
    QualityNavigationToolbar, open_figure_export_dialog,
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
            "Build or load a Digital Twin, then explore its response landscape here."
        )
        self.specimen_figure = self._placeholder_figure(
            "Select a mix and physics analysis to calculate a specimen field."
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 24)
        root.setSpacing(14)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._surface_tab(), "Response surface")
        self.tabs.addTab(self._specimen_tab(), "Physics-informed specimen")
        root.addWidget(self.tabs, 1)

        self.context.data_changed.connect(self.refresh)
        self.context.active_twin_changed.connect(self._refresh_surface_from_twin)
        self.refresh()

    @staticmethod
    def _placeholder_figure(message: str) -> Figure:
        figure = Figure(figsize=(8, 5), constrained_layout=True)
        axis = figure.add_subplot(111)
        axis.set_axis_off()
        axis.text(0.5, 0.5, message, ha="center", va="center", fontsize=13, alpha=0.72, wrap=True)
        return figure

    def _surface_tab(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        controls = QFrame()
        controls.setObjectName("Card")
        controls.setMinimumWidth(330)
        controls.setMaximumWidth(430)
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(18, 18, 18, 18)
        controls_layout.setSpacing(12)
        controls_layout.addWidget(SectionHeader(
            "Active Digital Twin",
            "The 3D response surface visualizes the currently active twin; it does not train another model.",
        ))
        self.surface_twin_label = QLabel("No active Digital Twin")
        self.surface_twin_label.setObjectName("Muted")
        self.surface_twin_label.setWordWrap(True)
        controls_layout.addWidget(self.surface_twin_label)

        form = QFormLayout()
        self.surface_x_combo = QComboBox()
        self.surface_y_combo = QComboBox()
        self.surface_mode_combo = QComboBox()
        self.surface_mode_combo.addItems(self.service.surface_modes())
        self.surface_resolution_spin = QSpinBox()
        self.surface_resolution_spin.setRange(15, 80)
        self.surface_resolution_spin.setValue(35)
        self.surface_resolution_spin.setSuffix(" × ")
        form.addRow("X axis", self.surface_x_combo)
        form.addRow("Y axis", self.surface_y_combo)
        form.addRow("Surface", self.surface_mode_combo)
        form.addRow("Grid", self.surface_resolution_spin)
        controls_layout.addLayout(form)

        self.surface_overlay_check = QCheckBox("Overlay available observations")
        self.surface_overlay_check.setChecked(True)
        self.surface_wireframe_check = QCheckBox("Show surface mesh")
        self.surface_projection_check = QCheckBox("Show base projection")
        self.surface_projection_check.setChecked(True)
        controls_layout.addWidget(self.surface_overlay_check)
        controls_layout.addWidget(self.surface_wireframe_check)
        controls_layout.addWidget(self.surface_projection_check)

        self.surface_build_button = QPushButton("Build 3D surface")
        self.surface_build_button.setObjectName("PrimaryButton")
        self.surface_build_button.clicked.connect(self.build_surface)
        self.surface_build_button.setEnabled(False)
        controls_layout.addWidget(self.surface_build_button)
        controls_layout.addSpacing(4)
        controls_layout.addWidget(SectionHeader("Camera", "Apply a preset or enter view angles."))
        camera_form = QFormLayout()
        self.surface_camera_combo = QComboBox(); self.surface_camera_combo.addItems(CAMERA_PRESETS.keys())
        self.surface_elevation_spin = QDoubleSpinBox(); self.surface_elevation_spin.setRange(-90.0, 90.0); self.surface_elevation_spin.setDecimals(1)
        self.surface_azimuth_spin = QDoubleSpinBox(); self.surface_azimuth_spin.setRange(-180.0, 180.0); self.surface_azimuth_spin.setDecimals(1)
        self._set_camera_values(self.surface_camera_combo, self.surface_elevation_spin, self.surface_azimuth_spin)
        self.surface_camera_combo.currentTextChanged.connect(
            lambda _text: self._set_camera_values(self.surface_camera_combo, self.surface_elevation_spin, self.surface_azimuth_spin)
        )
        camera_form.addRow("Preset", self.surface_camera_combo)
        camera_form.addRow("Elevation", self.surface_elevation_spin)
        camera_form.addRow("Azimuth", self.surface_azimuth_spin)
        controls_layout.addLayout(camera_form)
        apply_camera = QPushButton("Apply view"); apply_camera.clicked.connect(self.render_surface)
        controls_layout.addWidget(apply_camera)
        controls_layout.addStretch()
        controls_scroll = scrollable_panel(controls, minimum_width=350); controls_scroll.setMaximumWidth(470)
        splitter.addWidget(controls_scroll)

        view = QWidget(); view_layout = QVBoxLayout(view); view_layout.setContentsMargins(0, 0, 0, 0); view_layout.setSpacing(10)
        self.surface_min_pill = ValuePill(); self.surface_max_pill = ValuePill(); self.surface_uncertainty_pill = ValuePill()
        self.surface_support_pill = ValuePill(); self.surface_nodes_pill = ValuePill(); self.surface_r2_pill = ValuePill()
        toolbar = CompactToolbar()
        for label, pill in (("Minimum", self.surface_min_pill), ("Maximum", self.surface_max_pill),
                            ("Mean uncertainty", self.surface_uncertainty_pill), ("A–B region", self.surface_support_pill),
                            ("Grid nodes", self.surface_nodes_pill), ("CV R²", self.surface_r2_pill)):
            toolbar.add_metric(label, pill)
        toolbar.add_stretch()
        toolbar.add_action(QStyle.StandardPixmap.SP_DialogSaveButton, "Export response grid", self.export_surface_grid)
        toolbar.add_action(QStyle.StandardPixmap.SP_FileDialogDetailedView, "Export 3D surface figure", self.export_surface_figure)
        toolbar.finalize(); view_layout.addWidget(toolbar)
        self.surface_detail_label = QLabel("No surface is active."); self.surface_detail_label.setObjectName("Muted"); self.surface_detail_label.setWordWrap(True)
        view_layout.addWidget(self.surface_detail_label)
        self.surface_card = QFrame(); self.surface_card.setObjectName("Card")
        self.surface_chart_layout = QVBoxLayout(self.surface_card); self.surface_chart_layout.setContentsMargins(10, 10, 10, 10)
        self.surface_canvas = FigureCanvasQTAgg(self.surface_figure); self.surface_toolbar = QualityNavigationToolbar(self.surface_canvas, self.surface_card)
        self.surface_chart_layout.addWidget(self.surface_toolbar); self.surface_chart_layout.addWidget(self.surface_canvas, 1)
        view_layout.addWidget(self.surface_card, 1)
        splitter.addWidget(view); splitter.setSizes([360, 1080]); layout.addWidget(splitter)
        return page

    def _specimen_tab(self) -> QWidget:
        page = QWidget(); layout = QHBoxLayout(page); layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        controls = QFrame(); controls.setObjectName("Card"); controls.setMinimumWidth(345); controls.setMaximumWidth(455)
        controls_layout = QVBoxLayout(controls); controls_layout.setContentsMargins(18, 18, 18, 18); controls_layout.setSpacing(10)
        controls_layout.addWidget(SectionHeader(
            "Specimen physics",
            "Calculate theory-based fields in the experimental cube, cylinder, or beam. Calculated fields are not presented as measured tomography.",
        ))
        form = QFormLayout()
        self.specimen_mix_combo = QComboBox()
        self.specimen_analysis_combo = QComboBox(); self.specimen_analysis_combo.addItems(self.service.specimen_analyses())
        self.specimen_analysis_combo.currentTextChanged.connect(self._refresh_specimen_fields)
        self.specimen_field_combo = QComboBox()
        self.specimen_resolution_spin = QSpinBox(); self.specimen_resolution_spin.setRange(7, 24); self.specimen_resolution_spin.setValue(13); self.specimen_resolution_spin.setSuffix(" nodes/axis")
        self.specimen_load_ratio_spin = QDoubleSpinBox(); self.specimen_load_ratio_spin.setRange(0.0, 150.0); self.specimen_load_ratio_spin.setValue(75.0); self.specimen_load_ratio_spin.setSuffix(" %")
        self.specimen_acid_combo = QComboBox(); self.specimen_acid_combo.addItems(["H2SO4", "HCl"])
        self.specimen_exposure_spin = QDoubleSpinBox(); self.specimen_exposure_spin.setRange(0.1, 3650.0); self.specimen_exposure_spin.setValue(28.0); self.specimen_exposure_spin.setSuffix(" days")
        self.specimen_diffusivity_spin = QDoubleSpinBox(); self.specimen_diffusivity_spin.setRange(0.001, 1000.0); self.specimen_diffusivity_spin.setDecimals(3); self.specimen_diffusivity_spin.setValue(1.0); self.specimen_diffusivity_spin.setSuffix(" mm²/day")
        self.specimen_cutaway_combo = QComboBox(); self.specimen_cutaway_combo.addItems(self.service.cutaway_modes()); self.specimen_cutaway_combo.setCurrentText("Octant cutaway")
        self.specimen_colormap_combo = QComboBox(); self.specimen_colormap_combo.addItems(["plasma", "viridis", "magma", "cividis", "coolwarm"])
        form.addRow("Mix", self.specimen_mix_combo); form.addRow("Analysis", self.specimen_analysis_combo); form.addRow("Field", self.specimen_field_combo)
        form.addRow("Resolution", self.specimen_resolution_spin); form.addRow("Applied load", self.specimen_load_ratio_spin)
        form.addRow("Acid", self.specimen_acid_combo); form.addRow("Exposure", self.specimen_exposure_spin); form.addRow("Effective D", self.specimen_diffusivity_spin)
        form.addRow("View", self.specimen_cutaway_combo); form.addRow("Colour scale", self.specimen_colormap_combo)
        controls_layout.addLayout(form)
        self.specimen_assumption_note = QLabel("Effective diffusivity is an explicit modelling assumption; acid damage magnitude is calibrated to available residual-strength observations.")
        self.specimen_assumption_note.setObjectName("Muted"); self.specimen_assumption_note.setWordWrap(True); controls_layout.addWidget(self.specimen_assumption_note)
        generate_button = QPushButton("Calculate specimen field"); generate_button.setObjectName("PrimaryButton"); generate_button.clicked.connect(self.generate_specimen_field)
        controls_layout.addWidget(generate_button)
        controls_layout.addWidget(SectionHeader("Camera", "Apply a preset or enter view angles."))
        camera_form = QFormLayout()
        self.specimen_camera_combo = QComboBox(); self.specimen_camera_combo.addItems(CAMERA_PRESETS.keys())
        self.specimen_elevation_spin = QDoubleSpinBox(); self.specimen_elevation_spin.setRange(-90.0, 90.0); self.specimen_elevation_spin.setDecimals(1)
        self.specimen_azimuth_spin = QDoubleSpinBox(); self.specimen_azimuth_spin.setRange(-180.0, 180.0); self.specimen_azimuth_spin.setDecimals(1)
        self._set_camera_values(self.specimen_camera_combo, self.specimen_elevation_spin, self.specimen_azimuth_spin)
        self.specimen_camera_combo.currentTextChanged.connect(
            lambda _text: self._set_camera_values(self.specimen_camera_combo, self.specimen_elevation_spin, self.specimen_azimuth_spin)
        )
        camera_form.addRow("Preset", self.specimen_camera_combo); camera_form.addRow("Elevation", self.specimen_elevation_spin); camera_form.addRow("Azimuth", self.specimen_azimuth_spin)
        controls_layout.addLayout(camera_form)
        apply_camera = QPushButton("Apply view"); apply_camera.clicked.connect(self.render_specimen); controls_layout.addWidget(apply_camera)
        controls_layout.addStretch()
        controls_scroll = scrollable_panel(controls, minimum_width=365); controls_scroll.setMaximumWidth(490); splitter.addWidget(controls_scroll)

        view = QWidget(); view_layout = QVBoxLayout(view); view_layout.setContentsMargins(0, 0, 0, 0); view_layout.setSpacing(10)
        self.specimen_capacity_pill = ValuePill(); self.specimen_mean_pill = ValuePill(); self.specimen_range_pill = ValuePill(); self.specimen_cv_pill = ValuePill(); self.specimen_records_pill = ValuePill()
        toolbar = CompactToolbar()
        for label, pill in (("Bulk capacity", self.specimen_capacity_pill), ("Field mean", self.specimen_mean_pill), ("Field range", self.specimen_range_pill), ("Field CV", self.specimen_cv_pill), ("Source records", self.specimen_records_pill)):
            toolbar.add_metric(label, pill)
        toolbar.add_stretch(); toolbar.add_action(QStyle.StandardPixmap.SP_DialogSaveButton, "Export specimen field", self.export_specimen_field); toolbar.add_action(QStyle.StandardPixmap.SP_FileDialogDetailedView, "Export specimen figure", self.export_specimen_figure); toolbar.finalize()
        view_layout.addWidget(toolbar)
        self.specimen_detail_label = QLabel("No physics-informed specimen field is active."); self.specimen_detail_label.setObjectName("Muted"); self.specimen_detail_label.setWordWrap(True); view_layout.addWidget(self.specimen_detail_label)
        self.specimen_card = QFrame(); self.specimen_card.setObjectName("Card")
        self.specimen_chart_layout = QVBoxLayout(self.specimen_card); self.specimen_chart_layout.setContentsMargins(10, 10, 10, 10)
        self.specimen_canvas = FigureCanvasQTAgg(self.specimen_figure); self.specimen_toolbar = QualityNavigationToolbar(self.specimen_canvas, self.specimen_card)
        self.specimen_chart_layout.addWidget(self.specimen_toolbar); self.specimen_chart_layout.addWidget(self.specimen_canvas, 1); view_layout.addWidget(self.specimen_card, 1)
        splitter.addWidget(view); splitter.setSizes([390, 1040]); layout.addWidget(splitter)
        self._refresh_specimen_fields()
        return page

    @staticmethod
    def _set_camera_values(combo, elevation, azimuth) -> None:
        elev, azim = CAMERA_PRESETS.get(combo.currentText(), CAMERA_PRESETS["Isometric"])
        elevation.setValue(elev); azimuth.setValue(azim)

    def refresh(self) -> None:
        dataframe = self.context.dataframe
        current_mix = self.specimen_mix_combo.currentText() if hasattr(self, "specimen_mix_combo") else ""
        if hasattr(self, "specimen_mix_combo"):
            self.specimen_mix_combo.blockSignals(True); self.specimen_mix_combo.clear(); self.specimen_mix_combo.addItems(DataService.unique_values(dataframe, "mix_id"))
            index = self.specimen_mix_combo.findText(current_mix); self.specimen_mix_combo.setCurrentIndex(index if index >= 0 else 0); self.specimen_mix_combo.blockSignals(False)
        self._refresh_surface_from_twin()

    def _refresh_surface_from_twin(self, *_args) -> None:
        if not hasattr(self, "surface_x_combo"):
            return
        artifact = self.context.active_twin_artifact
        self.surface_x_combo.clear(); self.surface_y_combo.clear()
        if artifact is None:
            self.surface_twin_label.setText("No active Digital Twin. Build or load one in the Digital Twin tab first.")
            self.surface_build_button.setEnabled(False)
            return
        metadata = artifact["metadata"]; candidates = self.service.twin_service.map_axis_candidates(artifact)
        rank = metadata.get("model_rank"); rank_text = f"#%s · " % rank if rank else ""
        self.surface_twin_label.setText(
            f"{COLUMN_LABELS.get(metadata['response'], metadata['response'])} · {metadata.get('method')} · {rank_text}{metadata.get('model_status', 'Unranked')} · {metadata.get('confidence_percent', 95):.0f}% interval"
        )
        for value in candidates:
            label = COLUMN_LABELS.get(value, value); self.surface_x_combo.addItem(label, value); self.surface_y_combo.addItem(label, value)
        if len(candidates) >= 2:
            self.surface_y_combo.setCurrentIndex(1); self.surface_build_button.setEnabled(True)
        else:
            self.surface_build_button.setEnabled(False)
            self.surface_twin_label.setText(self.surface_twin_label.text() + " · fewer than two varying numeric predictors")

    def _refresh_specimen_fields(self, *_args) -> None:
        if not hasattr(self, "specimen_field_combo"):
            return
        analysis = self.specimen_analysis_combo.currentText()
        self.specimen_field_combo.clear()
        if analysis:
            self.specimen_field_combo.addItems(self.service.specimen_fields(analysis))
        acid = analysis == "Acid degradation cube"
        self.specimen_acid_combo.setEnabled(acid); self.specimen_exposure_spin.setEnabled(acid); self.specimen_diffusivity_spin.setEnabled(acid)
        self.specimen_load_ratio_spin.setEnabled(not acid)

    def build_surface(self) -> None:
        artifact = self.context.active_twin_artifact
        if artifact is None:
            QMessageBox.information(self, "No Digital Twin", "Build or load a Digital Twin first."); return
        x_field = self.surface_x_combo.currentData(); y_field = self.surface_y_combo.currentData()
        if not x_field or not y_field:
            QMessageBox.information(self, "3D surface unavailable", "Select two varying predictors."); return
        self.setCursor(Qt.CursorShape.WaitCursor)
        try:
            self.surface_result = self.service.build_surface(
                artifact, self.context.dataframe, str(x_field), str(y_field),
                resolution=self.surface_resolution_spin.value(), mode=self.surface_mode_combo.currentText(),
            )
            self._show_surface_metrics(); self.render_surface(); self.context.message.emit("3D response surface created from the active Digital Twin.")
        except Exception as error:
            QMessageBox.critical(self, "Surface generation failed", str(error))
        finally:
            self.unsetCursor()

    def _show_surface_metrics(self) -> None:
        if self.surface_result is None: return
        summary = self.surface_result.summary; metadata = self.surface_result.artifact["metadata"]; metrics = metadata.get("metrics", {})
        self.surface_min_pill.set_value(f"{summary['minimum_estimate']:.3f}"); self.surface_max_pill.set_value(f"{summary['maximum_estimate']:.3f}")
        self.surface_uncertainty_pill.set_value(f"{summary['mean_uncertainty_percent']:.1f}%", "success" if summary["mean_uncertainty_percent"] <= 15 else "warning")
        self.surface_support_pill.set_value(f"{summary['supported_area_percent']:.1f}%", "success" if summary["supported_area_percent"] >= 70 else "warning")
        self.surface_nodes_pill.set_value(int(summary["map_nodes"])); self.surface_r2_pill.set_value(f"{metrics.get('r2', float('nan')):.3f}", "success" if metrics.get("r2", -1) >= 0.5 else "warning")
        rank = metadata.get("model_rank"); rank_text = f"rank #{rank}/7 · " if rank else ""
        self.surface_detail_label.setText(
            f"Active twin · {metadata.get('method')} · {rank_text}{metadata.get('model_status', 'Unranked')} · {metadata.get('confidence_percent', 95):.0f}% empirical interval · {metadata.get('observations', '—')} fitted records."
        )

    def render_surface(self) -> None:
        if self.surface_result is None: return
        if self.surface_result.mode != self.surface_mode_combo.currentText():
            self.build_surface(); return
        try:
            self.surface_figure = self.service.surface_figure(
                self.surface_result, show_overlay=self.surface_overlay_check.isChecked(), show_wireframe=self.surface_wireframe_check.isChecked(), show_projection=self.surface_projection_check.isChecked(), elevation=self.surface_elevation_spin.value(), azimuth=self.surface_azimuth_spin.value(),
            )
            self.surface_canvas, self.surface_toolbar = self._replace_canvas(self.surface_chart_layout, self.surface_canvas, self.surface_toolbar, self.surface_figure, self.surface_card)
        except Exception as error:
            QMessageBox.critical(self, "3D view failed", str(error))

    def generate_specimen_field(self) -> None:
        mix_id = self.specimen_mix_combo.currentText(); analysis = self.specimen_analysis_combo.currentText(); field_type = self.specimen_field_combo.currentText()
        if not mix_id or not analysis or not field_type:
            QMessageBox.warning(self, "Specimen field unavailable", "Select a mix, analysis, and field."); return
        self.setCursor(Qt.CursorShape.WaitCursor)
        try:
            self.specimen_result = self.service.specimen_field(
                self.context.dataframe, mix_id=mix_id, analysis=analysis, field_type=field_type,
                resolution=self.specimen_resolution_spin.value(), load_ratio_percent=self.specimen_load_ratio_spin.value(),
                acid_type=self.specimen_acid_combo.currentText(), exposure_days=self.specimen_exposure_spin.value(),
                effective_diffusivity_mm2_day=self.specimen_diffusivity_spin.value(), twin_artifact=self.context.active_twin_artifact,
            )
            self._show_specimen_metrics(); self.render_specimen(); self.context.message.emit("Physics-informed specimen field calculated.")
        except Exception as error:
            QMessageBox.critical(self, "Specimen field failed", str(error))
        finally:
            self.unsetCursor()

    def _show_specimen_metrics(self) -> None:
        if self.specimen_result is None: return
        summary = self.specimen_result.summary
        self.specimen_capacity_pill.set_value(f"{self.specimen_result.capacity_value:.3f} MPa"); self.specimen_mean_pill.set_value(f"{summary['mean']:.3f}")
        self.specimen_range_pill.set_value(f"{summary['minimum']:.3f}–{summary['maximum']:.3f}"); self.specimen_cv_pill.set_value(f"{summary['coefficient_of_variation_percent']:.2f}%"); self.specimen_records_pill.set_value(self.specimen_result.source_records)
        assumptions = " ".join(self.specimen_result.assumptions)
        scale_text = (
            f"Colour scale: {self.specimen_result.color_min:.3f} to "
            f"{self.specimen_result.color_max:.3f}; {self.specimen_result.color_scale_basis}. "
            if self.specimen_result.color_min is not None and self.specimen_result.color_max is not None
            else ""
        )
        self.specimen_detail_label.setText(
            f"{self.specimen_result.mix_id} · {self.specimen_result.analysis} · {self.specimen_result.field_type}. "
            f"Field source: {self.specimen_result.field_source}. Capacity source: {self.specimen_result.capacity_source}. "
            f"{scale_text}{assumptions}"
        )

    def render_specimen(self) -> None:
        if self.specimen_result is None: return
        try:
            self.specimen_figure = self.service.specimen_figure(
                self.specimen_result, cutaway_mode=self.specimen_cutaway_combo.currentText(), elevation=self.specimen_elevation_spin.value(), azimuth=self.specimen_azimuth_spin.value(), colormap=self.specimen_colormap_combo.currentText(),
            )
            self.specimen_canvas, self.specimen_toolbar = self._replace_canvas(self.specimen_chart_layout, self.specimen_canvas, self.specimen_toolbar, self.specimen_figure, self.specimen_card)
        except Exception as error:
            QMessageBox.critical(self, "Specimen view failed", str(error))

    @staticmethod
    def _replace_canvas(layout, old_canvas, old_toolbar, figure, parent):
        layout.removeWidget(old_toolbar); old_toolbar.setParent(None); old_toolbar.deleteLater(); layout.removeWidget(old_canvas); old_canvas.setParent(None); old_canvas.deleteLater()
        canvas = FigureCanvasQTAgg(figure); toolbar = QualityNavigationToolbar(canvas, parent); layout.addWidget(toolbar); layout.addWidget(canvas, 1); canvas.draw_idle(); return canvas, toolbar

    def export_surface_grid(self) -> None:
        if self.surface_result is None:
            QMessageBox.information(self, "Nothing to export", "Build a response surface first."); return
        path, _ = QFileDialog.getSaveFileName(self, "Export response grid", str(EXPORT_DIR / "GPC_DTwin_3D_Response_Grid.csv"), "CSV data (*.csv)")
        if path:
            try:
                destination = self.service.export_dataframe(self.surface_result.surface, path); self.context.message.emit(f"Response grid exported to {destination.name}.")
            except Exception as error: QMessageBox.critical(self, "Export failed", str(error))

    def export_specimen_field(self) -> None:
        if self.specimen_result is None:
            QMessageBox.information(self, "Nothing to export", "Calculate a specimen field first."); return
        path, _ = QFileDialog.getSaveFileName(self, "Export specimen field", str(EXPORT_DIR / "GPC_DTwin_Physics_Specimen_Field.csv"), "CSV data (*.csv)")
        if path:
            try:
                destination = self.service.export_dataframe(self.specimen_result.field, path); self.context.message.emit(f"Specimen field exported to {destination.name}.")
            except Exception as error: QMessageBox.critical(self, "Export failed", str(error))

    def export_surface_figure(self) -> None:
        self._export_figure(self.surface_figure, "GPC_DTwin_3D_Response_Surface.png")

    def export_specimen_figure(self) -> None:
        self._export_figure(self.specimen_figure, "GPC_DTwin_Physics_Specimen_Field.png")

    def _export_figure(self, figure: Figure, filename: str) -> None:
        open_figure_export_dialog(self, figure, suggested_name=str(EXPORT_DIR / filename))
