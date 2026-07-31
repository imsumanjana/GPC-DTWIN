from __future__ import annotations

from pathlib import Path

import pandas as pd
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QFileDialog, QFormLayout, QFrame,
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QSpinBox, QSplitter, QStyle, QTableView, QTableWidget, QTableWidgetItem, QTabWidget,
    QVBoxLayout, QWidget,
)

from gpc_dtwin.columns import (
    COLUMN_LABELS, MODEL_DEFAULT_PREDICTORS, MODEL_NUMERIC_PREDICTORS,
    MODEL_PREDICTOR_COLUMNS, MODEL_RESPONSE_COLUMNS,
)
from gpc_dtwin.ui.export_preview_dialog import open_figure_export_dialog
from gpc_dtwin.paths import EXPORT_DIR, TWIN_DIR
from gpc_dtwin.services.digital_twin_service import DigitalTwinService, TwinBuildResult
from gpc_dtwin.ui.models import DataFrameModel
from gpc_dtwin.ui.figure_tabs import FigureTabs
from gpc_dtwin.ui.scrolling import scrollable_panel
from gpc_dtwin.ui.widgets import CompactToolbar, SectionHeader, ValuePill


class DigitalTwinPage(QWidget):
    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.context = context
        self.service = DigitalTwinService()
        self.current_result: TwinBuildResult | None = None
        self.active_artifact: dict | None = None
        self.batch_predictions = pd.DataFrame()
        self.map_data = pd.DataFrame()
        self.calibration_figures: dict[str, Figure] = {}
        self.map_figures: dict[str, Figure] = {}
        self.map_mode = "2d"

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 24)
        root.setSpacing(14)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_tab(), "Build and calibrate")
        self.tabs.addTab(self._scenario_tab(), "Prediction")
        self.tabs.addTab(self._map_tab(), "Response maps")
        self.tabs.addTab(self._library_tab(), "Twin library")
        root.addWidget(self.tabs, 1)

        self.context.data_changed.connect(self.refresh)
        self.refresh()
        self.refresh_library()

    def _build_tab(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter()

        controls = QFrame()
        controls.setObjectName("Card")
        controls.setMinimumWidth(330)
        controls.setMaximumWidth(430)
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(18, 18, 18, 18)
        controls_layout.setSpacing(10)
        form = QFormLayout()
        self.response_combo = QComboBox()
        self.response_combo.currentIndexChanged.connect(self.refresh_predictor_availability)
        self.method_combo = QComboBox()
        self.method_combo.addItems(self.service.method_names())
        self.confidence_combo = QComboBox()
        for value in (90.0, 95.0, 99.0):
            self.confidence_combo.addItem(f"{value:.0f}%", value)
        self.confidence_combo.setCurrentIndex(1)
        form.addRow("Response", self.response_combo)
        form.addRow("Twin method", self.method_combo)
        form.addRow("Confidence", self.confidence_combo)
        controls_layout.addLayout(form)

        controls_layout.addWidget(QLabel("Predictors"))
        self.predictor_list = QListWidget()
        self.predictor_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        controls_layout.addWidget(self.predictor_list, 1)
        self.include_review = QCheckBox("Include records marked for review")
        self.include_review.toggled.connect(self.refresh_predictor_availability)
        controls_layout.addWidget(self.include_review)
        self.predictor_note = QLabel(
            "Unavailable predictors are excluded automatically for the selected response."
        )
        self.predictor_note.setObjectName("Muted")
        self.predictor_note.setWordWrap(True)
        controls_layout.addWidget(self.predictor_note)
        build_button = QPushButton("Build digital twin")
        build_button.setObjectName("PrimaryButton")
        build_button.clicked.connect(self.build_twin)
        controls_layout.addWidget(build_button)
        controls_scroll = scrollable_panel(controls, minimum_width=350)
        controls_scroll.setMaximumWidth(470)
        splitter.addWidget(controls_scroll)

        results = QWidget()
        results_layout = QVBoxLayout(results)
        results_layout.setContentsMargins(0, 0, 0, 0)
        self.method_pill = ValuePill()
        self.rmse_pill = ValuePill()
        self.r2_pill = ValuePill()
        self.coverage_pill = ValuePill()
        self.width_pill = ValuePill()
        self.records_pill = ValuePill()
        toolbar = CompactToolbar()
        for label, pill in (
            ("Method", self.method_pill),
            ("RMSE", self.rmse_pill),
            ("R²", self.r2_pill),
            ("Coverage", self.coverage_pill),
            ("Mean width", self.width_pill),
            ("Records", self.records_pill),
        ):
            toolbar.add_metric(label, pill)
        toolbar.add_stretch()
        toolbar.add_action(
            QStyle.StandardPixmap.SP_DialogSaveButton,
            "Export calibration data",
            self.export_calibration,
        )
        toolbar.add_action(
            QStyle.StandardPixmap.SP_FileDialogDetailedView,
            "Export calibration figure",
            self.export_calibration_figure,
        )
        toolbar.finalize()
        results_layout.addWidget(toolbar)

        self.calibration_label = QLabel("Choose a response and predictors, then build a twin.")
        self.calibration_label.setObjectName("Muted")
        self.calibration_label.setWordWrap(True)
        results_layout.addWidget(self.calibration_label)

        calibration_splitter = QSplitter()
        self.calibration_model = DataFrameModel()
        self.calibration_table = QTableView()
        self.calibration_table.setModel(self.calibration_model)
        self.calibration_table.setSortingEnabled(True)
        self.calibration_table.setAlternatingRowColors(True)
        calibration_splitter.addWidget(self.calibration_table)
        self.calibration_figure_tabs = FigureTabs(minimum_canvas_size=(620, 540))
        calibration_splitter.addWidget(self.calibration_figure_tabs)
        calibration_splitter.setSizes([520, 780])
        results_layout.addWidget(calibration_splitter, 1)
        splitter.addWidget(results)
        splitter.setSizes([360, 1050])
        layout.addWidget(splitter)
        return page

    def _scenario_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)

        info = QFrame()
        info.setObjectName("Card")
        info_layout = QHBoxLayout(info)
        info_layout.setContentsMargins(18, 16, 18, 16)
        texts = QVBoxLayout()
        self.active_twin_label = QLabel("No twin selected")
        self.active_twin_label.setObjectName("SectionTitle")
        self.active_twin_detail = QLabel("Build a twin or load one from the library.")
        self.active_twin_detail.setObjectName("Muted")
        texts.addWidget(self.active_twin_label)
        texts.addWidget(self.active_twin_detail)
        info_layout.addLayout(texts, 1)
        layout.addWidget(info)

        scenario = QFrame()
        scenario.setObjectName("Card")
        scenario_layout = QVBoxLayout(scenario)
        scenario_layout.setContentsMargins(18, 16, 18, 16)
        scenario_layout.addWidget(SectionHeader(
            "Single scenario",
            "Enter material and process conditions. Blank cells use fitted default values."
        ))
        self.scenario_table = QTableWidget(1, 0)
        self.scenario_table.setAlternatingRowColors(True)
        self.scenario_table.setMaximumHeight(125)
        scenario_layout.addWidget(self.scenario_table)
        actions = QHBoxLayout()
        predict_button = QPushButton("Estimate scenario")
        predict_button.setObjectName("PrimaryButton")
        predict_button.clicked.connect(self.predict_scenario)
        actions.addWidget(predict_button)
        self.mean_pill = ValuePill()
        self.interval_pill = ValuePill()
        self.std_pill = ValuePill()
        self.reliability_pill = ValuePill()
        self.distance_pill = ValuePill()
        for label, pill in (
            ("Estimate", self.mean_pill),
            ("Interval", self.interval_pill),
            ("Uncertainty", self.std_pill),
            ("Reliability", self.reliability_pill),
            ("Distance", self.distance_pill),
        ):
            actions.addWidget(QLabel(label))
            actions.addWidget(pill)
        actions.addStretch()
        scenario_layout.addLayout(actions)
        self.scenario_reason = QLabel("")
        self.scenario_reason.setObjectName("Muted")
        self.scenario_reason.setWordWrap(True)
        scenario_layout.addWidget(self.scenario_reason)
        layout.addWidget(scenario)

        batch = QFrame()
        batch.setObjectName("Card")
        batch_layout = QVBoxLayout(batch)
        batch_layout.setContentsMargins(18, 16, 18, 16)
        header = QHBoxLayout()
        header.addWidget(SectionHeader(
            "Batch prediction",
            "Apply the active twin to compatible records and review uncertainty and domain support."
        ), 1)
        run_batch = QPushButton("Estimate active dataset")
        run_batch.clicked.connect(self.predict_active_dataset)
        export_batch = QPushButton("Export predictions")
        export_batch.clicked.connect(self.export_predictions)
        header.addWidget(run_batch)
        header.addWidget(export_batch)
        batch_layout.addLayout(header)
        self.prediction_model = DataFrameModel()
        self.prediction_table = QTableView()
        self.prediction_table.setModel(self.prediction_model)
        self.prediction_table.setSortingEnabled(True)
        self.prediction_table.setAlternatingRowColors(True)
        batch_layout.addWidget(self.prediction_table, 1)
        layout.addWidget(batch, 1)
        return page

    def _map_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        toolbar_card = QFrame()
        toolbar_card.setObjectName("Card")
        toolbar = QHBoxLayout(toolbar_card)
        toolbar.setContentsMargins(18, 14, 18, 14)
        self.map_x_combo = QComboBox()
        self.map_y_combo = QComboBox()
        self.map_x_combo.currentIndexChanged.connect(self._keep_map_axes_distinct)
        self.map_y_combo.currentIndexChanged.connect(self._keep_map_axes_distinct)
        self.map_x_combo.currentIndexChanged.connect(self._invalidate_map_view)
        self.map_y_combo.currentIndexChanged.connect(self._invalidate_map_view)
        self.map_resolution = QSpinBox()
        self.map_resolution.setRange(15, 100)
        self.map_resolution.setValue(45)
        self.map_resolution.valueChanged.connect(self._invalidate_map_view)
        toolbar.addWidget(QLabel("Horizontal axis"))
        toolbar.addWidget(self.map_x_combo)
        toolbar.addWidget(QLabel("Vertical axis"))
        toolbar.addWidget(self.map_y_combo)
        toolbar.addWidget(QLabel("Resolution"))
        toolbar.addWidget(self.map_resolution)
        generate = QPushButton("Generate response map")
        generate.setObjectName("PrimaryButton")
        generate.clicked.connect(self.generate_map)
        export_data = QPushButton("Export map data")
        export_data.clicked.connect(self.export_map_data)
        export_figure = QPushButton("Export figure")
        export_figure.clicked.connect(self.export_map_figure)
        toolbar.addStretch()
        toolbar.addWidget(generate)
        toolbar.addWidget(export_data)
        toolbar.addWidget(export_figure)
        layout.addWidget(toolbar_card)

        self.map_note = QLabel("Select an active twin with at least two numeric predictors.")
        self.map_note.setObjectName("Muted")
        self.map_note.setWordWrap(True)
        layout.addWidget(self.map_note)
        self.map_figure_tabs = FigureTabs(
            minimum_canvas_size=(720, 720), square_display=True, natural_square_side=720
        )
        layout.addWidget(self.map_figure_tabs, 1)
        return page

    def _library_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        toolbar = QHBoxLayout()
        save = QPushButton("Save current twin")
        save.setObjectName("PrimaryButton")
        save.clicked.connect(self.save_current_twin)
        load = QPushButton("Load selected")
        load.clicked.connect(self.load_selected_twin)
        delete = QPushButton("Delete selected")
        delete.clicked.connect(self.delete_selected_twin)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh_library)
        toolbar.addWidget(save)
        toolbar.addWidget(load)
        toolbar.addWidget(delete)
        toolbar.addStretch()
        toolbar.addWidget(refresh)
        layout.addLayout(toolbar)
        self.library_model = DataFrameModel()
        self.library_table = QTableView()
        self.library_table.setModel(self.library_model)
        self.library_table.setSortingEnabled(True)
        self.library_table.setAlternatingRowColors(True)
        self.library_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.library_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        layout.addWidget(self.library_table, 1)
        return page

    def refresh(self) -> None:
        current_response = self.response_combo.currentData()
        self.response_combo.blockSignals(True)
        self.response_combo.clear()
        for value in MODEL_RESPONSE_COLUMNS:
            self.response_combo.addItem(COLUMN_LABELS.get(value, value), value)
        target = current_response or "compressive_strength_mpa"
        index = self.response_combo.findData(target)
        self.response_combo.setCurrentIndex(index if index >= 0 else 0)
        self.response_combo.blockSignals(False)

        existing = {
            self.predictor_list.item(i).data(Qt.ItemDataRole.UserRole):
            self.predictor_list.item(i).checkState() == Qt.CheckState.Checked
            for i in range(self.predictor_list.count())
        }
        self.predictor_list.clear()
        for value in MODEL_PREDICTOR_COLUMNS:
            item = QListWidgetItem(COLUMN_LABELS.get(value, value))
            item.setData(Qt.ItemDataRole.UserRole, value)
            checked = existing.get(value, value in MODEL_DEFAULT_PREDICTORS)
            item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
            self.predictor_list.addItem(item)
        self.refresh_predictor_availability()

    def refresh_predictor_availability(self, *_args) -> None:
        if not hasattr(self, "predictor_list"):
            return
        response = self.response_combo.currentData()
        if not response:
            return
        try:
            available, unavailable = self.service.predictor_availability(
                self.context.dataframe,
                str(response),
                MODEL_PREDICTOR_COLUMNS,
                include_review_records=self.include_review.isChecked(),
            )
        except Exception:
            return
        available_set = set(available)
        unavailable_set = set(unavailable)
        labels: list[str] = []
        for index in range(self.predictor_list.count()):
            item = self.predictor_list.item(index)
            field = str(item.data(Qt.ItemDataRole.UserRole))
            enabled = field in available_set and field != response
            flags = item.flags()
            if enabled:
                item.setFlags(flags | Qt.ItemFlag.ItemIsEnabled)
                item.setToolTip("")
            else:
                item.setFlags(flags & ~Qt.ItemFlag.ItemIsEnabled)
                item.setCheckState(Qt.CheckState.Unchecked)
                if field == response:
                    item.setToolTip("The response cannot also be a predictor.")
                else:
                    item.setToolTip(
                        "No usable values overlap the selected response in the active dataset."
                    )
                    if field in unavailable_set:
                        labels.append(COLUMN_LABELS.get(field, field))
        if labels:
            self.predictor_note.setText(
                f"{len(labels)} unavailable parameters are excluded automatically for "
                f"{COLUMN_LABELS.get(str(response), str(response))}."
            )
        else:
            self.predictor_note.setText(
                "All listed predictors have usable overlap with the selected response."
            )

    def _checked_predictors(self) -> list[str]:
        return [
            str(self.predictor_list.item(i).data(Qt.ItemDataRole.UserRole))
            for i in range(self.predictor_list.count())
            if self.predictor_list.item(i).checkState() == Qt.CheckState.Checked
        ]

    def build_twin(self) -> None:
        response = self.response_combo.currentData()
        predictors = [value for value in self._checked_predictors() if value != response]
        if not response:
            return
        self.setCursor(Qt.CursorShape.WaitCursor)
        try:
            result = self.service.build_twin(
                self.context.dataframe,
                response=response,
                predictors=predictors,
                method=self.method_combo.currentText(),
                confidence_percent=float(self.confidence_combo.currentData()),
                include_review_records=self.include_review.isChecked(),
            )
            self.current_result = result
            self._show_result(result)
            self._set_active_artifact(result.artifact)
            self.context.message.emit(
                f"Digital twin created with {result.method} using {result.observations} records."
            )
            if result.omitted_predictors:
                labels = [
                    COLUMN_LABELS.get(field, field)
                    for field in result.omitted_predictors
                ]
                QMessageBox.warning(
                    self,
                    "Parameters excluded",
                    "The digital twin was built after automatically excluding parameters "
                    "without usable values for the selected response:\n\n"
                    + "\n".join(f"• {label}" for label in labels),
                )
        except Exception as error:
            QMessageBox.warning(self, "Digital twin unavailable", str(error))
        finally:
            self.unsetCursor()

    def _show_result(self, result: TwinBuildResult) -> None:
        metrics = result.metrics
        self.method_pill.set_value(result.method, "success")
        self.rmse_pill.set_value(f"{metrics['rmse']:.4f}")
        self.r2_pill.set_value(
            f"{metrics['r2']:.4f}", "success" if metrics["r2"] >= 0.5 else "warning"
        )
        coverage_gap = abs(metrics["coverage_percent"] - result.confidence_percent)
        coverage_tone = "success" if coverage_gap <= 10 else "warning"
        self.coverage_pill.set_value(f"{metrics['coverage_percent']:.1f}%", coverage_tone)
        self.width_pill.set_value(f"{metrics['mean_interval_width']:.4f}")
        self.records_pill.set_value(result.observations)
        message = (
            f"{result.cv_method} · {result.confidence_percent:.0f}% intervals · "
            f"{result.excluded_records} rows omitted."
        )
        if result.omitted_predictors:
            message += " Excluded parameters: " + ", ".join(
                COLUMN_LABELS.get(field, field)
                for field in result.omitted_predictors
            ) + "."
        self.calibration_label.setText(message)
        self.calibration_model.set_dataframe(result.calibration)
        self.calibration_figures = self.service.calibration_figures(result)
        self.calibration_figure_tabs.set_figures(self.calibration_figures)

    def _set_active_artifact(self, artifact: dict) -> None:
        self.active_artifact = artifact
        metadata = artifact["metadata"]
        metrics = metadata.get("metrics", {})
        self.active_twin_label.setText(
            f"{metadata['method']} · {COLUMN_LABELS.get(metadata['response'], metadata['response'])}"
        )
        self.active_twin_detail.setText(
            f"{metadata.get('confidence_percent', 95):.0f}% interval · "
            f"RMSE {metrics.get('rmse', float('nan')):.4f} · "
            f"{metadata.get('observations', '—')} records"
        )
        self._configure_scenario_inputs(artifact)
        self._configure_map_axes(artifact)

    def _configure_scenario_inputs(self, artifact: dict) -> None:
        metadata = artifact["metadata"]
        predictors = list(metadata["predictors"])
        defaults = metadata.get("input_defaults", {})
        self.scenario_table.setColumnCount(len(predictors))
        self.scenario_table.setHorizontalHeaderLabels(
            [COLUMN_LABELS.get(column, column) for column in predictors]
        )
        for index, predictor in enumerate(predictors):
            value = defaults.get(predictor)
            item = QTableWidgetItem("" if value is None else str(value))
            item.setData(Qt.ItemDataRole.UserRole, predictor)
            self.scenario_table.setItem(0, index, item)
        self.scenario_table.resizeColumnsToContents()

    def _configure_map_axes(self, artifact: dict) -> None:
        self.map_data = pd.DataFrame()
        self.map_figures = {}
        self.map_figure_tabs.clear()
        values = self.service.map_axis_candidates(artifact)
        self.map_x_combo.blockSignals(True)
        self.map_y_combo.blockSignals(True)
        self.map_x_combo.clear()
        self.map_y_combo.clear()
        for value in values:
            label = COLUMN_LABELS.get(value, value)
            self.map_x_combo.addItem(label, value)
            self.map_y_combo.addItem(label, value)
        self.map_mode = "2d" if len(values) >= 2 else "1d" if len(values) == 1 else "none"
        self.map_y_combo.setEnabled(self.map_mode == "2d")
        if self.map_mode == "2d":
            self.map_y_combo.setCurrentIndex(1)
            self.map_note.setText(
                "Response maps keep all unselected predictors at fitted default values."
            )
        elif self.map_mode == "1d":
            self.map_note.setText(
                "Only one predictor varies across the fitted data. A one-dimensional response curve will be generated."
            )
        else:
            self.map_note.setText(
                "The active twin has no numeric predictor with a usable fitted range."
            )
        self.map_x_combo.blockSignals(False)
        self.map_y_combo.blockSignals(False)


    def _invalidate_map_view(self, *_args) -> None:
        if not self.map_figures:
            return
        self.map_data = pd.DataFrame()
        self.map_figures = {}
        self.map_figure_tabs.clear()
        self.map_note.setText(
            "Response-view settings changed. Generate the view to update the figure."
        )

    def _keep_map_axes_distinct(self, *_args) -> None:
        if self.map_mode != "2d" or self.map_x_combo.count() < 2:
            return
        if self.map_x_combo.currentData() != self.map_y_combo.currentData():
            return
        sender = self.sender()
        target = self.map_y_combo if sender is self.map_x_combo else self.map_x_combo
        for index in range(target.count()):
            if target.itemData(index) != (
                self.map_x_combo.currentData() if target is self.map_y_combo else self.map_y_combo.currentData()
            ):
                target.blockSignals(True)
                target.setCurrentIndex(index)
                target.blockSignals(False)
                break

    def _scenario_values(self) -> dict[str, object]:
        if self.active_artifact is None:
            return {}
        metadata = self.active_artifact["metadata"]
        numeric = set(metadata.get("numeric_predictors", []))
        defaults = metadata.get("input_defaults", {})
        values: dict[str, object] = {}
        for index, predictor in enumerate(metadata["predictors"]):
            item = self.scenario_table.item(0, index)
            text = "" if item is None else item.text().strip()
            if predictor in numeric:
                values[predictor] = defaults.get(predictor) if text == "" else float(text)
            else:
                values[predictor] = defaults.get(predictor) if text == "" else text
        return values

    def predict_scenario(self) -> None:
        if self.active_artifact is None:
            QMessageBox.information(self, "No twin selected", "Build a twin or load one first.")
            return
        try:
            result = self.service.predict_scenario(self.active_artifact, self._scenario_values())
            self.mean_pill.set_value(f"{float(result['predicted_mean']):.4f}", "success")
            self.interval_pill.set_value(
                f"{float(result['lower_bound']):.3f} – {float(result['upper_bound']):.3f}"
            )
            self.std_pill.set_value(f"{float(result['prediction_std']):.4f}")
            grade = str(result["reliability_class"])
            tone = {"A": "success", "B": "success", "C": "warning", "D": "danger"}.get(grade, "neutral")
            self.reliability_pill.set_value(grade, tone)
            self.distance_pill.set_value(f"{float(result['nearest_training_distance']):.4f}")
            outside = str(result.get("outside_training_range_fields", "")).strip()
            detail = str(result.get("reliability_reason", ""))
            if outside:
                detail += " Outside-range fields: " + outside
            self.scenario_reason.setText(detail)
        except Exception as error:
            QMessageBox.warning(self, "Scenario estimate unavailable", str(error))

    def predict_active_dataset(self) -> None:
        if self.active_artifact is None:
            QMessageBox.information(self, "No twin selected", "Build a twin or load one first.")
            return
        try:
            self.batch_predictions = self.service.predict_dataframe(
                self.active_artifact, self.context.dataframe
            )
            self.prediction_model.set_dataframe(self.batch_predictions)
            self.context.message.emit(
                f"Generated {len(self.batch_predictions)} uncertainty-aware estimates."
            )
        except Exception as error:
            QMessageBox.warning(self, "Batch prediction unavailable", str(error))

    def generate_map(self) -> None:
        if self.active_artifact is None:
            QMessageBox.information(self, "No twin selected", "Build a twin or load one first.")
            return
        x_field = self.map_x_combo.currentData()
        if not x_field or self.map_mode == "none":
            QMessageBox.information(
                self, "Response view unavailable",
                "The active twin does not contain a numeric predictor with a usable fitted range."
            )
            return
        self.setCursor(Qt.CursorShape.WaitCursor)
        try:
            response = self.active_artifact["metadata"]["response"]
            response_label = COLUMN_LABELS.get(response, response)
            if self.map_mode == "1d":
                self.map_data = self.service.response_curve(
                    self.active_artifact, x_field, self.map_resolution.value()
                )
                figure = self.service.response_curve_figure(
                    self.map_data, x_field, response_label
                )
                self.map_figures = {"Response curve": figure}
                self.map_note.setText(
                    f"{len(self.map_data)} curve points · unselected predictors held at fitted defaults."
                )
            else:
                y_field = self.map_y_combo.currentData()
                if not y_field or x_field == y_field:
                    QMessageBox.information(
                        self, "Response map unavailable", "Select two different varying predictors."
                    )
                    return
                self.map_data = self.service.response_map(
                    self.active_artifact, x_field, y_field, self.map_resolution.value()
                )
                self.map_figures = self.service.response_map_figures(
                    self.map_data, x_field, y_field, response_label
                )
                reliability = self.map_data["reliability_class"].value_counts().to_dict()
                summary = " · ".join(f"{grade}: {reliability.get(grade, 0)}" for grade in "ABCD")
                self.map_note.setText(
                    f"{len(self.map_data)} grid points · reliability distribution {summary}."
                )
            self.map_figure_tabs.set_figures(self.map_figures)
        except ValueError as error:
            QMessageBox.information(self, "Response view unavailable", str(error))
        except Exception:
            QMessageBox.warning(
                self, "Response view unavailable",
                "The response view could not be generated. Review the selected axes and fitted data ranges."
            )
        finally:
            self.unsetCursor()

    def save_current_twin(self) -> None:
        if self.current_result is None:
            QMessageBox.information(self, "No current twin", "Build a digital twin first.")
            return
        try:
            path = self.service.save_artifact(self.current_result.artifact, TWIN_DIR)
            self.refresh_library()
            self.context.message.emit(f"Twin saved as {path.name}.")
        except Exception as error:
            QMessageBox.warning(self, "Twin could not be saved", str(error))

    def refresh_library(self) -> None:
        self.library_model.set_dataframe(self.service.list_saved_twins(TWIN_DIR))

    def _selected_twin_path(self) -> Path | None:
        row = self.library_table.currentIndex().row()
        dataframe = self.library_model.dataframe
        if row < 0 or row >= len(dataframe) or "artifact_path" not in dataframe.columns:
            return None
        return Path(str(dataframe.iloc[row]["artifact_path"]))

    def load_selected_twin(self) -> None:
        path = self._selected_twin_path()
        if path is None:
            QMessageBox.information(self, "No twin selected", "Select a twin row first.")
            return
        try:
            artifact = self.service.load_artifact(path)
            self._set_active_artifact(artifact)
            self.tabs.setCurrentIndex(1)
            self.context.message.emit(f"Loaded {path.name}.")
        except Exception as error:
            QMessageBox.warning(self, "Twin could not be loaded", str(error))

    def delete_selected_twin(self) -> None:
        path = self._selected_twin_path()
        if path is None:
            QMessageBox.information(self, "No twin selected", "Select a twin row first.")
            return
        answer = QMessageBox.question(self, "Delete twin?", f"Delete {path.name} and its metadata?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.delete_artifact(path)
            self.refresh_library()
            self.context.message.emit(f"Deleted {path.name}.")
        except Exception as error:
            QMessageBox.warning(self, "Twin could not be deleted", str(error))

    def export_calibration(self) -> None:
        if self.current_result is None:
            QMessageBox.information(self, "Nothing to export", "Build a digital twin first.")
            return
        self._export_dataframe(self.current_result.calibration, "twin_calibration.csv", "Export calibration")

    def export_predictions(self) -> None:
        if self.batch_predictions.empty:
            QMessageBox.information(self, "Nothing to export", "Generate batch predictions first.")
            return
        self._export_dataframe(self.batch_predictions, "twin_predictions.csv", "Export predictions")

    def export_map_data(self) -> None:
        if self.map_data.empty:
            QMessageBox.information(self, "Nothing to export", "Generate a response map first.")
            return
        self._export_dataframe(self.map_data, "twin_response_map.csv", "Export response map")

    def _export_dataframe(self, dataframe: pd.DataFrame, name: str, title: str) -> None:
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(
            self, title, str(EXPORT_DIR / name), "CSV data (*.csv)"
        )
        if path:
            destination = Path(path).with_suffix(".csv")
            dataframe.to_csv(destination, index=False, encoding="utf-8-sig")
            self.context.message.emit(f"Data exported to {destination.name}.")

    def export_calibration_figure(self) -> None:
        self._export_figure(
            self.calibration_figure_tabs.current_figure(), "twin_calibration.png"
        )

    def export_map_figure(self) -> None:
        self._export_figure(
            self.map_figure_tabs.current_figure(), "twin_response_map.png"
        )

    def _export_figure(self, figure: Figure | None, name: str) -> None:
        if figure is None:
            QMessageBox.information(self, "Nothing to export", "Generate the figure first.")
            return
        open_figure_export_dialog(
            self, figure, suggested_name=str(EXPORT_DIR / name)
        )

