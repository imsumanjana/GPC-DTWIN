from __future__ import annotations

from pathlib import Path

import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog,
    QFormLayout, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QScrollArea, QSpinBox, QSplitter, QTableView,
    QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from gpc_dtwin.columns import (
    COLUMN_LABELS, MODEL_DEFAULT_PREDICTORS, MODEL_NUMERIC_PREDICTORS,
    MODEL_PREDICTOR_COLUMNS, MODEL_RESPONSE_COLUMNS,
)
from gpc_dtwin.figure_export import save_square_figure
from gpc_dtwin.paths import ACTIVE_LEARNING_DIR, EXPORT_DIR
from gpc_dtwin.services.active_learning_service import (
    ActiveLearningRunResult, ActiveLearningService, LearningVariable,
    UpdateComparisonResult,
)
from gpc_dtwin.ui.models import DataFrameModel
from gpc_dtwin.ui.widgets import SectionHeader, ValuePill


class ActiveLearningPage(QWidget):
    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.context = context
        self.service = ActiveLearningService()
        self.current_run: ActiveLearningRunResult | None = None
        self.current_update: UpdateComparisonResult | None = None
        self.figures: dict[str, Figure] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 24)
        root.setSpacing(14)
        root.addWidget(SectionHeader(
            "Active Learning",
            "Prioritize informative material experiments, prepare laboratory plans, and quantify model changes after completed tests.",
        ))

        self.tabs = QTabWidget()
        self.tabs.addTab(self._recommendation_tab(), "Experiment recommendations")
        self.tabs.addTab(self._update_tab(), "Closed-loop update")
        self.tabs.addTab(self._library_tab(), "Run library")
        root.addWidget(self.tabs, 1)

        self.context.data_changed.connect(self.refresh)
        self.refresh()
        self.refresh_library()

    # ------------------------------------------------------------------
    # Recommendation tab
    # ------------------------------------------------------------------
    def _recommendation_tab(self) -> QWidget:
        page = QWidget()
        page_layout = QHBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        controls_scroll = QScrollArea()
        controls_scroll.setWidgetResizable(True)
        controls_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        controls_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        controls_scroll.setMinimumWidth(390)
        controls_scroll.setMaximumWidth(520)
        controls = QWidget()
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(6, 6, 8, 6)
        controls_layout.setSpacing(12)

        model_card = QFrame()
        model_card.setObjectName("Card")
        model_layout = QVBoxLayout(model_card)
        model_layout.setContentsMargins(16, 16, 16, 16)
        model_layout.addWidget(SectionHeader(
            "Response surrogate",
            "Fit an uncertainty-aware model before ranking new experiment scenarios.",
        ))
        form = QFormLayout()
        self.response_combo = QComboBox()
        self.method_combo = QComboBox()
        self.method_combo.addItems(self.service.method_names())
        self.method_combo.setCurrentText("Gaussian Process")
        self.confidence_spin = QDoubleSpinBox()
        self.confidence_spin.setRange(80.0, 99.0)
        self.confidence_spin.setValue(95.0)
        self.confidence_spin.setSuffix(" %")
        form.addRow("Response", self.response_combo)
        form.addRow("Method", self.method_combo)
        form.addRow("Confidence", self.confidence_spin)
        model_layout.addLayout(form)
        self.predictor_list = QListWidget()
        self.predictor_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.predictor_list.setMinimumHeight(210)
        model_layout.addWidget(self.predictor_list)
        self.include_review = QCheckBox("Include records marked for review")
        model_layout.addWidget(self.include_review)
        controls_layout.addWidget(model_card)

        acquisition_card = QFrame()
        acquisition_card.setObjectName("Card")
        acquisition_form = QFormLayout(acquisition_card)
        acquisition_form.setContentsMargins(16, 16, 16, 16)
        self.strategy_combo = QComboBox()
        self.strategy_combo.addItems(self.service.acquisition_names())
        self.strategy_combo.setCurrentText("Balanced exploration")
        self.direction_combo = QComboBox()
        self.direction_combo.addItems(["Maximize", "Minimize"])
        self.candidate_spin = QSpinBox()
        self.candidate_spin.setRange(100, 20000)
        self.candidate_spin.setValue(1200)
        self.candidate_spin.setSingleStep(100)
        self.recommendation_spin = QSpinBox()
        self.recommendation_spin.setRange(1, 50)
        self.recommendation_spin.setValue(10)
        self.diversity_spin = QDoubleSpinBox()
        self.diversity_spin.setRange(0.0, 0.90)
        self.diversity_spin.setValue(0.30)
        self.diversity_spin.setSingleStep(0.05)
        self.exploration_spin = QDoubleSpinBox()
        self.exploration_spin.setRange(0.0, 1000.0)
        self.exploration_spin.setDecimals(4)
        self.exploration_spin.setValue(0.01)
        self.bound_spin = QDoubleSpinBox()
        self.bound_spin.setRange(0.0, 10.0)
        self.bound_spin.setValue(2.0)
        self.bound_spin.setSingleStep(0.25)
        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, 999999)
        self.seed_spin.setValue(42)
        acquisition_form.addRow("Strategy", self.strategy_combo)
        acquisition_form.addRow("Direction", self.direction_combo)
        acquisition_form.addRow("Candidate pool", self.candidate_spin)
        acquisition_form.addRow("Recommendations", self.recommendation_spin)
        acquisition_form.addRow("Diversity weight", self.diversity_spin)
        acquisition_form.addRow("Improvement margin", self.exploration_spin)
        acquisition_form.addRow("Confidence-bound weight", self.bound_spin)
        acquisition_form.addRow("Random seed", self.seed_spin)
        controls_layout.addWidget(acquisition_card)

        variables_card = QFrame()
        variables_card.setObjectName("Card")
        variables_layout = QVBoxLayout(variables_card)
        variables_layout.setContentsMargins(16, 16, 16, 16)
        variables_layout.addWidget(SectionHeader(
            "Experiment variables",
            "Candidate scenarios remain within the selected numeric bounds.",
        ))
        variable_actions = QHBoxLayout()
        standard = QPushButton("Use standard variables")
        standard.clicked.connect(self.reset_variable_bounds)
        selected = QPushButton("Use selected numeric inputs")
        selected.clicked.connect(self.use_selected_predictors_as_variables)
        variable_actions.addWidget(standard)
        variable_actions.addWidget(selected)
        variables_layout.addLayout(variable_actions)
        self.variable_table = QTableWidget(0, 3)
        self.variable_table.setHorizontalHeaderLabels(["Field", "Lower", "Upper"])
        self.variable_table.verticalHeader().setVisible(False)
        self.variable_table.setMinimumHeight(185)
        variables_layout.addWidget(self.variable_table)
        self.binder_closure = QCheckBox("Maintain FA + GGBS + SF = 100%")
        self.binder_closure.setChecked(True)
        variables_layout.addWidget(self.binder_closure)
        controls_layout.addWidget(variables_card)

        run_button = QPushButton("Recommend experiments")
        run_button.setObjectName("PrimaryButton")
        run_button.clicked.connect(self.run_recommendation)
        controls_layout.addWidget(run_button)
        controls_layout.addStretch()
        controls_scroll.setWidget(controls)
        splitter.addWidget(controls_scroll)

        results = QWidget()
        results_layout = QVBoxLayout(results)
        results_layout.setContentsMargins(0, 0, 0, 0)
        results_layout.setSpacing(10)
        metrics = QHBoxLayout()
        self.recommendation_pill = ValuePill()
        self.pool_pill = ValuePill()
        self.acquisition_pill = ValuePill()
        self.uncertainty_pill = ValuePill()
        self.reliability_pill = ValuePill()
        for label, pill in (
            ("Recommendations", self.recommendation_pill),
            ("Eligible candidates", self.pool_pill),
            ("Top acquisition", self.acquisition_pill),
            ("Median uncertainty", self.uncertainty_pill),
            ("Best reliability", self.reliability_pill),
        ):
            metrics.addWidget(QLabel(label))
            metrics.addWidget(pill)
        metrics.addStretch()
        results_layout.addLayout(metrics)

        self.detail_label = QLabel(
            "Select a response, inputs, variable bounds, and an acquisition strategy."
        )
        self.detail_label.setObjectName("Muted")
        self.detail_label.setWordWrap(True)
        results_layout.addWidget(self.detail_label)

        actions = QHBoxLayout()
        self.x_axis_combo = QComboBox()
        self.y_axis_combo = QComboBox()
        self.x_axis_combo.currentIndexChanged.connect(self.refresh_acquisition_figure)
        self.y_axis_combo.currentIndexChanged.connect(self.refresh_acquisition_figure)
        actions.addWidget(QLabel("Map X"))
        actions.addWidget(self.x_axis_combo)
        actions.addWidget(QLabel("Map Y"))
        actions.addWidget(self.y_axis_combo)
        actions.addStretch()
        export_results = QPushButton("Export recommendations")
        export_results.clicked.connect(self.export_recommendations)
        export_plan = QPushButton("Export experiment plan")
        export_plan.clicked.connect(self.export_experiment_plan)
        export_figure = QPushButton("Export figure")
        export_figure.clicked.connect(self.export_active_figure)
        save_run = QPushButton("Save run")
        save_run.clicked.connect(self.save_run)
        actions.addWidget(export_results)
        actions.addWidget(export_plan)
        actions.addWidget(export_figure)
        actions.addWidget(save_run)
        results_layout.addLayout(actions)

        self.result_tabs = QTabWidget()
        recommendations_widget = QWidget()
        recommendations_layout = QVBoxLayout(recommendations_widget)
        self.recommendation_model = DataFrameModel()
        recommendation_table = QTableView()
        recommendation_table.setModel(self.recommendation_model)
        recommendation_table.setSortingEnabled(True)
        recommendation_table.setAlternatingRowColors(True)
        recommendation_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        recommendations_layout.addWidget(recommendation_table)
        self.result_tabs.addTab(recommendations_widget, "Recommendations")

        acquisition_widget = QWidget()
        acquisition_layout = QVBoxLayout(acquisition_widget)
        self.acquisition_canvas = FigureCanvasQTAgg(
            Figure(figsize=(7, 7), constrained_layout=True)
        )
        self.acquisition_canvas.setMinimumSize(620, 620)
        acquisition_layout.addWidget(self.acquisition_canvas)
        self.result_tabs.addTab(acquisition_widget, "Acquisition map")

        profile_widget = QWidget()
        profile_layout = QVBoxLayout(profile_widget)
        self.profile_canvas = FigureCanvasQTAgg(
            Figure(figsize=(7, 7), constrained_layout=True)
        )
        self.profile_canvas.setMinimumSize(620, 620)
        profile_layout.addWidget(self.profile_canvas)
        self.result_tabs.addTab(profile_widget, "Priority profile")

        surrogate_widget = QWidget()
        surrogate_layout = QVBoxLayout(surrogate_widget)
        self.surrogate_model = DataFrameModel()
        surrogate_table = QTableView()
        surrogate_table.setModel(self.surrogate_model)
        surrogate_table.setAlternatingRowColors(True)
        surrogate_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        surrogate_layout.addWidget(surrogate_table)
        self.result_tabs.addTab(surrogate_widget, "Surrogate validation")

        results_layout.addWidget(self.result_tabs, 1)
        splitter.addWidget(results)
        splitter.setSizes([430, 1050])
        page_layout.addWidget(splitter)
        return page

    # ------------------------------------------------------------------
    # Closed-loop update tab
    # ------------------------------------------------------------------
    def _update_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.addWidget(SectionHeader(
            "Completed experiment update",
            "Append compatible measured records and compare the active surrogate before and after the update.",
        ))
        self.update_detail = QLabel(
            "Load or create an active-learning run first. Exported experiment plans keep measured response fields blank."
        )
        self.update_detail.setObjectName("Muted")
        self.update_detail.setWordWrap(True)
        card_layout.addWidget(self.update_detail)
        buttons = QHBoxLayout()
        append_button = QPushButton("Append completed CSV")
        append_button.clicked.connect(self.append_completed_csv)
        evaluate_button = QPushButton("Evaluate model update")
        evaluate_button.setObjectName("PrimaryButton")
        evaluate_button.clicked.connect(self.evaluate_update)
        export_button = QPushButton("Export comparison")
        export_button.clicked.connect(self.export_update_comparison)
        export_figure = QPushButton("Export figure")
        export_figure.clicked.connect(lambda: self._export_figure(
            self.figures.get("update"), "GPC_DTwin_Active_Learning_Update.png"
        ))
        buttons.addWidget(append_button)
        buttons.addWidget(evaluate_button)
        buttons.addWidget(export_button)
        buttons.addWidget(export_figure)
        buttons.addStretch()
        card_layout.addLayout(buttons)
        layout.addWidget(card)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.update_model = DataFrameModel()
        update_table = QTableView()
        update_table.setModel(self.update_model)
        update_table.setAlternatingRowColors(True)
        update_table.setSortingEnabled(True)
        splitter.addWidget(update_table)
        self.update_canvas = FigureCanvasQTAgg(Figure(figsize=(7, 7), constrained_layout=True))
        self.update_canvas.setMinimumSize(620, 620)
        splitter.addWidget(self.update_canvas)
        splitter.setSizes([620, 760])
        layout.addWidget(splitter, 1)
        return page

    # ------------------------------------------------------------------
    # Library tab
    # ------------------------------------------------------------------
    def _library_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        toolbar = QHBoxLayout()
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh_library)
        load = QPushButton("Load selected")
        load.clicked.connect(self.load_selected_run)
        delete = QPushButton("Delete selected")
        delete.clicked.connect(self.delete_selected_run)
        open_folder = QPushButton("Open storage folder")
        open_folder.clicked.connect(self.open_storage_folder)
        toolbar.addWidget(refresh)
        toolbar.addWidget(load)
        toolbar.addWidget(delete)
        toolbar.addWidget(open_folder)
        toolbar.addStretch()
        layout.addLayout(toolbar)
        self.library_model = DataFrameModel()
        self.library_table = QTableView()
        self.library_table.setModel(self.library_model)
        self.library_table.setSortingEnabled(True)
        self.library_table.setAlternatingRowColors(True)
        self.library_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.library_table, 1)
        return page

    # ------------------------------------------------------------------
    # State and configuration helpers
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        dataframe = self.context.dataframe
        current_response = self.response_combo.currentData()
        self.response_combo.blockSignals(True)
        self.response_combo.clear()
        for response in MODEL_RESPONSE_COLUMNS:
            if response in dataframe.columns and pd.to_numeric(
                dataframe[response], errors="coerce"
            ).notna().sum() >= 8:
                self.response_combo.addItem(COLUMN_LABELS.get(response, response), response)
        if current_response:
            index = self.response_combo.findData(current_response)
            if index >= 0:
                self.response_combo.setCurrentIndex(index)
        self.response_combo.blockSignals(False)

        selected_predictors = set(self.checked_predictors())
        self.predictor_list.clear()
        for predictor in MODEL_PREDICTOR_COLUMNS:
            if predictor not in dataframe.columns:
                continue
            item = QListWidgetItem(COLUMN_LABELS.get(predictor, predictor))
            item.setData(Qt.ItemDataRole.UserRole, predictor)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            checked = predictor in selected_predictors or (
                not selected_predictors and predictor in MODEL_DEFAULT_PREDICTORS
            )
            item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
            self.predictor_list.addItem(item)
        if self.variable_table.rowCount() == 0:
            self.reset_variable_bounds()

    def checked_predictors(self) -> list[str]:
        return [
            self.predictor_list.item(index).data(Qt.ItemDataRole.UserRole)
            for index in range(self.predictor_list.count())
            if self.predictor_list.item(index).checkState() == Qt.CheckState.Checked
        ]

    def _set_predictor_checked(self, field: str) -> None:
        for index in range(self.predictor_list.count()):
            item = self.predictor_list.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == field:
                item.setCheckState(Qt.CheckState.Checked)
                return

    def _fill_variable_table(self, fields: list[str]) -> None:
        bounds = self.service.default_bounds(self.context.dataframe, fields)
        self.variable_table.setRowCount(0)
        for field in fields:
            if field not in MODEL_NUMERIC_PREDICTORS or field not in bounds:
                continue
            row = self.variable_table.rowCount()
            self.variable_table.insertRow(row)
            field_item = QTableWidgetItem(COLUMN_LABELS.get(field, field))
            field_item.setData(Qt.ItemDataRole.UserRole, field)
            self.variable_table.setItem(row, 0, field_item)
            self.variable_table.setItem(row, 1, QTableWidgetItem(f"{bounds[field][0]:.8g}"))
            self.variable_table.setItem(row, 2, QTableWidgetItem(f"{bounds[field][1]:.8g}"))
            self._set_predictor_checked(field)
        self.variable_table.resizeColumnsToContents()

    def reset_variable_bounds(self) -> None:
        fields = [
            "fa_percent_numeric", "ggbs_percent_numeric", "sf_percent_numeric", "aas_b_ratio"
        ]
        self._fill_variable_table(fields)
        self.binder_closure.setChecked(True)

    def use_selected_predictors_as_variables(self) -> None:
        fields = [field for field in self.checked_predictors() if field in MODEL_NUMERIC_PREDICTORS]
        if not fields:
            QMessageBox.information(self, "Experiment variables", "Select numeric predictors first.")
            return
        self._fill_variable_table(fields)
        composition_selected = all(field in fields for field in self.service.COMPOSITION_FIELDS)
        self.binder_closure.setChecked(composition_selected)

    def variables(self) -> list[LearningVariable]:
        variables: list[LearningVariable] = []
        for row in range(self.variable_table.rowCount()):
            field_item = self.variable_table.item(row, 0)
            lower_item = self.variable_table.item(row, 1)
            upper_item = self.variable_table.item(row, 2)
            if not field_item or not lower_item or not upper_item:
                continue
            field = field_item.data(Qt.ItemDataRole.UserRole)
            variables.append(LearningVariable(
                field=field,
                lower=float(lower_item.text()),
                upper=float(upper_item.text()),
            ))
        return variables

    # ------------------------------------------------------------------
    # Recommendation actions
    # ------------------------------------------------------------------
    def run_recommendation(self) -> None:
        response = self.response_combo.currentData()
        if not response:
            QMessageBox.warning(self, "Response required", "Select a response with usable records.")
            return
        try:
            run = self.service.recommend(
                dataframe=self.context.dataframe,
                response=response,
                predictors=self.checked_predictors(),
                variables=self.variables(),
                method=self.method_combo.currentText(),
                strategy=self.strategy_combo.currentText(),
                direction=self.direction_combo.currentText(),
                confidence_percent=self.confidence_spin.value(),
                candidate_count=self.candidate_spin.value(),
                recommendation_count=self.recommendation_spin.value(),
                binder_closure=self.binder_closure.isChecked(),
                diversity_weight=self.diversity_spin.value(),
                exploration_parameter=self.exploration_spin.value(),
                confidence_bound_weight=self.bound_spin.value(),
                include_review_records=self.include_review.isChecked(),
                seed=self.seed_spin.value(),
            )
        except Exception as error:
            QMessageBox.critical(self, "Recommendation failed", str(error))
            return
        self.set_run(run)
        self.context.message.emit(
            f"Generated {len(run.recommendations)} experiment recommendations."
        )

    def set_run(self, run: ActiveLearningRunResult) -> None:
        self.current_run = run
        self.current_update = None
        self.recommendation_model.set_dataframe(run.recommendations)
        self.surrogate_model.set_dataframe(run.surrogate_summary)
        self.update_model.set_dataframe(pd.DataFrame())
        self.update_detail.setText(
            f"Active baseline: {COLUMN_LABELS.get(run.response, run.response)} · "
            f"{run.method} · {run.strategy}."
        )
        self.recommendation_pill.set_value(len(run.recommendations), "success")
        self.pool_pill.set_value(len(run.candidate_pool))
        top = float(run.recommendations["acquisition_score"].max())
        median_uncertainty = float(
            run.recommendations["normalized_uncertainty_percent"].median()
        )
        reliability = str(run.recommendations.iloc[0]["reliability_class"])
        self.acquisition_pill.set_value(f"{top:.3f}")
        self.uncertainty_pill.set_value(f"{median_uncertainty:.1f}%")
        self.reliability_pill.set_value(reliability, "success" if reliability in {"A", "B"} else "warning")
        self.detail_label.setText(
            f"{run.method} used {run.artifact['metadata'].get('observations', 0)} records. "
            f"Candidates were ranked with {run.strategy.lower()} and diversity-aware selection."
        )

        fields = [item.field for item in run.variables]
        self.x_axis_combo.blockSignals(True)
        self.y_axis_combo.blockSignals(True)
        self.x_axis_combo.clear()
        self.y_axis_combo.clear()
        for field in fields:
            label = COLUMN_LABELS.get(field, field)
            self.x_axis_combo.addItem(label, field)
            self.y_axis_combo.addItem(label, field)
        if len(fields) > 1:
            self.y_axis_combo.setCurrentIndex(1)
        self.x_axis_combo.blockSignals(False)
        self.y_axis_combo.blockSignals(False)
        self.refresh_acquisition_figure()

        profile = self.service.recommendation_figure(run)
        self.figures["profile"] = profile
        self.profile_canvas = self._replace_canvas(self.profile_canvas, profile)
        self.tabs.setCurrentIndex(0)

    def refresh_acquisition_figure(self) -> None:
        if self.current_run is None:
            return
        x_field = self.x_axis_combo.currentData()
        y_field = self.y_axis_combo.currentData()
        try:
            figure = self.service.acquisition_figure(self.current_run, x_field, y_field)
        except Exception:
            return
        self.figures["acquisition"] = figure
        self.acquisition_canvas = self._replace_canvas(self.acquisition_canvas, figure)

    @staticmethod
    def _replace_canvas(old: FigureCanvasQTAgg, figure: Figure) -> FigureCanvasQTAgg:
        parent = old.parentWidget()
        layout = parent.layout() if parent else None
        index = layout.indexOf(old) if layout else -1
        if layout:
            layout.removeWidget(old)
        old.setParent(None)
        old.deleteLater()
        canvas = FigureCanvasQTAgg(figure)
        canvas.setMinimumSize(620, 620)
        if layout:
            layout.insertWidget(index if index >= 0 else layout.count(), canvas, 1)
        canvas.draw_idle()
        return canvas

    # ------------------------------------------------------------------
    # Export, storage, and update actions
    # ------------------------------------------------------------------
    def export_recommendations(self) -> None:
        if self.current_run is None:
            QMessageBox.information(self, "Nothing to export", "Generate recommendations first.")
            return
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(
            self, "Export recommendations",
            str(EXPORT_DIR / "GPC_DTwin_Experiment_Recommendations.csv"),
            "CSV data (*.csv)",
        )
        if path:
            destination = Path(path).with_suffix(".csv")
            self.current_run.recommendations.to_csv(
                destination, index=False, encoding="utf-8-sig"
            )
            self.current_run.surrogate_summary.to_csv(
                destination.with_name(destination.stem + "_surrogate.csv"),
                index=False, encoding="utf-8-sig",
            )
            self.context.message.emit(f"Recommendations exported to {destination.name}.")

    def export_experiment_plan(self) -> None:
        if self.current_run is None:
            QMessageBox.information(self, "Nothing to export", "Generate recommendations first.")
            return
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(
            self, "Export compatible experiment plan",
            str(EXPORT_DIR / "GPC_DTwin_Experiment_Plan.csv"),
            "CSV data (*.csv)",
        )
        if path:
            destination = Path(path).with_suffix(".csv")
            self.service.experiment_plan(self.current_run).to_csv(
                destination, index=False, encoding="utf-8-sig"
            )
            self.context.message.emit(f"Experiment plan exported to {destination.name}.")

    def export_active_figure(self) -> None:
        key = "acquisition" if self.result_tabs.currentIndex() == 1 else "profile"
        self._export_figure(
            self.figures.get(key),
            "GPC_DTwin_Active_Learning_Acquisition.png"
            if key == "acquisition" else "GPC_DTwin_Active_Learning_Profile.png",
        )

    def _export_figure(self, figure: Figure | None, default_name: str) -> None:
        if figure is None:
            QMessageBox.information(self, "Nothing to export", "Generate the figure first.")
            return
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        path, selected_filter = QFileDialog.getSaveFileName(
            self, "Export square figure", str(EXPORT_DIR / default_name),
            "PNG image (*.png);;PDF document (*.pdf);;SVG image (*.svg);;TIFF image (*.tiff *.tif)",
        )
        if not path:
            return
        destination = Path(path)
        if not destination.suffix:
            suffix = ".pdf" if "PDF" in selected_filter else ".svg" if "SVG" in selected_filter else ".tiff" if "TIFF" in selected_filter else ".png"
            destination = destination.with_suffix(suffix)
        try:
            save_square_figure(figure, destination)
            self.context.message.emit(
                f"Square 600 dpi figure exported to {destination.name}."
            )
        except Exception as error:
            QMessageBox.critical(self, "Figure export failed", str(error))

    def save_run(self) -> None:
        if self.current_run is None:
            QMessageBox.information(self, "No active run", "Generate recommendations first.")
            return
        try:
            path = self.service.save_result(self.current_run, ACTIVE_LEARNING_DIR)
        except Exception as error:
            QMessageBox.warning(self, "Save failed", str(error))
            return
        self.refresh_library()
        self.context.message.emit(f"Active-learning run saved as {path.name}.")

    def append_completed_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Append completed experiment records", "", "CSV data (*.csv)"
        )
        if not path:
            return
        answer = QMessageBox.question(
            self, "Append records?",
            "The selected compatible records will be added to the active dataset. Existing records remain unchanged. Continue?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            appended = self.context.append_csv(path)
        except Exception as error:
            QMessageBox.critical(self, "Append failed", str(error))
            return
        self.update_detail.setText(
            f"Appended {appended} completed records. Evaluate the active model update when ready."
        )

    def evaluate_update(self) -> None:
        if self.current_run is None:
            QMessageBox.information(self, "No active baseline", "Create or load a run first.")
            return
        try:
            update = self.service.compare_update(self.current_run, self.context.dataframe)
        except Exception as error:
            QMessageBox.critical(self, "Update comparison failed", str(error))
            return
        self.current_update = update
        self.update_model.set_dataframe(update.comparison)
        figure = self.service.update_figure(update)
        self.figures["update"] = figure
        self.update_canvas = self._replace_canvas(self.update_canvas, figure)
        summary = update.updated_summary.iloc[0]
        self.update_detail.setText(
            f"Compared {int(summary['observations_before'])} baseline records with "
            f"{int(summary['observations_after'])} current records."
        )
        self.tabs.setCurrentIndex(1)
        self.context.message.emit("Model-update comparison completed.")

    def export_update_comparison(self) -> None:
        if self.current_update is None:
            QMessageBox.information(self, "Nothing to export", "Evaluate an update first.")
            return
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(
            self, "Export model-update comparison",
            str(EXPORT_DIR / "GPC_DTwin_Active_Learning_Update.csv"),
            "CSV data (*.csv)",
        )
        if path:
            destination = Path(path).with_suffix(".csv")
            self.current_update.comparison.to_csv(
                destination, index=False, encoding="utf-8-sig"
            )
            self.current_update.updated_summary.to_csv(
                destination.with_name(destination.stem + "_summary.csv"),
                index=False, encoding="utf-8-sig",
            )
            self.context.message.emit(f"Update comparison exported to {destination.name}.")

    def refresh_library(self) -> None:
        self.library_model.set_dataframe(self.service.list_saved_results(ACTIVE_LEARNING_DIR))

    def _selected_library_path(self) -> Path | None:
        selection = self.library_table.selectionModel().selectedRows()
        if not selection:
            return None
        row = selection[0].row()
        dataframe = self.library_model.dataframe
        if row >= len(dataframe) or "artifact_path" not in dataframe.columns:
            return None
        return Path(str(dataframe.iloc[row]["artifact_path"]))

    def load_selected_run(self) -> None:
        path = self._selected_library_path()
        if path is None:
            QMessageBox.information(self, "Run library", "Select a saved run first.")
            return
        try:
            run = self.service.load_result(path)
        except Exception as error:
            QMessageBox.warning(self, "Load failed", str(error))
            return
        self.set_run(run)
        self.context.message.emit(f"Loaded {path.name}.")

    def delete_selected_run(self) -> None:
        path = self._selected_library_path()
        if path is None:
            QMessageBox.information(self, "Run library", "Select a saved run first.")
            return
        answer = QMessageBox.question(self, "Delete saved run?", f"Delete {path.name}?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.delete_result(path)
        except Exception as error:
            QMessageBox.warning(self, "Delete failed", str(error))
            return
        self.refresh_library()
        self.context.message.emit(f"Deleted {path.name}.")

    def open_storage_folder(self) -> None:
        ACTIVE_LEARNING_DIR.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(ACTIVE_LEARNING_DIR.resolve())))
