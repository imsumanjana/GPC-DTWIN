from __future__ import annotations

from pathlib import Path

import pandas as pd
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog,
    QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMessageBox, QPushButton, QScrollArea, QSpinBox,
    QSplitter, QStyle, QTabWidget, QTableView, QVBoxLayout, QWidget,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from gpc_dtwin.columns import COLUMN_LABELS
from gpc_dtwin.ui.export_preview_dialog import open_figure_export_dialog
from gpc_dtwin.paths import DURABILITY_DIR, EXPORT_DIR, NDT_DIR
from gpc_dtwin.services.digital_twin_service import DigitalTwinService
from gpc_dtwin.services.ndt_durability_service import (
    DURABILITY_DEFAULT_PREDICTORS, NDTDurabilityService,
)
from gpc_dtwin.ui.models import DataFrameModel
from gpc_dtwin.ui.scrolling import scrollable_panel
from gpc_dtwin.ui.widgets import CompactToolbar, SectionHeader, ValuePill


class NDTDurabilityPage(QWidget):
    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.context = context
        self.service = NDTDurabilityService()
        self.ndt_result = None
        self.active_ndt_artifact = None
        self.profile_result = None
        self.durability_result = None
        self.active_durability_artifact = None
        self.ndt_figure: Figure | None = None
        self.profile_figure: Figure | None = None
        self.sweep_figure: Figure | None = None
        self.sweep_data = pd.DataFrame()

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 24)
        root.setSpacing(14)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._ndt_fusion_tab(), "NDT fusion")
        self.tabs.addTab(self._ndt_estimate_tab(), "NDT estimate")
        self.tabs.addTab(self._durability_profile_tab(), "Durability profile")
        self.tabs.addTab(self._durability_estimator_tab(), "Durability estimator")
        root.addWidget(self.tabs, 1)

        self.context.data_changed.connect(self.refresh)
        self.refresh()

    # ------------------------------------------------------------------
    # NDT fusion
    # ------------------------------------------------------------------
    def _ndt_fusion_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        splitter = QSplitter()

        controls = QFrame()
        controls.setObjectName("Card")
        controls.setMinimumWidth(330)
        controls.setMaximumWidth(430)
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(16, 16, 16, 16)
        controls_layout.addWidget(SectionHeader(
            "Reference matching",
            "Select the destructive-strength condition used to match NDT readings by mix identity."
        ))
        form = QFormLayout()
        self.ndt_group_combo = QComboBox()
        self.ndt_age_spin = QDoubleSpinBox()
        self.ndt_age_spin.setRange(0.0, 10000.0)
        self.ndt_age_spin.setDecimals(1)
        self.ndt_age_spin.setValue(28.0)
        self.ndt_age_spin.setSpecialValueText("Any")
        self.ndt_age_spin.setSuffix(" days")
        self.ndt_curing_edit = QLineEdit("Ambient")
        self.ndt_algorithm_combo = QComboBox()
        self.ndt_algorithm_combo.addItems(self.service.ndt_algorithm_names())
        self.ndt_review_check = QCheckBox("Include records marked for review")
        self.ndt_review_check.setChecked(True)
        form.addRow("Reference group", self.ndt_group_combo)
        form.addRow("Reference age", self.ndt_age_spin)
        form.addRow("Curing contains", self.ndt_curing_edit)
        form.addRow("Algorithm", self.ndt_algorithm_combo)
        controls_layout.addLayout(form)
        controls_layout.addWidget(self.ndt_review_check)

        run = QPushButton("Compare NDT input sets")
        run.setObjectName("PrimaryButton")
        run.clicked.connect(self.run_ndt_fusion)
        save = QPushButton("Save best NDT model")
        save.clicked.connect(self.save_best_ndt_model)
        controls_layout.addWidget(run)
        controls_layout.addWidget(save)
        controls_layout.addSpacing(6)
        self.ndt_reference_note = QLabel("No comparison is active.")
        self.ndt_reference_note.setObjectName("Muted")
        self.ndt_reference_note.setWordWrap(True)
        controls_layout.addWidget(self.ndt_reference_note)
        controls_layout.addStretch()
        controls_scroll = scrollable_panel(controls, minimum_width=350)
        controls_scroll.setMaximumWidth(470)
        splitter.addWidget(controls_scroll)

        results = QWidget()
        results_layout = QVBoxLayout(results)
        results_layout.setContentsMargins(0, 0, 0, 0)
        results_layout.setSpacing(10)

        self.ndt_best_pill = ValuePill()
        self.ndt_records_pill = ValuePill()
        self.ndt_rmse_pill = ValuePill()
        self.ndt_mae_pill = ValuePill()
        self.ndt_r2_pill = ValuePill()
        toolbar = CompactToolbar()
        for label, pill in (
            ("Best input set", self.ndt_best_pill),
            ("Matched mixes", self.ndt_records_pill),
            ("RMSE", self.ndt_rmse_pill),
            ("MAE", self.ndt_mae_pill),
            ("R²", self.ndt_r2_pill),
        ):
            toolbar.add_metric(label, pill)
        toolbar.add_stretch()
        toolbar.add_label("View")
        self.ndt_view_combo = QComboBox()
        self.ndt_view_combo.addItems([
            "Observed vs estimated", "Residuals", "Input-set RMSE"
        ])
        self.ndt_view_combo.currentTextChanged.connect(self.render_ndt_figure)
        toolbar.add_widget(self.ndt_view_combo)
        toolbar.add_label("Input set")
        self.ndt_feature_combo = QComboBox()
        self.ndt_feature_combo.currentTextChanged.connect(self.render_ndt_figure)
        toolbar.add_widget(self.ndt_feature_combo)
        toolbar.add_action(
            QStyle.StandardPixmap.SP_DialogSaveButton,
            "Export NDT results",
            self.export_ndt_results,
        )
        toolbar.add_action(
            QStyle.StandardPixmap.SP_FileDialogDetailedView,
            "Export NDT figure",
            lambda: self.export_figure(self.ndt_figure, "ndt_fusion.png"),
        )
        toolbar.finalize()
        results_layout.addWidget(toolbar)

        chart_card = QFrame()
        chart_card.setObjectName("Card")
        chart_layout = QVBoxLayout(chart_card)
        self.ndt_canvas = FigureCanvasQTAgg(Figure(figsize=(8, 4.6), constrained_layout=True))
        chart_layout.addWidget(self.ndt_canvas, 1)
        results_layout.addWidget(chart_card, 3)

        tables = QSplitter(Qt.Orientation.Horizontal)
        self.ndt_ranking_model = DataFrameModel()
        ranking = QTableView()
        ranking.setModel(self.ndt_ranking_model)
        ranking.setSortingEnabled(True)
        ranking.setAlternatingRowColors(True)
        ranking.horizontalHeader().setStretchLastSection(True)
        tables.addWidget(ranking)
        self.ndt_prediction_model = DataFrameModel()
        predictions = QTableView()
        predictions.setModel(self.ndt_prediction_model)
        predictions.setSortingEnabled(True)
        predictions.setAlternatingRowColors(True)
        predictions.horizontalHeader().setStretchLastSection(True)
        tables.addWidget(predictions)
        tables.setSizes([520, 620])
        results_layout.addWidget(tables, 2)
        splitter.addWidget(results)
        splitter.setSizes([360, 1120])
        layout.addWidget(splitter)
        return page

    def _ndt_estimate_tab(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        controls = QFrame()
        controls.setObjectName("Card")
        controls.setMinimumWidth(390)
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(18, 18, 18, 18)
        controls_layout.addWidget(SectionHeader(
            "NDT model",
            "Use the active best model or select a saved model from the local library."
        ))
        self.ndt_library_combo = QComboBox()
        controls_layout.addWidget(self.ndt_library_combo)
        library_buttons = QHBoxLayout()
        load = QPushButton("Load selected")
        load.clicked.connect(self.load_selected_ndt_model)
        delete = QPushButton("Delete selected")
        delete.setObjectName("DangerButton")
        delete.clicked.connect(self.delete_selected_ndt_model)
        library_buttons.addWidget(load)
        library_buttons.addWidget(delete)
        controls_layout.addLayout(library_buttons)
        self.ndt_model_note = QLabel("Run NDT fusion or load a saved model.")
        self.ndt_model_note.setObjectName("Muted")
        self.ndt_model_note.setWordWrap(True)
        controls_layout.addWidget(self.ndt_model_note)
        controls_layout.addSpacing(8)
        controls_layout.addWidget(SectionHeader(
            "Scenario inputs",
            "Only inputs required by the active model are used."
        ))
        form = QFormLayout()
        self.ndt_input_spins: dict[str, QDoubleSpinBox] = {}
        ndt_fields = [
            ("upv_m_s", 0.0, 20000.0, 1, 3500.0),
            ("rebound_estimated_strength_mpa", 0.0, 250.0, 3, 30.0),
            ("fa_percent_numeric", 0.0, 100.0, 2, 20.0),
            ("ggbs_percent_numeric", 0.0, 100.0, 2, 70.0),
            ("sf_percent_numeric", 0.0, 100.0, 2, 10.0),
        ]
        for field, minimum, maximum, decimals, value in ndt_fields:
            spin = QDoubleSpinBox()
            spin.setRange(minimum, maximum)
            spin.setDecimals(decimals)
            spin.setValue(value)
            self.ndt_input_spins[field] = spin
            form.addRow(COLUMN_LABELS.get(field, field), spin)
        controls_layout.addLayout(form)
        estimate = QPushButton("Estimate compressive strength")
        estimate.setObjectName("PrimaryButton")
        estimate.clicked.connect(self.estimate_ndt_scenario)
        controls_layout.addWidget(estimate)
        controls_layout.addStretch()
        controls_scroll = scrollable_panel(controls, minimum_width=390)
        controls_scroll.setMaximumWidth(480)
        layout.addWidget(controls_scroll)

        result_card = QFrame()
        result_card.setObjectName("Card")
        result_layout = QVBoxLayout(result_card)
        result_layout.setContentsMargins(26, 24, 26, 24)
        result_layout.addWidget(SectionHeader(
            "Estimate",
            "The reliability class reflects validation error, completeness, and input-range support."
        ))
        result_metrics = QHBoxLayout()
        self.ndt_estimate_pill = ValuePill("—")
        self.ndt_reliability_pill = ValuePill("—")
        self.ndt_estimate_set_pill = ValuePill("—")
        for label, pill in (
            ("Compressive strength", self.ndt_estimate_pill),
            ("Reliability", self.ndt_reliability_pill),
            ("Input set", self.ndt_estimate_set_pill),
        ):
            block = QVBoxLayout()
            heading = QLabel(label)
            heading.setObjectName("Muted")
            block.addWidget(heading)
            block.addWidget(pill)
            result_metrics.addLayout(block)
        result_metrics.addStretch()
        result_layout.addLayout(result_metrics)
        self.ndt_estimate_note = QLabel("No estimate is active.")
        self.ndt_estimate_note.setObjectName("Muted")
        self.ndt_estimate_note.setWordWrap(True)
        result_layout.addWidget(self.ndt_estimate_note)
        result_layout.addStretch()
        layout.addWidget(result_card, 1)
        return page

    # ------------------------------------------------------------------
    # Durability profile
    # ------------------------------------------------------------------
    def _durability_profile_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        splitter = QSplitter()

        controls = QFrame()
        controls.setObjectName("Card")
        controls.setMinimumWidth(330)
        controls.setMaximumWidth(430)
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(16, 16, 16, 16)
        controls_layout.addWidget(SectionHeader(
            "Screening score",
            "Balance strength retention and mass stability using transparent, adjustable weights."
        ))
        form = QFormLayout()
        self.strength_weight_spin = QDoubleSpinBox()
        self.strength_weight_spin.setRange(0.0, 100.0)
        self.strength_weight_spin.setValue(80.0)
        self.strength_weight_spin.setSuffix(" %")
        self.mass_weight_spin = QDoubleSpinBox()
        self.mass_weight_spin.setRange(0.0, 100.0)
        self.mass_weight_spin.setValue(20.0)
        self.mass_weight_spin.setSuffix(" %")
        self.mass_penalty_spin = QDoubleSpinBox()
        self.mass_penalty_spin.setRange(0.0, 100.0)
        self.mass_penalty_spin.setDecimals(1)
        self.mass_penalty_spin.setValue(10.0)
        self.mass_penalty_spin.setSuffix(" points / 1%")
        self.profile_review_check = QCheckBox("Include records marked for review")
        form.addRow("Strength-retention weight", self.strength_weight_spin)
        form.addRow("Mass-stability weight", self.mass_weight_spin)
        form.addRow("Mass-change penalty", self.mass_penalty_spin)
        controls_layout.addLayout(form)
        controls_layout.addWidget(self.profile_review_check)
        calculate = QPushButton("Calculate profile")
        calculate.setObjectName("PrimaryButton")
        calculate.clicked.connect(self.run_durability_profile)
        controls_layout.addWidget(calculate)
        self.profile_formula = QLabel(
            "Score = normalized strength weight × retained strength + normalized mass weight × "
            "max(0, 100 − penalty × |mass change|)."
        )
        self.profile_formula.setObjectName("Muted")
        self.profile_formula.setWordWrap(True)
        controls_layout.addWidget(self.profile_formula)
        controls_layout.addStretch()
        controls_scroll = scrollable_panel(controls, minimum_width=350)
        controls_scroll.setMaximumWidth(470)
        splitter.addWidget(controls_scroll)

        results = QWidget()
        results_layout = QVBoxLayout(results)
        results_layout.setContentsMargins(0, 0, 0, 0)
        results_layout.setSpacing(10)
        self.profile_records_pill = ValuePill()
        self.profile_best_pill = ValuePill()
        self.profile_score_pill = ValuePill()
        self.profile_retention_pill = ValuePill()
        self.profile_loss_pill = ValuePill()
        toolbar = CompactToolbar()
        for label, pill in (
            ("Exposure records", self.profile_records_pill),
            ("Top mix", self.profile_best_pill),
            ("Top score", self.profile_score_pill),
            ("Mean retention", self.profile_retention_pill),
            ("Maximum loss", self.profile_loss_pill),
        ):
            toolbar.add_metric(label, pill)
        toolbar.add_stretch()
        toolbar.add_label("View")
        self.profile_view_combo = QComboBox()
        self.profile_view_combo.addItems([
            "Durability score", "Initial vs residual strength",
            "Strength-retention heatmap", "Mass-change heatmap",
        ])
        self.profile_view_combo.currentTextChanged.connect(self.render_profile_figure)
        toolbar.add_widget(self.profile_view_combo)
        toolbar.add_action(
            QStyle.StandardPixmap.SP_DialogSaveButton,
            "Export durability ranking",
            self.export_profile_ranking,
        )
        toolbar.add_action(
            QStyle.StandardPixmap.SP_FileDialogDetailedView,
            "Export durability-profile figure",
            lambda: self.export_figure(self.profile_figure, "durability_profile.png"),
        )
        toolbar.finalize()
        results_layout.addWidget(toolbar)

        chart_card = QFrame()
        chart_card.setObjectName("Card")
        chart_layout = QVBoxLayout(chart_card)
        self.profile_canvas = FigureCanvasQTAgg(Figure(figsize=(8, 4.7), constrained_layout=True))
        chart_layout.addWidget(self.profile_canvas, 1)
        results_layout.addWidget(chart_card, 3)

        self.profile_model = DataFrameModel()
        table = QTableView()
        table.setModel(self.profile_model)
        table.setSortingEnabled(True)
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setStretchLastSection(True)
        results_layout.addWidget(table, 2)
        splitter.addWidget(results)
        splitter.setSizes([360, 1120])
        layout.addWidget(splitter)
        return page

    # ------------------------------------------------------------------
    # Durability estimator
    # ------------------------------------------------------------------
    def _durability_estimator_tab(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setMinimumWidth(390)
        scroll.setMaximumWidth(470)
        controls = QWidget()
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(4, 4, 10, 4)
        controls_layout.addWidget(SectionHeader(
            "Exposure model",
            "Build an uncertainty-aware estimator from available exposure records."
        ))
        model_card = QFrame()
        model_card.setObjectName("Card")
        model_form = QFormLayout(model_card)
        model_form.setContentsMargins(16, 16, 16, 16)
        self.dur_response_combo = QComboBox()
        for value in self.service.durability_response_names():
            self.dur_response_combo.addItem(COLUMN_LABELS.get(value, value), value)
        self.dur_method_combo = QComboBox()
        self.dur_method_combo.addItems(DigitalTwinService.method_names())
        self.dur_confidence_combo = QComboBox()
        for value in (90.0, 95.0, 99.0):
            self.dur_confidence_combo.addItem(f"{value:.0f}%", value)
        self.dur_confidence_combo.setCurrentIndex(1)
        self.dur_review_check = QCheckBox("Include records marked for review")
        model_form.addRow("Response", self.dur_response_combo)
        model_form.addRow("Method", self.dur_method_combo)
        model_form.addRow("Confidence", self.dur_confidence_combo)
        model_form.addRow("", self.dur_review_check)
        controls_layout.addWidget(model_card)

        controls_layout.addWidget(QLabel("Predictors"))
        self.dur_predictor_list = QListWidget()
        self.dur_predictor_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.dur_predictor_list.setMaximumHeight(190)
        controls_layout.addWidget(self.dur_predictor_list)
        build = QPushButton("Build durability estimator")
        build.setObjectName("PrimaryButton")
        build.clicked.connect(self.build_durability_estimator)
        save = QPushButton("Save active estimator")
        save.clicked.connect(self.save_durability_estimator)
        controls_layout.addWidget(build)
        controls_layout.addWidget(save)

        controls_layout.addWidget(SectionHeader(
            "Saved estimators", "Load or remove an estimator from the local library."
        ))
        self.dur_library_combo = QComboBox()
        controls_layout.addWidget(self.dur_library_combo)
        library_buttons = QHBoxLayout()
        load = QPushButton("Load")
        load.clicked.connect(self.load_selected_durability_model)
        delete = QPushButton("Delete")
        delete.setObjectName("DangerButton")
        delete.clicked.connect(self.delete_selected_durability_model)
        library_buttons.addWidget(load)
        library_buttons.addWidget(delete)
        controls_layout.addLayout(library_buttons)
        controls_layout.addStretch()
        scroll.setWidget(controls)
        layout.addWidget(scroll)

        results = QWidget()
        results_layout = QVBoxLayout(results)
        results_layout.setContentsMargins(0, 0, 0, 0)
        results_layout.setSpacing(10)

        self.dur_records_pill = ValuePill()
        self.dur_rmse_pill = ValuePill()
        self.dur_r2_pill = ValuePill()
        self.dur_coverage_pill = ValuePill()
        self.dur_method_pill = ValuePill()
        metrics_toolbar = CompactToolbar()
        for label, pill in (
            ("Records", self.dur_records_pill),
            ("RMSE", self.dur_rmse_pill),
            ("R²", self.dur_r2_pill),
            ("Coverage", self.dur_coverage_pill),
            ("Method", self.dur_method_pill),
        ):
            metrics_toolbar.add_metric(label, pill)
        metrics_toolbar.add_stretch()
        metrics_toolbar.finalize()
        results_layout.addWidget(metrics_toolbar)

        scenario = QFrame()
        scenario.setObjectName("Card")
        scenario_layout = QVBoxLayout(scenario)
        scenario_layout.addWidget(SectionHeader(
            "Scenario estimate",
            "Inputs not required by the active estimator are ignored."
        ))
        form = QFormLayout()
        self.dur_input_spins: dict[str, QDoubleSpinBox] = {}
        for field, minimum, maximum, decimals, value in (
            ("fa_percent_numeric", 0.0, 100.0, 2, 20.0),
            ("ggbs_percent_numeric", 0.0, 100.0, 2, 70.0),
            ("sf_percent_numeric", 0.0, 100.0, 2, 10.0),
            ("initial_compressive_strength_mpa", 0.0, 300.0, 3, 45.0),
            ("acid_concentration_percent", 0.0, 100.0, 2, 5.0),
            ("acid_exposure_days", 0.0, 36500.0, 1, 28.0),
        ):
            spin = QDoubleSpinBox()
            spin.setRange(minimum, maximum)
            spin.setDecimals(decimals)
            spin.setValue(value)
            self.dur_input_spins[field] = spin
            form.addRow(COLUMN_LABELS.get(field, field), spin)
        self.dur_acid_combo = QComboBox()
        form.addRow(COLUMN_LABELS.get("acid_type", "Exposure medium"), self.dur_acid_combo)
        scenario_layout.addLayout(form)
        estimate = QPushButton("Estimate exposure response")
        estimate.setObjectName("PrimaryButton")
        estimate.clicked.connect(self.estimate_durability_scenario)
        scenario_layout.addWidget(estimate)
        output = QHBoxLayout()
        self.dur_estimate_pill = ValuePill()
        self.dur_interval_pill = ValuePill()
        self.dur_reliability_pill = ValuePill()
        for label, pill in (
            ("Estimate", self.dur_estimate_pill),
            ("Interval", self.dur_interval_pill),
            ("Reliability", self.dur_reliability_pill),
        ):
            output.addWidget(QLabel(label))
            output.addWidget(pill)
        output.addStretch()
        scenario_layout.addLayout(output)
        self.dur_estimate_note = QLabel("Build or load an estimator to calculate a scenario.")
        self.dur_estimate_note.setObjectName("Muted")
        self.dur_estimate_note.setWordWrap(True)
        scenario_layout.addWidget(self.dur_estimate_note)
        results_layout.addWidget(scenario)

        sweep_toolbar = CompactToolbar()
        sweep_toolbar.add_label("Sweep field")
        self.dur_sweep_combo = QComboBox()
        sweep_toolbar.add_widget(self.dur_sweep_combo)
        self.dur_sweep_resolution = QSpinBox()
        self.dur_sweep_resolution.setRange(15, 250)
        self.dur_sweep_resolution.setValue(60)
        sweep_toolbar.add_widget(self.dur_sweep_resolution)
        sweep_toolbar.add_stretch()
        sweep_toolbar.add_action(
            QStyle.StandardPixmap.SP_MediaPlay,
            "Generate response curve",
            self.generate_durability_sweep,
            accent=True,
        )
        sweep_toolbar.add_action(
            QStyle.StandardPixmap.SP_DialogSaveButton,
            "Export response-curve data",
            self.export_sweep_data,
        )
        sweep_toolbar.add_action(
            QStyle.StandardPixmap.SP_FileDialogDetailedView,
            "Export response-curve figure",
            lambda: self.export_figure(self.sweep_figure, "durability_estimator.png"),
        )
        sweep_toolbar.finalize()
        results_layout.addWidget(sweep_toolbar)

        chart_card = QFrame()
        chart_card.setObjectName("Card")
        chart_layout = QVBoxLayout(chart_card)
        self.sweep_canvas = FigureCanvasQTAgg(Figure(figsize=(8, 4.8), constrained_layout=True))
        chart_layout.addWidget(self.sweep_canvas, 1)
        results_layout.addWidget(chart_card, 1)
        layout.addWidget(results, 1)
        return page

    # ------------------------------------------------------------------
    # Refresh and shared utilities
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        groups = self.service.available_reference_groups(self.context.dataframe)
        current = self.ndt_group_combo.currentText()
        self.ndt_group_combo.clear()
        for group in groups:
            self.ndt_group_combo.addItem(group.replace("_", " ").title(), group)
        preferred = "AMBIENT_28D_MECHANICAL"
        target = current or preferred
        index = self.ndt_group_combo.findData(target)
        if index < 0:
            index = self.ndt_group_combo.findText(target)
        self.ndt_group_combo.setCurrentIndex(index if index >= 0 else 0)

        self._populate_predictors()
        media = []
        if "acid_type" in self.context.dataframe.columns:
            media = sorted(
                self.context.dataframe["acid_type"].dropna().astype(str).unique().tolist()
            )
        current_medium = self.dur_acid_combo.currentText()
        self.dur_acid_combo.clear()
        self.dur_acid_combo.addItems(media or ["Exposure"])
        index = self.dur_acid_combo.findText(current_medium)
        if index >= 0:
            self.dur_acid_combo.setCurrentIndex(index)
        self.refresh_ndt_library()
        self.refresh_durability_library()
        self.run_durability_profile(silent=True)

    def _populate_predictors(self) -> None:
        selected = {
            self.dur_predictor_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.dur_predictor_list.count())
            if self.dur_predictor_list.item(i).checkState() == Qt.CheckState.Checked
        }
        self.dur_predictor_list.clear()
        available = [
            column for column in DURABILITY_DEFAULT_PREDICTORS
            if column in self.context.dataframe.columns
        ]
        for column in available:
            item = QListWidgetItem(COLUMN_LABELS.get(column, column))
            item.setData(Qt.ItemDataRole.UserRole, column)
            item.setCheckState(
                Qt.CheckState.Checked
                if not selected or column in selected
                else Qt.CheckState.Unchecked
            )
            self.dur_predictor_list.addItem(item)

    @staticmethod
    def _replace_canvas(old: FigureCanvasQTAgg, figure: Figure) -> FigureCanvasQTAgg:
        parent = old.parentWidget()
        layout = parent.layout()
        index = layout.indexOf(old)
        layout.removeWidget(old)
        old.setParent(None)
        old.deleteLater()
        canvas = FigureCanvasQTAgg(figure)
        layout.insertWidget(index, canvas, 1)
        canvas.draw_idle()
        return canvas

    def export_dataframe(self, dataframe: pd.DataFrame, default_name: str) -> None:
        if dataframe.empty:
            QMessageBox.information(self, "Nothing to export", "The current table is empty.")
            return
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", str(EXPORT_DIR / default_name), "CSV data (*.csv)"
        )
        if path:
            destination = Path(path)
            if destination.suffix.lower() != ".csv":
                destination = destination.with_suffix(".csv")
            dataframe.to_csv(destination, index=False, encoding="utf-8-sig")
            self.context.message.emit(f"Data exported to {destination.name}.")

    def export_figure(self, figure: Figure | None, default_name: str) -> None:
        if figure is None:
            QMessageBox.information(self, "Nothing to export", "Generate a figure first.")
            return
        open_figure_export_dialog(
            self, figure, suggested_name=str(EXPORT_DIR / default_name)
        )

    # ------------------------------------------------------------------
    # NDT actions
    # ------------------------------------------------------------------
    def run_ndt_fusion(self) -> None:
        age = self.ndt_age_spin.value()
        age_value = None if age <= 0 else float(age)
        try:
            result = self.service.compare_ndt_fusion(
                self.context.dataframe,
                reference_group=str(self.ndt_group_combo.currentData() or self.ndt_group_combo.currentText()),
                reference_age_days=age_value,
                curing_keyword=self.ndt_curing_edit.text(),
                algorithm=self.ndt_algorithm_combo.currentText(),
                include_review_records=self.ndt_review_check.isChecked(),
            )
        except Exception as error:
            QMessageBox.warning(self, "NDT fusion unavailable", str(error))
            return
        self.ndt_result = result
        self.active_ndt_artifact = result.artifacts[result.best_feature_set]
        self.ndt_ranking_model.set_dataframe(result.rankings)
        self.ndt_feature_combo.blockSignals(True)
        self.ndt_feature_combo.clear()
        self.ndt_feature_combo.addItems(result.rankings["feature_set"].astype(str).tolist())
        self.ndt_feature_combo.setCurrentText(result.best_feature_set)
        self.ndt_feature_combo.blockSignals(False)
        self.ndt_best_pill.set_value(result.best_feature_set, "success")
        self.ndt_records_pill.set_value(result.observations)
        self.ndt_rmse_pill.set_value(f"{result.best_metrics['rmse']:.3f} MPa")
        self.ndt_mae_pill.set_value(f"{result.best_metrics['mae']:.3f} MPa")
        r2 = result.best_metrics["r2"]
        self.ndt_r2_pill.set_value(f"{r2:.3f}", "success" if r2 >= 0.5 else "warning")
        self.ndt_reference_note.setText(
            f"{result.cv_method}. Reference group: {result.reference_group}; "
            f"reference age: {result.reference_age_days if result.reference_age_days is not None else 'any'}; "
            f"curing filter: {result.curing_keyword or 'none'}."
        )
        self.ndt_model_note.setText(
            f"Active: {result.best_feature_set} · {result.algorithm} · {result.observations} matched mixes."
        )
        self.render_ndt_figure()
        self.refresh_ndt_library()
        self.context.message.emit("NDT fusion comparison completed.")

    def render_ndt_figure(self) -> None:
        if self.ndt_result is None:
            return
        view = self.ndt_view_combo.currentText()
        feature_set = self.ndt_feature_combo.currentText() or self.ndt_result.best_feature_set
        if view == "Residuals":
            figure = self.service.ndt_residual_figure(self.ndt_result, feature_set)
        elif view == "Input-set RMSE":
            figure = self.service.ndt_comparison_figure(self.ndt_result)
        else:
            figure = self.service.ndt_observed_predicted_figure(self.ndt_result, feature_set)
        self.ndt_figure = figure
        self.ndt_canvas = self._replace_canvas(self.ndt_canvas, figure)
        frame = self.ndt_result.predictions[
            self.ndt_result.predictions["feature_set"] == feature_set
        ].copy()
        self.ndt_prediction_model.set_dataframe(frame)

    def export_ndt_results(self) -> None:
        if self.ndt_result is None:
            QMessageBox.information(self, "Nothing to export", "Run NDT fusion first.")
            return
        combined = self.ndt_result.predictions.merge(
            self.ndt_result.rankings,
            on="feature_set", how="left", suffixes=("", "_summary")
        )
        self.export_dataframe(combined, "ndt_fusion_results.csv")

    def save_best_ndt_model(self) -> None:
        if self.active_ndt_artifact is None:
            QMessageBox.information(self, "No active model", "Run NDT fusion first.")
            return
        try:
            path = self.service.save_ndt_artifact(self.active_ndt_artifact, NDT_DIR)
        except Exception as error:
            QMessageBox.warning(self, "Save failed", str(error))
            return
        self.refresh_ndt_library()
        self.context.message.emit(f"NDT model saved as {path.name}.")

    def refresh_ndt_library(self) -> None:
        frame = self.service.list_saved_ndt_models(NDT_DIR)
        current = self.ndt_library_combo.currentData()
        self.ndt_library_combo.clear()
        if self.active_ndt_artifact is not None:
            meta = self.active_ndt_artifact["metadata"]
            self.ndt_library_combo.addItem(
                f"Active · {meta.get('feature_set', '')} · {meta.get('algorithm', '')}",
                "__active__",
            )
        for _, row in frame.iterrows():
            label = (
                f"{row['feature_set']} · {row['algorithm']} · "
                f"RMSE {float(row['rmse']):.3f}"
            )
            self.ndt_library_combo.addItem(label, str(row["artifact_path"]))
        index = self.ndt_library_combo.findData(current)
        if index >= 0:
            self.ndt_library_combo.setCurrentIndex(index)

    def load_selected_ndt_model(self) -> None:
        value = self.ndt_library_combo.currentData()
        if value == "__active__":
            return
        if not value:
            QMessageBox.information(self, "No saved model", "No saved NDT model is selected.")
            return
        try:
            self.active_ndt_artifact = self.service.load_ndt_artifact(value)
        except Exception as error:
            QMessageBox.warning(self, "Load failed", str(error))
            return
        meta = self.active_ndt_artifact["metadata"]
        self.ndt_model_note.setText(
            f"Loaded: {meta.get('feature_set', '')} · {meta.get('algorithm', '')} · "
            f"{meta.get('observations', '')} matched mixes."
        )
        self.refresh_ndt_library()
        self.context.message.emit("NDT model loaded.")

    def delete_selected_ndt_model(self) -> None:
        value = self.ndt_library_combo.currentData()
        if not value or value == "__active__":
            QMessageBox.information(self, "No saved model", "Select a saved NDT model to delete.")
            return
        answer = QMessageBox.question(self, "Delete model?", "Delete the selected NDT model?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.service.delete_artifact(value)
        self.refresh_ndt_library()
        self.context.message.emit("NDT model deleted.")

    def estimate_ndt_scenario(self) -> None:
        if self.active_ndt_artifact is None:
            QMessageBox.information(self, "No active model", "Run NDT fusion or load a saved model.")
            return
        values = {field: spin.value() for field, spin in self.ndt_input_spins.items()}
        try:
            result = self.service.predict_ndt_scenario(self.active_ndt_artifact, values)
        except Exception as error:
            QMessageBox.warning(self, "Estimate unavailable", str(error))
            return
        tone = {"A": "success", "B": "success", "C": "warning", "D": "danger"}.get(
            result["reliability_class"], "neutral"
        )
        self.ndt_estimate_pill.set_value(
            f"{result['predicted_compressive_strength_mpa']:.3f} MPa", tone
        )
        self.ndt_reliability_pill.set_value(result["reliability_class"], tone)
        self.ndt_estimate_set_pill.set_value(result["feature_set"])
        details = [result["reliability_reason"]]
        if result["outside_training_range_fields"]:
            details.append("Outside range: " + result["outside_training_range_fields"])
        if result["missing_fields"]:
            details.append("Defaults used for: " + result["missing_fields"])
        self.ndt_estimate_note.setText(" ".join(details))

    # ------------------------------------------------------------------
    # Durability profile actions
    # ------------------------------------------------------------------
    def run_durability_profile(self, silent: bool = False) -> None:
        try:
            result = self.service.durability_profile(
                self.context.dataframe,
                strength_weight=self.strength_weight_spin.value(),
                mass_weight=self.mass_weight_spin.value(),
                mass_penalty=self.mass_penalty_spin.value(),
                include_review_records=self.profile_review_check.isChecked(),
            )
        except Exception as error:
            if not silent:
                QMessageBox.warning(self, "Durability profile unavailable", str(error))
            return
        self.profile_result = result
        self.profile_model.set_dataframe(result.ranking)
        self.profile_records_pill.set_value(result.records)
        self.profile_best_pill.set_value(result.best_mix, "success")
        self.profile_score_pill.set_value(f"{result.best_score:.2f}", "success")
        self.profile_retention_pill.set_value(f"{result.mean_retention:.2f}%")
        self.profile_loss_pill.set_value(f"{result.maximum_strength_loss:.2f}%", "warning")
        self.profile_formula.setText(
            f"Score = {result.strength_weight:.2f} × retained strength + "
            f"{result.mass_weight:.2f} × max(0, 100 − {result.mass_penalty:.1f} × |mass change|). "
            "This configurable score supports screening and is not a prescribed material standard."
        )
        self.render_profile_figure()
        if not silent:
            self.context.message.emit("Durability profile calculated.")

    def render_profile_figure(self) -> None:
        if self.profile_result is None:
            return
        view = self.profile_view_combo.currentText()
        try:
            if view == "Initial vs residual strength":
                figure = self.service.durability_initial_residual_figure(
                    self.context.dataframe, self.profile_review_check.isChecked()
                )
            elif view == "Strength-retention heatmap":
                figure = self.service.durability_heatmap_figure(
                    self.context.dataframe, "strength_retention_percent",
                    self.profile_review_check.isChecked(),
                )
            elif view == "Mass-change heatmap":
                figure = self.service.durability_heatmap_figure(
                    self.context.dataframe, "mass_change_percent_derived",
                    self.profile_review_check.isChecked(),
                )
            else:
                figure = self.service.durability_score_figure(self.profile_result)
        except Exception as error:
            QMessageBox.warning(self, "Figure unavailable", str(error))
            return
        self.profile_figure = figure
        self.profile_canvas = self._replace_canvas(self.profile_canvas, figure)

    def export_profile_ranking(self) -> None:
        if self.profile_result is None:
            QMessageBox.information(self, "Nothing to export", "Calculate a durability profile first.")
            return
        self.export_dataframe(self.profile_result.ranking, "durability_ranking.csv")

    # ------------------------------------------------------------------
    # Durability estimator actions
    # ------------------------------------------------------------------
    def _checked_durability_predictors(self) -> list[str]:
        return [
            self.dur_predictor_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.dur_predictor_list.count())
            if self.dur_predictor_list.item(i).checkState() == Qt.CheckState.Checked
        ]

    def build_durability_estimator(self) -> None:
        predictors = self._checked_durability_predictors()
        try:
            result = self.service.build_durability_twin(
                self.context.dataframe,
                response=self.dur_response_combo.currentData(),
                predictors=predictors,
                method=self.dur_method_combo.currentText(),
                confidence_percent=float(self.dur_confidence_combo.currentData()),
                include_review_records=self.dur_review_check.isChecked(),
            )
        except Exception as error:
            QMessageBox.warning(self, "Durability estimator unavailable", str(error))
            return
        self.durability_result = result
        self.active_durability_artifact = result.artifact
        metrics = result.metrics
        self.dur_records_pill.set_value(result.observations)
        self.dur_rmse_pill.set_value(f"{metrics['rmse']:.3f}")
        self.dur_r2_pill.set_value(
            f"{metrics['r2']:.3f}", "success" if metrics["r2"] >= 0.5 else "warning"
        )
        coverage_tone = "success" if metrics["calibration_gap_percent"] <= 10 else "warning"
        self.dur_coverage_pill.set_value(f"{metrics['coverage_percent']:.1f}%", coverage_tone)
        self.dur_method_pill.set_value(result.method)
        self._refresh_sweep_fields()
        self.refresh_durability_library()
        self.context.message.emit("Durability estimator built.")
        if result.omitted_predictors:
            QMessageBox.warning(
                self,
                "Parameters excluded",
                "The durability estimator was built after automatically excluding "
                "parameters without usable values for the selected response:\n\n"
                + "\n".join(
                    f"• {COLUMN_LABELS.get(field, field)}"
                    for field in result.omitted_predictors
                ),
            )

    def _refresh_sweep_fields(self) -> None:
        self.dur_sweep_combo.clear()
        if self.active_durability_artifact is None:
            return
        metadata = self.active_durability_artifact["metadata"]
        for field, limits in metadata.get("numeric_training_ranges", {}).items():
            if len(limits) == 2 and not abs(float(limits[1]) - float(limits[0])) < 1e-12:
                self.dur_sweep_combo.addItem(COLUMN_LABELS.get(field, field), field)
        preferred = self.dur_sweep_combo.findData("ggbs_percent_numeric")
        if preferred >= 0:
            self.dur_sweep_combo.setCurrentIndex(preferred)

    def save_durability_estimator(self) -> None:
        if self.active_durability_artifact is None:
            QMessageBox.information(self, "No active estimator", "Build an estimator first.")
            return
        try:
            path = self.service.save_durability_artifact(
                self.active_durability_artifact, DURABILITY_DIR
            )
        except Exception as error:
            QMessageBox.warning(self, "Save failed", str(error))
            return
        self.refresh_durability_library()
        self.context.message.emit(f"Durability estimator saved as {path.name}.")

    def refresh_durability_library(self) -> None:
        frame = self.service.list_saved_durability_models(DURABILITY_DIR)
        current = self.dur_library_combo.currentData()
        self.dur_library_combo.clear()
        if self.active_durability_artifact is not None:
            metadata = self.active_durability_artifact["metadata"]
            self.dur_library_combo.addItem(
                f"Active · {COLUMN_LABELS.get(metadata.get('response', ''), metadata.get('response', ''))} "
                f"· {metadata.get('method', '')}",
                "__active__",
            )
        for _, row in frame.iterrows():
            self.dur_library_combo.addItem(
                f"{COLUMN_LABELS.get(row['response'], row['response'])} · {row['method']} · "
                f"RMSE {float(row['rmse']):.3f}",
                str(row["artifact_path"]),
            )
        index = self.dur_library_combo.findData(current)
        if index >= 0:
            self.dur_library_combo.setCurrentIndex(index)

    def load_selected_durability_model(self) -> None:
        value = self.dur_library_combo.currentData()
        if value == "__active__":
            return
        if not value:
            QMessageBox.information(self, "No saved estimator", "No saved estimator is selected.")
            return
        try:
            artifact = self.service.load_durability_artifact(value)
        except Exception as error:
            QMessageBox.warning(self, "Load failed", str(error))
            return
        self.active_durability_artifact = artifact
        metadata = artifact["metadata"]
        metrics = metadata.get("metrics", {})
        self.dur_records_pill.set_value(metadata.get("observations", "—"))
        self.dur_rmse_pill.set_value(f"{float(metrics.get('rmse', float('nan'))):.3f}")
        r2 = float(metrics.get("r2", float("nan")))
        self.dur_r2_pill.set_value(f"{r2:.3f}", "success" if r2 >= 0.5 else "warning")
        coverage = float(metrics.get("coverage_percent", float("nan")))
        self.dur_coverage_pill.set_value(f"{coverage:.1f}%")
        self.dur_method_pill.set_value(metadata.get("method", ""))
        response_index = self.dur_response_combo.findData(metadata.get("response"))
        if response_index >= 0:
            self.dur_response_combo.setCurrentIndex(response_index)
        self._refresh_sweep_fields()
        self.refresh_durability_library()
        self.context.message.emit("Durability estimator loaded.")

    def delete_selected_durability_model(self) -> None:
        value = self.dur_library_combo.currentData()
        if not value or value == "__active__":
            QMessageBox.information(self, "No saved estimator", "Select a saved estimator to delete.")
            return
        answer = QMessageBox.question(self, "Delete estimator?", "Delete the selected estimator?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.service.delete_artifact(value)
        self.refresh_durability_library()
        self.context.message.emit("Durability estimator deleted.")

    def _durability_values(self) -> dict[str, object]:
        values: dict[str, object] = {
            field: spin.value() for field, spin in self.dur_input_spins.items()
        }
        values["acid_type"] = self.dur_acid_combo.currentText()
        return values

    def estimate_durability_scenario(self) -> None:
        if self.active_durability_artifact is None:
            QMessageBox.information(self, "No active estimator", "Build or load an estimator first.")
            return
        try:
            estimate = self.service.predict_durability_scenario(
                self.active_durability_artifact, self._durability_values()
            )
        except Exception as error:
            QMessageBox.warning(self, "Estimate unavailable", str(error))
            return
        metadata = self.active_durability_artifact["metadata"]
        metrics = metadata.get("metrics", {})
        reliability = str(estimate["reliability_class"])
        nrmse = float(metrics.get("normalized_rmse_percent", 0.0))
        r2 = float(metrics.get("r2", 0.0))
        if nrmse > 40 or r2 < 0:
            reliability = "D"
            estimate["reliability_reason"] = (
                "Global cross-validation indicates weak predictive support for this response."
            )
        elif nrmse > 25 and reliability in {"A", "B"}:
            reliability = "C"
            estimate["reliability_reason"] = (
                "Global cross-validation indicates limited predictive support for this response."
            )
        tone = {"A": "success", "B": "success", "C": "warning", "D": "danger"}.get(
            reliability, "neutral"
        )
        self.dur_estimate_pill.set_value(f"{estimate['predicted_mean']:.3f}", tone)
        self.dur_interval_pill.set_value(
            f"{estimate['lower_bound']:.3f} – {estimate['upper_bound']:.3f}"
        )
        self.dur_reliability_pill.set_value(reliability, tone)
        details = [estimate["reliability_reason"]]
        if estimate.get("outside_training_range_fields"):
            details.append("Outside range: " + estimate["outside_training_range_fields"])
        self.dur_estimate_note.setText(" ".join(details))

    def generate_durability_sweep(self) -> None:
        if self.active_durability_artifact is None:
            QMessageBox.information(self, "No active estimator", "Build or load an estimator first.")
            return
        axis = self.dur_sweep_combo.currentData()
        if not axis:
            QMessageBox.information(
                self, "No sweep field", "The active estimator has no varying numeric predictor."
            )
            return
        try:
            sweep = self.service.durability_sweep(
                self.active_durability_artifact,
                self._durability_values(),
                axis,
                self.dur_sweep_resolution.value(),
            )
            response = self.active_durability_artifact["metadata"]["response"]
            figure = self.service.durability_sweep_figure(sweep, axis, response)
        except Exception as error:
            QMessageBox.warning(self, "Curve unavailable", str(error))
            return
        self.sweep_data = sweep
        self.sweep_figure = figure
        self.sweep_canvas = self._replace_canvas(self.sweep_canvas, figure)
        self.context.message.emit("Durability response curve generated.")

    def export_sweep_data(self) -> None:
        self.export_dataframe(self.sweep_data, "durability_response_curve.csv")
