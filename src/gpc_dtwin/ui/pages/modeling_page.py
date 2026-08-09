from __future__ import annotations

from pathlib import Path

import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QFileDialog, QFormLayout, QFrame,
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QSplitter, QStyle, QTableView, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout,
    QWidget,
)

from gpc_dtwin.columns import (
    COLUMN_LABELS, MODEL_DEFAULT_PREDICTORS, MODEL_PREDICTOR_COLUMNS,
    MODEL_RESPONSE_COLUMNS,
)
from gpc_dtwin.ui.export_preview_dialog import open_figure_export_dialog
from gpc_dtwin.paths import EXPORT_DIR, MODEL_DIR
from gpc_dtwin.services.modeling_service import ModelComparisonResult, ModelingService
from gpc_dtwin.ui.models import DataFrameModel
from gpc_dtwin.ui.figure_tabs import FigureTabs
from gpc_dtwin.ui.scrolling import scrollable_panel
from gpc_dtwin.ui.widgets import CompactToolbar, SectionHeader, ValuePill


class ModelingPage(QWidget):
    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.context = context
        self.service = ModelingService()
        self.current_result: ModelComparisonResult | None = None
        self.active_artifact: dict | None = None
        self.batch_predictions = pd.DataFrame()
        self.figures: dict[str, Figure] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 24)
        root.setSpacing(14)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._comparison_tab(), "Model comparison")
        self.tabs.addTab(self._prediction_tab(), "Prediction")
        self.tabs.addTab(self._library_tab(), "Model library")
        root.addWidget(self.tabs, 1)

        self.context.data_changed.connect(self._handle_data_change)
        self.refresh()
        self.refresh_library()
        self._update_workflow_tabs()

    def _comparison_tab(self) -> QWidget:
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
        form.addRow("Response", self.response_combo)
        controls_layout.addLayout(form)

        controls_layout.addWidget(QLabel("Predictors"))
        self.predictor_list = QListWidget()
        self.predictor_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        controls_layout.addWidget(self.predictor_list, 1)

        controls_layout.addWidget(QLabel("Candidate algorithms · all 7 benchmarked"))
        self.algorithm_list = QListWidget()
        self.algorithm_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.algorithm_list.setMaximumHeight(190)
        controls_layout.addWidget(self.algorithm_list)

        self.include_review = QCheckBox("Include records marked for review")
        self.include_review.setChecked(False)
        self.include_review.toggled.connect(self.refresh_predictor_availability)
        controls_layout.addWidget(self.include_review)
        self.predictor_note = QLabel(
            "Unavailable predictors are disabled automatically for the selected response."
        )
        self.predictor_note.setObjectName("Muted")
        self.predictor_note.setWordWrap(True)
        controls_layout.addWidget(self.predictor_note)
        run_button = QPushButton("Compare models")
        run_button.setObjectName("PrimaryButton")
        run_button.clicked.connect(self.run_comparison)
        controls_layout.addWidget(run_button)
        controls_scroll = scrollable_panel(controls, minimum_width=350)
        controls_scroll.setMaximumWidth(470)
        splitter.addWidget(controls_scroll)

        results = QWidget()
        results_layout = QVBoxLayout(results)
        results_layout.setContentsMargins(0, 0, 0, 0)
        self.best_model_pill = ValuePill()
        self.rmse_pill = ValuePill()
        self.mae_pill = ValuePill()
        self.r2_pill = ValuePill()
        self.observations_pill = ValuePill()
        toolbar = CompactToolbar()
        for label, pill in (
            ("Best model", self.best_model_pill),
            ("RMSE", self.rmse_pill),
            ("MAE", self.mae_pill),
            ("R²", self.r2_pill),
            ("Records", self.observations_pill),
        ):
            toolbar.add_metric(label, pill)
        toolbar.add_stretch()
        toolbar.add_label("Diagnostics")
        self.diagnostic_algorithm = QComboBox()
        self.diagnostic_algorithm.setMinimumWidth(150)
        self.diagnostic_algorithm.currentTextChanged.connect(self.update_diagnostics)
        toolbar.add_widget(self.diagnostic_algorithm)
        toolbar.add_action(
            QStyle.StandardPixmap.SP_DialogSaveButton,
            "Export model-comparison results",
            self.export_comparison,
        )
        toolbar.add_action(
            QStyle.StandardPixmap.SP_FileDialogDetailedView,
            "Export active figure",
            self.export_active_figure,
        )
        toolbar.finalize()
        results_layout.addWidget(toolbar)

        self.cv_label = QLabel("Select a response and predictors, then compare models.")
        self.cv_label.setObjectName("Muted")
        self.cv_label.setWordWrap(True)
        results_layout.addWidget(self.cv_label)

        self.result_tabs = QTabWidget()
        self.result_tabs.currentChanged.connect(self._active_result_tab_changed)

        comparison_table_widget = QWidget()
        comparison_table_layout = QVBoxLayout(comparison_table_widget)
        comparison_table_layout.setContentsMargins(0, 0, 0, 0)
        self.ranking_model = DataFrameModel()
        self.ranking_table = QTableView()
        self.ranking_table.setModel(self.ranking_model)
        self.ranking_table.setSortingEnabled(True)
        self.ranking_table.setAlternatingRowColors(True)
        comparison_table_layout.addWidget(self.ranking_table, 1)
        self.result_tabs.addTab(comparison_table_widget, "Comparison table")

        comparison_chart_widget = QWidget()
        comparison_chart_layout = QVBoxLayout(comparison_chart_widget)
        comparison_chart_layout.setContentsMargins(0, 0, 0, 0)
        self.comparison_canvas = FigureCanvasQTAgg(Figure(figsize=(7, 5), constrained_layout=True))
        comparison_chart_layout.addWidget(self.comparison_canvas, 1)
        self.result_tabs.addTab(comparison_chart_widget, "Ranking chart")

        diagnostic_widget = QWidget()
        diagnostic_layout = QVBoxLayout(diagnostic_widget)
        self.diagnostic_figure_tabs = FigureTabs(minimum_canvas_size=(620, 540))
        diagnostic_layout.addWidget(self.diagnostic_figure_tabs)
        self.result_tabs.addTab(diagnostic_widget, "Diagnostics")

        influence_table_widget = QWidget()
        influence_table_layout = QVBoxLayout(influence_table_widget)
        influence_table_layout.setContentsMargins(0, 0, 0, 0)
        self.influence_model = DataFrameModel()
        self.influence_table = QTableView()
        self.influence_table.setModel(self.influence_model)
        self.influence_table.setSortingEnabled(True)
        self.influence_table.setAlternatingRowColors(True)
        influence_table_layout.addWidget(self.influence_table, 1)
        self.result_tabs.addTab(influence_table_widget, "Feature influence table")

        influence_chart_widget = QWidget()
        influence_chart_layout = QVBoxLayout(influence_chart_widget)
        influence_chart_layout.setContentsMargins(0, 0, 0, 0)
        self.influence_canvas = FigureCanvasQTAgg(
            Figure(figsize=(7, 5), constrained_layout=True)
        )
        influence_chart_layout.addWidget(self.influence_canvas, 1)
        self.result_tabs.addTab(influence_chart_widget, "Feature influence chart")

        results_layout.addWidget(self.result_tabs, 1)
        splitter.addWidget(results)
        splitter.setSizes([360, 1050])
        layout.addWidget(splitter)
        return page

    def _prediction_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)

        info = QFrame()
        info.setObjectName("Card")
        info_layout = QHBoxLayout(info)
        info_layout.setContentsMargins(18, 16, 18, 16)
        self.active_model_label = QLabel("No model selected")
        self.active_model_label.setObjectName("SectionTitle")
        self.active_model_detail = QLabel("Run a comparison or load a saved model.")
        self.active_model_detail.setObjectName("Muted")
        texts = QVBoxLayout()
        texts.addWidget(self.active_model_label)
        texts.addWidget(self.active_model_detail)
        info_layout.addLayout(texts, 1)
        layout.addWidget(info)

        scenario = QFrame()
        scenario.setObjectName("Card")
        scenario_layout = QVBoxLayout(scenario)
        scenario_layout.setContentsMargins(18, 16, 18, 16)
        scenario_layout.addWidget(SectionHeader(
            "Single scenario", "Enter predictor values for one material scenario. Blank numeric cells use the model median."
        ))
        self.scenario_table = QTableWidget(1, 0)
        self.scenario_table.setAlternatingRowColors(True)
        self.scenario_table.setMaximumHeight(120)
        scenario_layout.addWidget(self.scenario_table)
        scenario_actions = QHBoxLayout()
        predict_scenario = QPushButton("Predict scenario")
        predict_scenario.setObjectName("PrimaryButton")
        predict_scenario.clicked.connect(self.predict_scenario)
        self.scenario_result = ValuePill()
        scenario_actions.addWidget(predict_scenario)
        scenario_actions.addWidget(QLabel("Prediction"))
        scenario_actions.addWidget(self.scenario_result)
        scenario_actions.addStretch()
        scenario_layout.addLayout(scenario_actions)
        layout.addWidget(scenario)

        batch = QFrame()
        batch.setObjectName("Card")
        batch_layout = QVBoxLayout(batch)
        batch_layout.setContentsMargins(18, 16, 18, 16)
        batch_header = QHBoxLayout()
        batch_header.addWidget(SectionHeader(
            "Batch prediction", "Apply the selected model to all compatible rows in the active dataset."
        ), 1)
        predict_batch = QPushButton("Predict active dataset")
        predict_batch.clicked.connect(self.predict_active_dataset)
        export_batch = QPushButton("Export predictions")
        export_batch.clicked.connect(self.export_predictions)
        batch_header.addWidget(predict_batch)
        batch_header.addWidget(export_batch)
        batch_layout.addLayout(batch_header)
        self.prediction_model = DataFrameModel()
        prediction_table = QTableView()
        prediction_table.setModel(self.prediction_model)
        prediction_table.setSortingEnabled(True)
        prediction_table.setAlternatingRowColors(True)
        batch_layout.addWidget(prediction_table, 1)
        layout.addWidget(batch, 1)
        return page

    def _library_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        toolbar = QHBoxLayout()
        save = QPushButton("Save current best model")
        save.setObjectName("PrimaryButton")
        save.clicked.connect(self.save_current_model)
        load = QPushButton("Load selected")
        load.clicked.connect(self.load_selected_model)
        delete = QPushButton("Delete selected")
        delete.clicked.connect(self.delete_selected_model)
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

    def _handle_data_change(self) -> None:
        """Invalidate page-local fitted state when the experimental dataset changes."""
        self.current_result = None
        self.active_artifact = None
        self.batch_predictions = pd.DataFrame()
        self.active_model_label.setText("No model selected")
        self.active_model_detail.setText("Run a comparison or load a saved model.")
        self.scenario_result.set_value("—")
        self.refresh()
        self._update_workflow_tabs()

    def _update_workflow_tabs(self) -> None:
        """Enable point prediction only after a fitted prediction model exists."""
        has_model = self.active_artifact is not None
        self.tabs.setTabEnabled(0, True)
        self.tabs.setTabEnabled(1, has_model)
        self.tabs.setTabEnabled(2, True)
        if not has_model and self.tabs.currentIndex() == 1:
            self.tabs.setCurrentIndex(0)

    def refresh(self) -> None:
        self._fill_combo(self.response_combo, MODEL_RESPONSE_COLUMNS, "compressive_strength_mpa")
        self._fill_check_list(
            self.predictor_list,
            MODEL_PREDICTOR_COLUMNS,
            checked_items=set(MODEL_DEFAULT_PREDICTORS),
        )
        self.algorithm_list.clear()
        for rank, algorithm in enumerate(self.service.algorithm_names(), start=1):
            item = QListWidgetItem(f"{rank}. {algorithm}")
            item.setData(Qt.ItemDataRole.UserRole, algorithm)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.algorithm_list.addItem(item)
        self.refresh_predictor_availability()

    def refresh_predictor_availability(self, *_args) -> None:
        response = self.response_combo.currentData()
        if not response or not hasattr(self, "predictor_list"):
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
        disabled_labels: list[str] = []

        for index in range(self.predictor_list.count()):
            item = self.predictor_list.item(index)
            predictor = str(item.data(Qt.ItemDataRole.UserRole))
            enabled = predictor != response and predictor in available_set
            flags = item.flags()
            if enabled:
                item.setFlags(flags | Qt.ItemFlag.ItemIsEnabled)
                item.setToolTip("")
            else:
                item.setFlags(flags & ~Qt.ItemFlag.ItemIsEnabled)
                item.setCheckState(Qt.CheckState.Unchecked)
                if predictor == response:
                    item.setToolTip("The response cannot also be used as a predictor.")
                else:
                    item.setToolTip(
                        "No usable values overlap the selected response in the active dataset."
                    )
                    if predictor in unavailable_set:
                        disabled_labels.append(COLUMN_LABELS.get(predictor, predictor))

        if disabled_labels:
            self.predictor_note.setText(
                f"{len(disabled_labels)} unavailable fields are disabled for "
                f"{COLUMN_LABELS.get(str(response), str(response))}."
            )
        else:
            self.predictor_note.setText(
                "All listed predictors have usable overlap with the selected response."
            )

    @staticmethod
    def _fill_combo(combo: QComboBox, values: list[str], preferred: str) -> None:
        current = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        for value in values:
            combo.addItem(COLUMN_LABELS.get(value, value), value)
        target = current or preferred
        index = combo.findData(target)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.blockSignals(False)

    @staticmethod
    def _fill_check_list(
        widget: QListWidget,
        values: list[str],
        checked_items: set[str],
        use_labels: bool = True,
    ) -> None:
        existing = {
            widget.item(i).data(Qt.ItemDataRole.UserRole):
            widget.item(i).checkState() == Qt.CheckState.Checked
            for i in range(widget.count())
        }
        widget.clear()
        for value in values:
            text = COLUMN_LABELS.get(value, value) if use_labels else value
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, value)
            checked = existing.get(value, value in checked_items)
            item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
            widget.addItem(item)

    @staticmethod
    def _checked_values(widget: QListWidget) -> list[str]:
        return [
            str(widget.item(i).data(Qt.ItemDataRole.UserRole))
            for i in range(widget.count())
            if widget.item(i).checkState() == Qt.CheckState.Checked
        ]

    def run_comparison(self) -> None:
        response = self.response_combo.currentData()
        predictors = [value for value in self._checked_values(self.predictor_list) if value != response]
        algorithms = self.service.algorithm_names()
        if not response:
            return
        self.setCursor(Qt.CursorShape.WaitCursor)
        try:
            result = self.service.compare_models(
                self.context.dataframe,
                response,
                predictors,
                algorithms,
                include_review_records=self.include_review.isChecked(),
            )
            self.current_result = result
            self.active_artifact = result.artifact
            self.context.set_model_comparison(result)
            self._show_result(result)
            self._configure_prediction_inputs(result.artifact)
            self.tabs.setCurrentIndex(0)
            completion = (
                f"Model comparison completed. {result.best_algorithm} ranked first and is recommended for the Digital Twin."
            )
            if result.omitted_predictors:
                count = len(result.omitted_predictors)
                completion += (
                    f" {count} unavailable predictor"
                    f"{'s were' if count != 1 else ' was'} omitted."
                )
            self.context.message.emit(completion)
            if result.omitted_predictors:
                labels = [
                    COLUMN_LABELS.get(field, field)
                    for field in result.omitted_predictors
                ]
                QMessageBox.warning(
                    self,
                    "Parameters excluded",
                    "Model comparison completed after automatically excluding parameters "
                    "without usable values for the selected response:\n\n"
                    + "\n".join(f"• {label}" for label in labels),
                )
        except Exception as error:
            QMessageBox.warning(self, "Model comparison unavailable", str(error))
        finally:
            self.unsetCursor()

    def _show_result(self, result: ModelComparisonResult) -> None:
        metrics = result.best_metrics
        self.best_model_pill.set_value(result.best_algorithm, "success")
        self.rmse_pill.set_value(f"{metrics['rmse']:.4f}")
        self.mae_pill.set_value(f"{metrics['mae']:.4f}")
        self.r2_pill.set_value(f"{metrics['r2']:.4f}", "success" if metrics["r2"] >= 0.5 else "warning")
        self.observations_pill.set_value(result.observations)
        message = (
            f"{result.cv_method} · {result.excluded_records} rows omitted because the "
            "response was unavailable or the record state was excluded."
        )
        if result.omitted_predictors:
            labels = [
                COLUMN_LABELS.get(column, column)
                for column in result.omitted_predictors
            ]
            message += " Unavailable predictors omitted: " + ", ".join(labels) + "."
        self.cv_label.setText(message)
        self.ranking_model.set_dataframe(result.rankings)
        self.influence_model.set_dataframe(result.feature_influence)

        self.diagnostic_algorithm.blockSignals(True)
        self.diagnostic_algorithm.clear()
        self.diagnostic_algorithm.addItems(result.rankings["algorithm"].astype(str).tolist())
        self.diagnostic_algorithm.setCurrentText(result.best_algorithm)
        self.diagnostic_algorithm.blockSignals(False)

        self.figures["comparison"] = self.service.comparison_figure(result)
        diagnostic_figures = self.service.diagnostic_figures(result, result.best_algorithm)
        self.figures["diagnostics"] = next(iter(diagnostic_figures.values()))
        self.figures["influence"] = self.service.influence_figure(result)
        self.comparison_canvas = self._replace_canvas(self.comparison_canvas, self.figures["comparison"])
        self.diagnostic_figure_tabs.set_figures(diagnostic_figures)
        self.influence_canvas = self._replace_canvas(self.influence_canvas, self.figures["influence"])
        self._set_active_artifact(result.artifact)

    def update_diagnostics(self, algorithm: str) -> None:
        if self.current_result is None or not algorithm:
            return
        try:
            figures = self.service.diagnostic_figures(self.current_result, algorithm)
            self.figures["diagnostics"] = next(iter(figures.values()))
            self.diagnostic_figure_tabs.set_figures(figures)
        except Exception as error:
            QMessageBox.warning(self, "Diagnostics unavailable", str(error))

    def _active_result_tab_changed(self, index: int) -> None:
        # The comparison table is intentionally a peer tab to the response charts.
        # Only figure-bearing tabs update the active figure used by the export action.
        key_by_index = {1: "comparison", 2: "diagnostics", 4: "influence"}
        key = key_by_index.get(index)
        if key and key in self.figures:
            self.figures["active"] = self.figures[key]

    @staticmethod
    def _replace_canvas(old: FigureCanvasQTAgg, figure: Figure) -> FigureCanvasQTAgg:
        parent = old.parentWidget()
        canvas = FigureCanvasQTAgg(figure)
        if isinstance(parent, QSplitter):
            index = parent.indexOf(old)
            old.setParent(None)
            old.deleteLater()
            parent.insertWidget(index, canvas)
        else:
            layout = parent.layout()
            index = layout.indexOf(old)
            layout.removeWidget(old)
            old.setParent(None)
            old.deleteLater()
            layout.insertWidget(index, canvas, 1)
        canvas.draw_idle()
        return canvas

    def _configure_prediction_inputs(self, artifact: dict) -> None:
        metadata = artifact["metadata"]
        predictors = list(metadata["predictors"])
        defaults = metadata.get("input_defaults", {})
        self.scenario_table.setColumnCount(len(predictors))
        self.scenario_table.setHorizontalHeaderLabels(
            [COLUMN_LABELS.get(column, column) for column in predictors]
        )
        for column_index, predictor in enumerate(predictors):
            value = defaults.get(predictor)
            item = QTableWidgetItem("" if value is None else str(value))
            item.setData(Qt.ItemDataRole.UserRole, predictor)
            self.scenario_table.setItem(0, column_index, item)
        self.scenario_table.resizeColumnsToContents()

    def _set_active_artifact(self, artifact: dict) -> None:
        self.active_artifact = artifact
        metadata = artifact["metadata"]
        metrics = metadata.get("metrics", {})
        self.active_model_label.setText(
            f"{metadata['algorithm']} · {COLUMN_LABELS.get(metadata['response'], metadata['response'])}"
        )
        self.active_model_detail.setText(
            f"{metadata.get('cv_method', '')} · RMSE {metrics.get('rmse', float('nan')):.4f} · "
            f"{metadata.get('observations', '—')} records"
        )
        self._configure_prediction_inputs(artifact)
        self._update_workflow_tabs()

    def predict_scenario(self) -> None:
        if self.active_artifact is None:
            QMessageBox.information(self, "No model selected", "Run a comparison or load a saved model first.")
            return
        metadata = self.active_artifact["metadata"]
        numeric = set(metadata.get("numeric_predictors", []))
        defaults = metadata.get("input_defaults", {})
        values: dict[str, object] = {}
        try:
            for column_index, predictor in enumerate(metadata["predictors"]):
                item = self.scenario_table.item(0, column_index)
                text = "" if item is None else item.text().strip()
                if predictor in numeric:
                    values[predictor] = defaults.get(predictor) if text == "" else float(text)
                else:
                    values[predictor] = defaults.get(predictor) if text == "" else text
            prediction = self.service.predict_scenario(self.active_artifact, values)
            self.scenario_result.set_value(f"{prediction:.4f}", "success")
        except Exception as error:
            QMessageBox.warning(self, "Prediction unavailable", str(error))

    def predict_active_dataset(self) -> None:
        if self.active_artifact is None:
            QMessageBox.information(self, "No model selected", "Run a comparison or load a saved model first.")
            return
        try:
            self.batch_predictions = self.service.predict_dataframe(
                self.active_artifact, self.context.dataframe
            )
            self.prediction_model.set_dataframe(self.batch_predictions)
            self.context.message.emit(f"Generated {len(self.batch_predictions)} predictions.")
        except Exception as error:
            QMessageBox.warning(self, "Batch prediction unavailable", str(error))

    def save_current_model(self) -> None:
        if self.current_result is None:
            QMessageBox.information(self, "No current model", "Run a model comparison first.")
            return
        try:
            path = self.service.save_artifact(self.current_result.artifact, MODEL_DIR)
            self.refresh_library()
            self.context.message.emit(f"Model saved as {path.name}.")
        except Exception as error:
            QMessageBox.warning(self, "Model could not be saved", str(error))

    def refresh_library(self) -> None:
        self.library_model.set_dataframe(self.service.list_saved_models(MODEL_DIR))

    def _selected_model_path(self) -> Path | None:
        row = self.library_table.currentIndex().row()
        dataframe = self.library_model.dataframe
        if row < 0 or row >= len(dataframe) or "artifact_path" not in dataframe.columns:
            return None
        return Path(str(dataframe.iloc[row]["artifact_path"]))

    def load_selected_model(self) -> None:
        path = self._selected_model_path()
        if path is None:
            QMessageBox.information(self, "No model selected", "Select a model row first.")
            return
        try:
            artifact = self.service.load_artifact(path)
            self._set_active_artifact(artifact)
            ranking = self.service.comparison_from_artifact(artifact)
            if ranking is not None and self.service.artifact_matches_dataframe(
                artifact, self.context.dataframe
            ):
                self.context.set_model_comparison(ranking)
                handoff = " Validated ranking restored; Digital Twin is now available."
            else:
                handoff = (
                    " Point prediction is available, but the saved ranking does not match the active "
                    "dataset; compare models again before opening Digital Twin."
                )
            self.tabs.setCurrentIndex(1)
            self.context.message.emit(f"Loaded {path.name}." + handoff)
        except Exception as error:
            QMessageBox.warning(self, "Model could not be loaded", str(error))

    def delete_selected_model(self) -> None:
        path = self._selected_model_path()
        if path is None:
            QMessageBox.information(self, "No model selected", "Select a model row first.")
            return
        answer = QMessageBox.question(
            self, "Delete model?", f"Delete {path.name} and its metadata?"
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.delete_artifact(path)
            self.refresh_library()
            self.context.message.emit(f"Deleted {path.name}.")
        except Exception as error:
            QMessageBox.warning(self, "Model could not be deleted", str(error))

    def export_comparison(self) -> None:
        if self.current_result is None:
            QMessageBox.information(self, "Nothing to export", "Run a model comparison first.")
            return
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(
            self, "Export model ranking", str(EXPORT_DIR / "model_comparison.csv"), "CSV data (*.csv)"
        )
        if path:
            destination = Path(path).with_suffix(".csv")
            self.current_result.rankings.to_csv(destination, index=False, encoding="utf-8-sig")
            self.context.message.emit(f"Model ranking exported to {destination.name}.")

    def export_predictions(self) -> None:
        if self.batch_predictions.empty:
            QMessageBox.information(self, "Nothing to export", "Generate batch predictions first.")
            return
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(
            self, "Export predictions", str(EXPORT_DIR / "model_predictions.csv"), "CSV data (*.csv)"
        )
        if path:
            destination = Path(path).with_suffix(".csv")
            self.batch_predictions.to_csv(destination, index=False, encoding="utf-8-sig")
            self.context.message.emit(f"Predictions exported to {destination.name}.")

    def export_active_figure(self) -> None:
        # Table and ranking-chart tabs both export the ranking chart; later tabs export
        # their corresponding response diagnostic or feature-influence figure.
        key = {0: "comparison", 1: "comparison", 2: "diagnostics", 3: "influence"}.get(
            self.result_tabs.currentIndex(), "comparison"
        )
        figure = (
            self.diagnostic_figure_tabs.current_figure()
            if key == "diagnostics" else self.figures.get(key)
        )
        if figure is None:
            QMessageBox.information(self, "Nothing to export", "Run a model comparison first.")
            return
        open_figure_export_dialog(
            self, figure, suggested_name=str(EXPORT_DIR / f"model_{key}.png")
        )

