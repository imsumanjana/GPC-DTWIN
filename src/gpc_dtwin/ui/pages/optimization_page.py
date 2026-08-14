from __future__ import annotations

from pathlib import Path

import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDoubleSpinBox,
    QFileDialog, QFormLayout, QFrame, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QMessageBox, QPushButton, QScrollArea, QSpinBox, QSplitter, QStyle,
    QTableView, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from gpc_dtwin.columns import (
    BINDER_PERCENT_COLUMNS, COLUMN_LABELS, MODEL_DEFAULT_PREDICTORS, MODEL_NUMERIC_PREDICTORS,
    MODEL_PREDICTOR_COLUMNS, MODEL_RESPONSE_COLUMNS,
)
from gpc_dtwin.ui.export_preview_dialog import open_figure_export_dialog
from gpc_dtwin.paths import EXPORT_DIR, OPTIMIZATION_DIR
from gpc_dtwin.services.digital_twin_service import DigitalTwinService
from gpc_dtwin.services.optimization_service import (
    ConstraintDefinition, InverseDesignResult, ObjectiveDefinition,
    OptimizationRunResult, OptimizationService, TargetDefinition, VariableDefinition,
)
from gpc_dtwin.ui.models import DataFrameModel
from gpc_dtwin.ui.figure_tabs import FigureTabs
from gpc_dtwin.ui.widgets import CompactToolbar, SectionHeader, ValuePill


class OptimizationPage(QWidget):
    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.context = context
        self.service = OptimizationService()
        self.current_optimization: OptimizationRunResult | None = None
        self.current_inverse: InverseDesignResult | None = None
        self.figures: dict[str, Figure] = {}
        self.available_responses: list[str] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 24)
        root.setSpacing(14)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._optimizer_tab(), "Pareto optimizer")
        self.tabs.addTab(self._inverse_tab(), "Inverse design")
        self.tabs.addTab(self._library_tab(), "Run library")
        root.addWidget(self.tabs, 1)

        self.context.data_changed.connect(self.refresh)
        self.refresh()
        self.refresh_library()

    def _optimizer_tab(self) -> QWidget:
        page = QWidget()
        page_layout = QHBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter()

        controls_scroll = QScrollArea()
        controls_scroll.setWidgetResizable(True)
        controls_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        controls_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        controls_scroll.setMinimumWidth(390)
        controls_scroll.setMaximumWidth(500)
        controls = QWidget()
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(6, 6, 8, 6)
        controls_layout.setSpacing(12)

        surrogate_card = QFrame()
        surrogate_card.setObjectName("Card")
        surrogate_layout = QVBoxLayout(surrogate_card)
        surrogate_layout.setContentsMargins(16, 16, 16, 16)
        surrogate_layout.addWidget(SectionHeader(
            "Surrogate configuration",
            "Select the inputs used to estimate every objective and constraint."
        ))
        surrogate_form = QFormLayout()
        self.method_combo = QComboBox()
        self.method_combo.addItems(DigitalTwinService.method_names())
        self.method_combo.setCurrentText("Random Forest")
        self.confidence_spin = QDoubleSpinBox()
        self.confidence_spin.setRange(80.0, 99.0)
        self.confidence_spin.setValue(95.0)
        self.confidence_spin.setSuffix(" %")
        surrogate_form.addRow("Prediction model", self.method_combo)
        surrogate_form.addRow("Confidence", self.confidence_spin)
        surrogate_layout.addLayout(surrogate_form)
        self.predictor_list = QListWidget()
        self.predictor_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.predictor_list.setMinimumHeight(190)
        surrogate_layout.addWidget(self.predictor_list)
        self.include_review = QCheckBox("Include records marked for review")
        surrogate_layout.addWidget(self.include_review)
        controls_layout.addWidget(surrogate_card)

        objectives_card = QFrame()
        objectives_card.setObjectName("Card")
        objectives_layout = QVBoxLayout(objectives_card)
        objectives_layout.setContentsMargins(16, 16, 16, 16)
        objectives_layout.addWidget(SectionHeader(
            "Objectives", "Enable one or more responses and assign their priorities."
        ))
        self.objective_table = QTableWidget(4, 4)
        self.objective_table.setHorizontalHeaderLabels(["Use", "Response", "Direction", "Weight"])
        self.objective_table.verticalHeader().setVisible(False)
        self.objective_table.setMinimumHeight(176)
        objectives_layout.addWidget(self.objective_table)
        controls_layout.addWidget(objectives_card)

        constraints_card = QFrame()
        constraints_card.setObjectName("Card")
        constraints_layout = QVBoxLayout(constraints_card)
        constraints_layout.setContentsMargins(16, 16, 16, 16)
        constraints_layout.addWidget(SectionHeader(
            "Constraints", "Optional minimum or maximum response requirements."
        ))
        self.constraint_table = QTableWidget(3, 4)
        self.constraint_table.setHorizontalHeaderLabels(["Use", "Response", "Relation", "Threshold"])
        self.constraint_table.verticalHeader().setVisible(False)
        self.constraint_table.setMinimumHeight(144)
        constraints_layout.addWidget(self.constraint_table)
        controls_layout.addWidget(constraints_card)

        variables_card = QFrame()
        variables_card.setObjectName("Card")
        variables_layout = QVBoxLayout(variables_card)
        variables_layout.setContentsMargins(16, 16, 16, 16)
        variables_layout.addWidget(SectionHeader(
            "Decision variables", "Bounds remain inside the selected material domain."
        ))
        variable_actions = QHBoxLayout()
        reset_variables = QPushButton("Use standard variables")
        reset_variables.clicked.connect(self.reset_variable_bounds)
        selected_variables = QPushButton("Use selected numeric inputs")
        selected_variables.clicked.connect(self.use_selected_predictors_as_variables)
        variable_actions.addWidget(reset_variables)
        variable_actions.addWidget(selected_variables)
        variables_layout.addLayout(variable_actions)
        self.variable_table = QTableWidget(0, 3)
        self.variable_table.setHorizontalHeaderLabels(["Field", "Lower", "Upper"])
        self.variable_table.verticalHeader().setVisible(False)
        self.variable_table.setMinimumHeight(170)
        variables_layout.addWidget(self.variable_table)
        self.binder_closure = QCheckBox("Maintain FA + GGBS + SF = 100%")
        self.binder_closure.setChecked(True)
        variables_layout.addWidget(self.binder_closure)
        controls_layout.addWidget(variables_card)

        search_card = QFrame()
        search_card.setObjectName("Card")
        search_layout = QFormLayout(search_card)
        search_layout.setContentsMargins(16, 16, 16, 16)
        self.population_spin = QSpinBox()
        self.population_spin.setRange(16, 300)
        self.population_spin.setValue(64)
        self.population_spin.setSingleStep(8)
        self.generations_spin = QSpinBox()
        self.generations_spin.setRange(1, 150)
        self.generations_spin.setValue(20)
        self.uncertainty_spin = QDoubleSpinBox()
        self.uncertainty_spin.setRange(0.0, 3.0)
        self.uncertainty_spin.setSingleStep(0.1)
        self.uncertainty_spin.setValue(0.5)
        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, 999999)
        self.seed_spin.setValue(42)
        search_layout.addRow("Population", self.population_spin)
        search_layout.addRow("Generations", self.generations_spin)
        search_layout.addRow("Uncertainty penalty", self.uncertainty_spin)
        search_layout.addRow("Random seed", self.seed_spin)
        controls_layout.addWidget(search_card)

        run_button = QPushButton("Run Pareto search")
        run_button.setObjectName("PrimaryButton")
        run_button.clicked.connect(self.run_optimization)
        controls_layout.addWidget(run_button)
        controls_layout.addStretch()
        controls_scroll.setWidget(controls)
        splitter.addWidget(controls_scroll)

        results = QWidget()
        results_layout = QVBoxLayout(results)
        results_layout.setContentsMargins(0, 0, 0, 0)
        results_layout.setSpacing(10)
        self.pareto_count_pill = ValuePill()
        self.feasible_pill = ValuePill()
        self.evaluated_pill = ValuePill()
        self.best_reliability_pill = ValuePill()
        self.best_score_pill = ValuePill()
        toolbar = CompactToolbar()
        for label, pill in (
            ("Pareto solutions", self.pareto_count_pill),
            ("Feasible population", self.feasible_pill),
            ("Candidates evaluated", self.evaluated_pill),
            ("Best reliability", self.best_reliability_pill),
            ("Compromise score", self.best_score_pill),
        ):
            toolbar.add_metric(label, pill)
        toolbar.add_stretch()
        toolbar.add_action(
            QStyle.StandardPixmap.SP_DialogSaveButton,
            "Export Pareto results",
            self.export_optimization,
        )
        toolbar.add_action(
            QStyle.StandardPixmap.SP_FileDialogDetailedView,
            "Export Pareto figure",
            self.export_optimization_figure,
        )
        toolbar.add_action(
            QStyle.StandardPixmap.SP_DriveHDIcon,
            "Save optimization run",
            self.save_optimization,
        )
        toolbar.finalize()
        results_layout.addWidget(toolbar)

        self.optimization_detail = QLabel("Configure objectives, bounds, and constraints, then run the search.")
        self.optimization_detail.setObjectName("Muted")
        self.optimization_detail.setWordWrap(True)
        results_layout.addWidget(self.optimization_detail)

        self.optimization_results_tabs = QTabWidget()
        self.optimization_results_tabs.currentChanged.connect(self._optimizer_result_tab_changed)

        front_widget = QWidget()
        front_layout = QHBoxLayout(front_widget)
        front_splitter = QSplitter()
        self.pareto_model = DataFrameModel()
        self.pareto_table = QTableView()
        self.pareto_table.setModel(self.pareto_model)
        self.pareto_table.setSortingEnabled(True)
        self.pareto_table.setAlternatingRowColors(True)
        front_splitter.addWidget(self.pareto_table)
        self.pareto_canvas = FigureCanvasQTAgg(Figure(figsize=(7, 5), constrained_layout=True))
        front_splitter.addWidget(self.pareto_canvas)
        front_splitter.setSizes([610, 700])
        front_layout.addWidget(front_splitter)
        self.optimization_results_tabs.addTab(front_widget, "Pareto front")

        profiles_widget = QWidget()
        profiles_layout = QVBoxLayout(profiles_widget)
        self.parallel_canvas = FigureCanvasQTAgg(Figure(figsize=(9, 5), constrained_layout=True))
        profiles_layout.addWidget(self.parallel_canvas)
        self.optimization_results_tabs.addTab(profiles_widget, "Solution profiles")

        population_widget = QWidget()
        population_layout = QVBoxLayout(population_widget)
        self.population_model = DataFrameModel()
        population_table = QTableView()
        population_table.setModel(self.population_model)
        population_table.setSortingEnabled(True)
        population_table.setAlternatingRowColors(True)
        population_layout.addWidget(population_table)
        self.optimization_results_tabs.addTab(population_widget, "Final population")

        surrogate_widget = QWidget()
        surrogate_layout = QVBoxLayout(surrogate_widget)
        self.surrogate_model = DataFrameModel()
        surrogate_table = QTableView()
        surrogate_table.setModel(self.surrogate_model)
        surrogate_table.setSortingEnabled(True)
        surrogate_table.setAlternatingRowColors(True)
        surrogate_layout.addWidget(surrogate_table)
        self.optimization_results_tabs.addTab(surrogate_widget, "Surrogate validation")

        results_layout.addWidget(self.optimization_results_tabs, 1)
        splitter.addWidget(results)
        splitter.setSizes([430, 1100])
        page_layout.addWidget(splitter)
        return page

    def _inverse_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        configuration = QFrame()
        configuration.setObjectName("Card")
        configuration_layout = QVBoxLayout(configuration)
        configuration_layout.setContentsMargins(18, 16, 18, 16)
        configuration_layout.addWidget(SectionHeader(
            "Performance targets",
            "The surrogate inputs, decision-variable bounds, method, and closure rule are taken from the Pareto optimizer configuration."
        ))
        self.target_table = QTableWidget(4, 5)
        self.target_table.setHorizontalHeaderLabels(["Use", "Response", "Relation", "Target", "Weight"])
        self.target_table.verticalHeader().setVisible(False)
        self.target_table.setMaximumHeight(185)
        configuration_layout.addWidget(self.target_table)

        inverse_options = QHBoxLayout()
        self.candidate_count_spin = QSpinBox()
        self.candidate_count_spin.setRange(200, 50000)
        self.candidate_count_spin.setValue(2500)
        self.candidate_count_spin.setSingleStep(500)
        self.recommendation_count_spin = QSpinBox()
        self.recommendation_count_spin.setRange(3, 100)
        self.recommendation_count_spin.setValue(20)
        inverse_options.addWidget(QLabel("Candidates"))
        inverse_options.addWidget(self.candidate_count_spin)
        inverse_options.addWidget(QLabel("Alternatives"))
        inverse_options.addWidget(self.recommendation_count_spin)
        inverse_options.addStretch()
        run_inverse = QPushButton("Find matching scenarios")
        run_inverse.setObjectName("PrimaryButton")
        run_inverse.clicked.connect(self.run_inverse_design)
        inverse_options.addWidget(run_inverse)
        configuration_layout.addLayout(inverse_options)
        layout.addWidget(configuration)

        self.inverse_evaluated_pill = ValuePill()
        self.inverse_satisfaction_pill = ValuePill()
        self.inverse_reliability_pill = ValuePill()
        self.inverse_loss_pill = ValuePill()
        toolbar = CompactToolbar()
        for label, pill in (
            ("Candidates evaluated", self.inverse_evaluated_pill),
            ("Targets satisfied", self.inverse_satisfaction_pill),
            ("Best reliability", self.inverse_reliability_pill),
            ("Design loss", self.inverse_loss_pill),
        ):
            toolbar.add_metric(label, pill)
        toolbar.add_stretch()
        toolbar.add_action(
            QStyle.StandardPixmap.SP_DialogSaveButton,
            "Export inverse-design recommendations",
            self.export_inverse,
        )
        toolbar.add_action(
            QStyle.StandardPixmap.SP_FileDialogDetailedView,
            "Export inverse-design figure",
            self.export_inverse_figure,
        )
        toolbar.add_action(
            QStyle.StandardPixmap.SP_DriveHDIcon,
            "Save inverse-design run",
            self.save_inverse,
        )
        toolbar.finalize()
        layout.addWidget(toolbar)

        self.inverse_detail = QLabel("Set one or more targets to rank compatible material scenarios.")
        self.inverse_detail.setObjectName("Muted")
        self.inverse_detail.setWordWrap(True)
        layout.addWidget(self.inverse_detail)

        splitter = QSplitter()
        self.inverse_model = DataFrameModel()
        inverse_table = QTableView()
        inverse_table.setModel(self.inverse_model)
        inverse_table.setSortingEnabled(True)
        inverse_table.setAlternatingRowColors(True)
        splitter.addWidget(inverse_table)
        self.inverse_figure_tabs = FigureTabs(minimum_canvas_size=(620, 540))
        splitter.addWidget(self.inverse_figure_tabs)
        splitter.setSizes([720, 700])
        layout.addWidget(splitter, 1)
        return page

    def _library_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)
        header = QHBoxLayout()
        header.addWidget(SectionHeader(
            "Saved runs",
            "Reload optimization and inverse-design results with their fitted surrogates."
        ), 1)
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh_library)
        open_folder = QPushButton("Open folder")
        open_folder.clicked.connect(self.open_library_folder)
        header.addWidget(refresh_button)
        header.addWidget(open_folder)
        layout.addLayout(header)

        self.library_model = DataFrameModel()
        self.library_table = QTableView()
        self.library_table.setModel(self.library_model)
        self.library_table.setSortingEnabled(True)
        self.library_table.setAlternatingRowColors(True)
        self.library_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.library_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        layout.addWidget(self.library_table, 1)

        actions = QHBoxLayout()
        load_button = QPushButton("Load selected")
        load_button.setObjectName("PrimaryButton")
        load_button.clicked.connect(self.load_selected_run)
        delete_button = QPushButton("Delete selected")
        delete_button.clicked.connect(self.delete_selected_run)
        actions.addStretch()
        actions.addWidget(load_button)
        actions.addWidget(delete_button)
        layout.addLayout(actions)
        return page

    @staticmethod
    def _set_canvas(current: FigureCanvasQTAgg, figure: Figure) -> FigureCanvasQTAgg:
        """Reuse the existing Qt canvas instead of deleting native widgets mid-session.

        Replacing a canvas with ``deleteLater`` while Qt still has queued paint or
        event-filter callbacks can produce a native access violation on Windows.
        Rebinding the figure keeps the widget and its chart-style button stable.
        """
        current.setUpdatesEnabled(False)
        current.figure = figure
        figure.set_canvas(current)
        current.setUpdatesEnabled(True)
        current.draw_idle()
        return current

    @staticmethod
    def _enabled_checkbox(checked: bool = False) -> QCheckBox:
        checkbox = QCheckBox()
        checkbox.setChecked(checked)
        checkbox.setStyleSheet("margin-left: 12px;")
        return checkbox

    @staticmethod
    def _weight_spin(value: float = 1.0) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(0.05, 100.0)
        spin.setDecimals(2)
        spin.setValue(value)
        return spin

    @staticmethod
    def _value_spin(value: float = 0.0) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(-1000000.0, 1000000.0)
        spin.setDecimals(4)
        spin.setValue(value)
        return spin

    def _response_combo(self, responses: list[str], selected: str | None = None) -> QComboBox:
        combo = QComboBox()
        for field in responses:
            combo.addItem(COLUMN_LABELS.get(field, field), field)
        if selected:
            index = combo.findData(selected)
            if index >= 0:
                combo.setCurrentIndex(index)
        return combo

    def _populate_config_tables(self, responses: list[str]) -> None:
        objective_defaults = [
            ("compressive_strength_mpa", "Maximize", 1.0),
            ("flexural_strength_mpa", "Maximize", 0.7),
            ("strength_loss_percent_derived", "Minimize", 0.8),
            ("slump_mm", "Maximize", 0.4),
        ]
        for row, (response, direction, weight) in enumerate(objective_defaults):
            enabled = response in responses and row < 2
            checkbox = self._enabled_checkbox(enabled)
            combo = self._response_combo(responses, response)
            direction_combo = QComboBox()
            direction_combo.addItems(["Maximize", "Minimize"])
            direction_combo.setCurrentText(direction)
            self.objective_table.setCellWidget(row, 0, checkbox)
            self.objective_table.setCellWidget(row, 1, combo)
            self.objective_table.setCellWidget(row, 2, direction_combo)
            self.objective_table.setCellWidget(row, 3, self._weight_spin(weight))

        constraint_defaults = [
            ("compressive_strength_mpa", "At least", 30.0),
            ("slump_mm", "At least", 40.0),
            ("strength_loss_percent_derived", "At most", 15.0),
        ]
        for row, (response, relation, threshold) in enumerate(constraint_defaults):
            checkbox = self._enabled_checkbox(False)
            combo = self._response_combo(responses, response)
            relation_combo = QComboBox()
            relation_combo.addItems(["At least", "At most"])
            relation_combo.setCurrentText(relation)
            self.constraint_table.setCellWidget(row, 0, checkbox)
            self.constraint_table.setCellWidget(row, 1, combo)
            self.constraint_table.setCellWidget(row, 2, relation_combo)
            self.constraint_table.setCellWidget(row, 3, self._value_spin(threshold))

        target_defaults = [
            ("compressive_strength_mpa", "At least", 40.0, 1.0),
            ("flexural_strength_mpa", "At least", 3.0, 0.8),
            ("slump_mm", "At least", 50.0, 0.5),
            ("strength_loss_percent_derived", "At most", 10.0, 0.8),
        ]
        for row, (response, relation, target, weight) in enumerate(target_defaults):
            checkbox = self._enabled_checkbox(response in responses and row == 0)
            combo = self._response_combo(responses, response)
            relation_combo = QComboBox()
            relation_combo.addItems(["At least", "At most", "Closest"])
            relation_combo.setCurrentText(relation)
            self.target_table.setCellWidget(row, 0, checkbox)
            self.target_table.setCellWidget(row, 1, combo)
            self.target_table.setCellWidget(row, 2, relation_combo)
            self.target_table.setCellWidget(row, 3, self._value_spin(target))
            self.target_table.setCellWidget(row, 4, self._weight_spin(weight))

    def _selected_predictors(self) -> list[str]:
        selected: list[str] = []
        for index in range(self.predictor_list.count()):
            item = self.predictor_list.item(index)
            if item.checkState() == Qt.CheckState.Checked:
                selected.append(str(item.data(Qt.ItemDataRole.UserRole)))
        return selected

    def _objectives(self) -> list[ObjectiveDefinition]:
        items: list[ObjectiveDefinition] = []
        for row in range(self.objective_table.rowCount()):
            use = self.objective_table.cellWidget(row, 0)
            if not use or not use.isChecked():
                continue
            response = self.objective_table.cellWidget(row, 1).currentData()
            direction = self.objective_table.cellWidget(row, 2).currentText()
            weight = self.objective_table.cellWidget(row, 3).value()
            items.append(ObjectiveDefinition(str(response), direction, float(weight)))
        return items

    def _constraints(self) -> list[ConstraintDefinition]:
        items: list[ConstraintDefinition] = []
        for row in range(self.constraint_table.rowCount()):
            use = self.constraint_table.cellWidget(row, 0)
            if not use or not use.isChecked():
                continue
            response = self.constraint_table.cellWidget(row, 1).currentData()
            relation = self.constraint_table.cellWidget(row, 2).currentText()
            threshold = self.constraint_table.cellWidget(row, 3).value()
            items.append(ConstraintDefinition(str(response), relation, float(threshold)))
        return items

    def _targets(self) -> list[TargetDefinition]:
        items: list[TargetDefinition] = []
        for row in range(self.target_table.rowCount()):
            use = self.target_table.cellWidget(row, 0)
            if not use or not use.isChecked():
                continue
            response = self.target_table.cellWidget(row, 1).currentData()
            relation = self.target_table.cellWidget(row, 2).currentText()
            target = self.target_table.cellWidget(row, 3).value()
            weight = self.target_table.cellWidget(row, 4).value()
            items.append(TargetDefinition(str(response), relation, float(target), float(weight)))
        return items

    def _variables(self) -> list[VariableDefinition]:
        items: list[VariableDefinition] = []
        for row in range(self.variable_table.rowCount()):
            field_item = self.variable_table.item(row, 0)
            lower_item = self.variable_table.item(row, 1)
            upper_item = self.variable_table.item(row, 2)
            if not field_item or not lower_item or not upper_item:
                continue
            field = str(field_item.data(Qt.ItemDataRole.UserRole) or field_item.text())
            try:
                lower = float(lower_item.text())
                upper = float(upper_item.text())
            except ValueError as error:
                raise ValueError(f"Invalid bounds for {field}.") from error
            items.append(VariableDefinition(field, lower, upper))
        return items

    def reset_variable_bounds(self) -> None:
        standard = [*BINDER_PERCENT_COLUMNS, "aas_b_ratio"]
        self._set_variable_rows(standard)
        self.binder_closure.setChecked(True)

    def use_selected_predictors_as_variables(self) -> None:
        fields = [field for field in self._selected_predictors() if field in MODEL_NUMERIC_PREDICTORS]
        if not fields:
            QMessageBox.information(self, "Decision variables", "No numeric surrogate inputs are selected.")
            return
        self._set_variable_rows(fields)
        if not all(field in fields for field in self.service.COMPOSITION_FIELDS):
            self.binder_closure.setChecked(False)

    def _set_variable_rows(self, fields: list[str]) -> None:
        bounds = self.service.default_bounds(self.context.dataframe, fields)
        self.variable_table.setRowCount(0)
        for field in fields:
            if field not in bounds:
                continue
            lower, upper = bounds[field]
            row = self.variable_table.rowCount()
            self.variable_table.insertRow(row)
            name_item = QTableWidgetItem(COLUMN_LABELS.get(field, field))
            name_item.setData(Qt.ItemDataRole.UserRole, field)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.variable_table.setItem(row, 0, name_item)
            self.variable_table.setItem(row, 1, QTableWidgetItem(f"{lower:.6g}"))
            self.variable_table.setItem(row, 2, QTableWidgetItem(f"{upper:.6g}"))
        self.variable_table.resizeColumnsToContents()

    def refresh(self) -> None:
        dataframe = self.context.dataframe
        responses = [
            field for field in MODEL_RESPONSE_COLUMNS
            if field in dataframe.columns and pd.to_numeric(dataframe[field], errors="coerce").notna().sum() >= 8
        ]
        existing_predictors = self._selected_predictors() if self.predictor_list.count() else []
        self.predictor_list.clear()
        for field in MODEL_PREDICTOR_COLUMNS:
            if field not in dataframe.columns:
                continue
            item = QListWidgetItem(COLUMN_LABELS.get(field, field))
            item.setData(Qt.ItemDataRole.UserRole, field)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            checked = field in existing_predictors or (
                not existing_predictors and field in MODEL_DEFAULT_PREDICTORS
            )
            item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
            self.predictor_list.addItem(item)
        if responses != self.available_responses:
            self.available_responses = list(responses)
            self._populate_config_tables(responses)
        if self.variable_table.rowCount() == 0:
            self.reset_variable_bounds()

    def run_optimization(self) -> None:
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            result = self.service.optimize(
                dataframe=self.context.dataframe,
                objectives=self._objectives(),
                constraints=self._constraints(),
                variables=self._variables(),
                predictors=self._selected_predictors(),
                method=self.method_combo.currentText(),
                confidence_percent=self.confidence_spin.value(),
                population_size=self.population_spin.value(),
                generations=self.generations_spin.value(),
                uncertainty_weight=self.uncertainty_spin.value(),
                binder_closure=self.binder_closure.isChecked(),
                include_review_records=self.include_review.isChecked(),
                seed=self.seed_spin.value(),
            )
            self.current_optimization = result
            self._display_optimization(result)
            self.context.message.emit(
                f"Pareto search completed with {len(result.pareto_solutions)} solutions."
            )
            self._warn_surrogate_exclusions(result.surrogate_summary, "Optimization")
        except Exception as error:
            QMessageBox.critical(self, "Optimization failed", str(error))
        finally:
            QApplication.restoreOverrideCursor()

    def _warn_surrogate_exclusions(self, summary: pd.DataFrame, workflow: str) -> None:
        if summary.empty or "dropped_predictors" not in summary.columns:
            return
        fields: list[str] = []
        for value in summary["dropped_predictors"].astype(str):
            fields.extend(part.strip() for part in value.split(",") if part.strip())
        unique = list(dict.fromkeys(fields))
        if not unique:
            return
        QMessageBox.warning(
            self,
            "Parameters excluded",
            f"{workflow} completed after automatically excluding response-incompatible "
            "parameters without usable values:\n\n"
            + "\n".join(
                f"• {COLUMN_LABELS.get(field, field)}" for field in unique
            )
            + "\n\nReview the surrogate-validation table for response-specific details.",
        )

    def _display_optimization(self, result: OptimizationRunResult) -> None:
        self.pareto_model.set_dataframe(result.pareto_solutions)
        self.population_model.set_dataframe(result.final_population)
        self.surrogate_model.set_dataframe(result.surrogate_summary)
        pareto_figure = self.service.pareto_figure(result)
        parallel_figure = self.service.parallel_figure(result)
        self.figures["pareto"] = pareto_figure
        self.figures["parallel"] = parallel_figure
        self.pareto_canvas = self._set_canvas(self.pareto_canvas, pareto_figure)
        self.parallel_canvas = self._set_canvas(self.parallel_canvas, parallel_figure)
        feasible = int(result.final_population["feasible"].sum())
        self.pareto_count_pill.set_value(len(result.pareto_solutions))
        self.feasible_pill.set_value(f"{feasible}/{len(result.final_population)}")
        self.evaluated_pill.set_value(result.candidates_evaluated)
        if not result.pareto_solutions.empty:
            best = result.pareto_solutions.iloc[0]
            reliability = str(best["reliability_class"])
            tone = "success" if reliability == "A" else "warning" if reliability in {"B", "C"} else "danger"
            self.best_reliability_pill.set_value(reliability, tone)
            self.best_score_pill.set_value(f"{float(best['compromise_score']):.3f}")
        dropped = []
        if "dropped_predictors" in result.surrogate_summary.columns:
            dropped = [
                value for value in result.surrogate_summary["dropped_predictors"].astype(str)
                if value.strip()
            ]
        adaptation = (
            " Response-specific blank inputs were omitted automatically; review the surrogate table."
            if dropped else ""
        )
        self.optimization_detail.setText(
            f"Constraint-aware NSGA-II · {result.method} surrogates · {result.population_size} candidates per generation · "
            f"{result.generations} generations · {result.confidence_percent:.0f}% intervals. "
            "Review surrogate validation and reliability before selecting a scenario." + adaptation
        )

    def run_inverse_design(self) -> None:
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            result = self.service.inverse_design(
                dataframe=self.context.dataframe,
                targets=self._targets(),
                variables=self._variables(),
                predictors=self._selected_predictors(),
                method=self.method_combo.currentText(),
                confidence_percent=self.confidence_spin.value(),
                candidate_count=self.candidate_count_spin.value(),
                recommendation_count=self.recommendation_count_spin.value(),
                uncertainty_weight=self.uncertainty_spin.value(),
                binder_closure=self.binder_closure.isChecked(),
                include_review_records=self.include_review.isChecked(),
                seed=self.seed_spin.value(),
            )
            self.current_inverse = result
            self._display_inverse(result)
            self.context.message.emit(
                f"Inverse design ranked {len(result.recommendations)} alternatives."
            )
            self._warn_surrogate_exclusions(result.surrogate_summary, "Inverse design")
        except Exception as error:
            QMessageBox.critical(self, "Inverse design failed", str(error))
        finally:
            QApplication.restoreOverrideCursor()

    def _display_inverse(self, result: InverseDesignResult) -> None:
        self.inverse_model.set_dataframe(result.recommendations)
        figures = self.service.inverse_figures(result)
        self.figures["inverse"] = next(iter(figures.values()))
        self.inverse_figure_tabs.set_figures(figures)
        self.inverse_evaluated_pill.set_value(result.candidates_evaluated)
        if not result.recommendations.empty:
            best = result.recommendations.iloc[0]
            self.inverse_satisfaction_pill.set_value(
                f"{int(best['targets_satisfied'])}/{int(best['target_count'])}"
            )
            reliability = str(best["reliability_class"])
            tone = "success" if reliability == "A" else "warning" if reliability in {"B", "C"} else "danger"
            self.inverse_reliability_pill.set_value(reliability, tone)
            self.inverse_loss_pill.set_value(f"{float(best['design_loss']):.4f}")
        self.inverse_detail.setText(
            f"{result.candidates_evaluated} scenarios evaluated with {result.method} surrogates. "
            "Lower design loss indicates closer target matching after uncertainty and range penalties."
        )

    def _optimizer_result_tab_changed(self, index: int) -> None:
        if index == 0 and self.current_optimization:
            self.pareto_canvas.draw_idle()
        elif index == 1 and self.current_optimization:
            self.parallel_canvas.draw_idle()

    def export_optimization(self) -> None:
        if self.current_optimization is None:
            QMessageBox.information(self, "Export", "Run or load an optimization first.")
            return
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Pareto solutions", str(EXPORT_DIR / "GPC_DTwin_Pareto_Solutions.csv"),
            "CSV data (*.csv)"
        )
        if not path:
            return
        destination = Path(path).with_suffix(".csv")
        self.current_optimization.pareto_solutions.to_csv(destination, index=False)
        self.current_optimization.final_population.to_csv(
            destination.with_name(destination.stem + "_population.csv"), index=False
        )
        self.current_optimization.surrogate_summary.to_csv(
            destination.with_name(destination.stem + "_surrogates.csv"), index=False
        )
        self.context.message.emit(f"Optimization results exported to {destination.name}.")

    def export_inverse(self) -> None:
        if self.current_inverse is None:
            QMessageBox.information(self, "Export", "Run or load an inverse design first.")
            return
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(
            self, "Export recommendations", str(EXPORT_DIR / "GPC_DTwin_Inverse_Design.csv"),
            "CSV data (*.csv)"
        )
        if not path:
            return
        destination = Path(path).with_suffix(".csv")
        self.current_inverse.recommendations.to_csv(destination, index=False)
        self.current_inverse.surrogate_summary.to_csv(
            destination.with_name(destination.stem + "_surrogates.csv"), index=False
        )
        self.context.message.emit(f"Inverse-design results exported to {destination.name}.")

    @staticmethod
    def _save_figure(figure: Figure | None, parent: QWidget, default_name: str) -> None:
        if figure is None:
            QMessageBox.information(parent, "Nothing to export", "Generate a figure first.")
            return
        open_figure_export_dialog(
            parent, figure, suggested_name=str(EXPORT_DIR / default_name)
        )

    def export_optimization_figure(self) -> None:
        key = "parallel" if self.optimization_results_tabs.currentIndex() == 1 else "pareto"
        self._save_figure(self.figures.get(key), self, f"GPC_DTwin_{key}.png")

    def export_inverse_figure(self) -> None:
        self._save_figure(
            self.inverse_figure_tabs.current_figure(), self, "GPC_DTwin_Inverse_Design.png"
        )

    def save_optimization(self) -> None:
        if self.current_optimization is None:
            QMessageBox.information(self, "Save run", "Run or load an optimization first.")
            return
        path = self.service.save_result(self.current_optimization, OPTIMIZATION_DIR)
        self.refresh_library()
        self.context.message.emit(f"Optimization run saved as {path.name}.")

    def save_inverse(self) -> None:
        if self.current_inverse is None:
            QMessageBox.information(self, "Save run", "Run or load an inverse design first.")
            return
        path = self.service.save_result(self.current_inverse, OPTIMIZATION_DIR)
        self.refresh_library()
        self.context.message.emit(f"Inverse-design run saved as {path.name}.")

    def refresh_library(self) -> None:
        self.library_model.set_dataframe(self.service.list_saved_results(OPTIMIZATION_DIR))

    def _selected_library_path(self) -> Path | None:
        indexes = self.library_table.selectionModel().selectedRows()
        if not indexes:
            QMessageBox.information(self, "Run library", "Select a saved run.")
            return None
        row = indexes[0].row()
        dataframe = self.library_model.dataframe
        if row >= len(dataframe):
            return None
        return Path(str(dataframe.iloc[row]["artifact_path"]))

    def load_selected_run(self) -> None:
        path = self._selected_library_path()
        if path is None:
            return
        try:
            result = self.service.load_result(path)
            if isinstance(result, OptimizationRunResult):
                self.current_optimization = result
                self._display_optimization(result)
                self.tabs.setCurrentIndex(0)
            else:
                self.current_inverse = result
                self._display_inverse(result)
                self.tabs.setCurrentIndex(1)
            self.context.message.emit(f"Loaded {path.name}.")
        except Exception as error:
            QMessageBox.critical(self, "Load failed", str(error))

    def delete_selected_run(self) -> None:
        path = self._selected_library_path()
        if path is None:
            return
        answer = QMessageBox.question(
            self, "Delete saved run?", f"Delete {path.name} and its exported run files?"
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.delete_result(path)
            self.refresh_library()
            self.context.message.emit(f"Deleted {path.name}.")
        except Exception as error:
            QMessageBox.critical(self, "Delete failed", str(error))

    @staticmethod
    def open_library_folder() -> None:
        OPTIMIZATION_DIR.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(OPTIMIZATION_DIR)))
