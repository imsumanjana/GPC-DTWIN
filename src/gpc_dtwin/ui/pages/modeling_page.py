from __future__ import annotations

from pathlib import Path

import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QFileDialog, QFormLayout, QFrame,
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QSplitter, QTableView, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout,
    QWidget,
)

from gpc_dtwin.columns import (
    COLUMN_LABELS, MODEL_DEFAULT_PREDICTORS, MODEL_PREDICTOR_COLUMNS,
    MODEL_RESPONSE_COLUMNS,
)
from gpc_dtwin.figure_export import save_square_figure
from gpc_dtwin.paths import EXPORT_DIR, MODEL_DIR
from gpc_dtwin.services.modeling_service import ModelComparisonResult, ModelingService
from gpc_dtwin.ui.models import DataFrameModel
from gpc_dtwin.ui.figure_tabs import FigureTabs
from gpc_dtwin.ui.scrolling import scrollable_panel
from gpc_dtwin.ui.widgets import SectionHeader, ValuePill


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

        self.context.data_changed.connect(self.refresh)
        self.refresh()
        self.refresh_library()

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

        controls_layout.addWidget(QLabel("Algorithms"))
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
        metrics = QHBoxLayout()
        self.best_model_pill = ValuePill()
        self.rmse_pill = ValuePill()
        self.mae_pill = ValuePill()
        self.r2_pill = ValuePill()
        self.observations_pill = ValuePill()
        for label, pill in (
            ("Best model", self.best_model_pill),
            ("RMSE", self.rmse_pill),
            ("MAE", self.mae_pill),
            ("R²", self.r2_pill),
            ("Records", self.observations_pill),
        ):
            metrics.addWidget(QLabel(label))
            metrics.addWidget(pill)
        metrics.addStretch()
        results_layout.addLayout(metrics)

        self.cv_label = QLabel("Select a response and predictors, then compare models.")
        self.cv_label.setObjectName("Muted")
        self.cv_label.setWordWrap(True)
        results_layout.addWidget(self.cv_label)

        toolbar = QHBoxLayout()
        self.diagnostic_algorithm = QComboBox()
        self.diagnostic_algorithm.currentTextChanged.connect(self.update_diagnostics)
        toolbar.addWidget(QLabel("Diagnostics"))
        toolbar.addWidget(self.diagnostic_algorithm)
        toolbar.addStretch()
        export_table = QPushButton("Export results")
        export_table.clicked.connect(self.export_comparison)
        export_figure = QPushButton("Export figure")
        export_figure.clicked.connect(self.export_active_figure)
        toolbar.addWidget(export_table)
        toolbar.addWidget(export_figure)
        results_layout.addLayout(toolbar)

        self.result_tabs = QTabWidget()
        self.result_tabs.currentChanged.connect(self._active_result_tab_changed)

        comparison_widget = QWidget()
        comparison_layout = QHBoxLayout(comparison_widget)
        comparison_splitter = QSplitter()
        self.ranking_model = DataFrameModel()
        self.ranking_table = QTableView()
        self.ranking_table.setModel(self.ranking_model)
        self.ranking_table.setSortingEnabled(True)
        self.ranking_table.setAlternatingRowColors(True)
        comparison_splitter.addWidget(self.ranking_table)
        self.comparison_canvas = FigureCanvasQTAgg(Figure(figsize=(7, 5), constrained_layout=True))
        comparison_splitter.addWidget(self.comparison_canvas)
        comparison_splitter.setSizes([500, 700])
        comparison_layout.addWidget(comparison_splitter)
        self.result_tabs.addTab(comparison_widget, "Ranking")

        diagnostic_widget = QWidget()
        diagnostic_layout = QVBoxLayout(diagnostic_widget)
        self.diagnostic_figure_tabs = FigureTabs(minimum_canvas_size=(620, 540))
        diagnostic_layout.addWidget(self.diagnostic_figure_tabs)
        self.result_tabs.addTab(diagnostic_widget, "Diagnostics")

        influence_widget = QWidget()
        influence_layout = QHBoxLayout(influence_widget)
        influence_splitter = QSplitter()
        self.influence_model = DataFrameModel()
        self.influence_table = QTableView()
        self.influence_table.setModel(self.influence_model)
        self.influence_table.setAlternatingRowColors(True)
        influence_splitter.addWidget(self.influence_table)
        self.influence_canvas = FigureCanvasQTAgg(Figure(figsize=(7, 5), constrained_layout=True))
        influence_splitter.addWidget(self.influence_canvas)
        influence_splitter.setSizes([460, 720])
        influence_layout.addWidget(influence_splitter)
        self.result_tabs.addTab(influence_widget, "Feature influence")

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

    def refresh(self) -> None:
        self._fill_combo(self.response_combo, MODEL_RESPONSE_COLUMNS, "compressive_strength_mpa")
        self._fill_check_list(
            self.predictor_list,
            MODEL_PREDICTOR_COLUMNS,
            checked_items=set(MODEL_DEFAULT_PREDICTORS),
        )
        self._fill_check_list(
            self.algorithm_list,
            self.service.algorithm_names(),
            checked_items=set(self.service.algorithm_names()),
            use_labels=False,
        )
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
        algorithms = self._checked_values(self.algorithm_list)
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
            self._show_result(result)
            self._configure_prediction_inputs(result.artifact)
            self.tabs.setCurrentIndex(0)
            completion = (
                f"Model comparison completed. {result.best_algorithm} ranked first by RMSE."
            )
            if result.omitted_predictors:
                count = len(result.omitted_predictors)
                completion += (
                    f" {count} unavailable predictor"
                    f"{'s were' if count != 1 else ' was'} omitted."
                )
            self.context.message.emit(completion)
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
        keys = ["comparison", "diagnostics", "influence"]
        if 0 <= index < len(keys) and keys[index] in self.figures:
            self.figures["active"] = self.figures[keys[index]]

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
            self.tabs.setCurrentIndex(1)
            self.context.message.emit(f"Loaded {path.name}.")
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
        keys = ["comparison", "diagnostics", "influence"]
        key = keys[self.result_tabs.currentIndex()] if self.result_tabs.currentIndex() < len(keys) else "comparison"
        figure = (
            self.diagnostic_figure_tabs.current_figure()
            if key == "diagnostics" else self.figures.get(key)
        )
        if figure is None:
            QMessageBox.information(self, "Nothing to export", "Run a model comparison first.")
            return
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(
            self, "Export figure", str(EXPORT_DIR / f"model_{key}.png"),
            "PNG image (*.png);;PDF document (*.pdf);;SVG image (*.svg);;TIFF image (*.tiff)"
        )
        if path:
            destination = Path(path)
            if not destination.suffix:
                destination = destination.with_suffix(".png")
            save_square_figure(figure, destination)
            self.context.message.emit(f"Figure exported to {destination.name}.")
