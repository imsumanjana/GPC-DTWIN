from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QFileDialog, QFormLayout, QFrame,
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QSplitter, QTabWidget, QTableView, QVBoxLayout, QWidget
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from gpc_dtwin.columns import BINDER_PERCENT_COLUMNS, COLUMN_LABELS
from gpc_dtwin.ui.export_preview_dialog import open_figure_export_dialog
from gpc_dtwin.paths import EXPORT_DIR
from gpc_dtwin.services.statistics_service import StatisticsService
from gpc_dtwin.ui.models import DataFrameModel
from gpc_dtwin.ui.scrolling import scrollable_panel
from gpc_dtwin.ui.widgets import ValuePill


class StatisticsPage(QWidget):
    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.context = context
        self.service = StatisticsService()
        self.current_figure: Figure | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 24)
        root.setSpacing(14)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._descriptive_tab(), "Descriptive")
        self.tabs.addTab(self._correlation_tab(), "Correlation")
        self.tabs.addTab(self._anova_tab(), "Group comparison")
        self.tabs.addTab(self._regression_tab(), "Regression")
        root.addWidget(self.tabs, 1)

        self.context.data_changed.connect(self.refresh)
        self.refresh()

    def _descriptive_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        controls = QHBoxLayout()
        self.desc_columns = QListWidget()
        self.desc_columns.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.desc_columns.setMaximumHeight(130)
        controls.addWidget(self.desc_columns, 1)
        run = QPushButton("Calculate")
        run.setObjectName("PrimaryButton")
        run.clicked.connect(self.run_descriptive)
        export = QPushButton("Export table")
        export.clicked.connect(lambda: self.export_table(self.desc_model.dataframe, "descriptive_statistics.csv"))
        buttons = QVBoxLayout()
        buttons.addWidget(run)
        buttons.addWidget(export)
        buttons.addStretch()
        controls.addLayout(buttons)
        layout.addLayout(controls)
        self.desc_model = DataFrameModel()
        table = QTableView()
        table.setModel(self.desc_model)
        table.setSortingEnabled(True)
        table.setAlternatingRowColors(True)
        layout.addWidget(table, 1)
        return page

    def _correlation_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Method"))
        self.corr_method = QComboBox()
        self.corr_method.addItems(["pearson", "spearman"])
        controls.addWidget(self.corr_method)
        run = QPushButton("Calculate")
        run.setObjectName("PrimaryButton")
        run.clicked.connect(self.run_correlation)
        controls.addWidget(run)
        controls.addStretch()
        export = QPushButton("Export figure")
        export.clicked.connect(self.export_current_figure)
        controls.addWidget(export)
        layout.addLayout(controls)
        self.corr_canvas = FigureCanvasQTAgg(Figure(figsize=(8, 5), constrained_layout=True))
        layout.addWidget(self.corr_canvas, 1)
        return page

    def _anova_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        controls = QFrame()
        controls.setObjectName("Card")
        form = QFormLayout(controls)
        self.anova_response = QComboBox()
        self.anova_factor = QComboBox()
        form.addRow("Response", self.anova_response)
        form.addRow("Factor", self.anova_factor)
        run = QPushButton("Run comparison")
        run.setObjectName("PrimaryButton")
        run.clicked.connect(self.run_anova)
        form.addRow("", run)
        layout.addWidget(controls)

        metrics = QHBoxLayout()
        self.anova_f = ValuePill()
        self.anova_p = ValuePill()
        self.anova_eta = ValuePill()
        metrics.addWidget(QLabel("F statistic")); metrics.addWidget(self.anova_f)
        metrics.addWidget(QLabel("p value")); metrics.addWidget(self.anova_p)
        metrics.addWidget(QLabel("η²")); metrics.addWidget(self.anova_eta)
        metrics.addStretch()
        layout.addLayout(metrics)

        splitter = QSplitter()
        self.anova_model = DataFrameModel()
        table = QTableView()
        table.setModel(self.anova_model)
        table.setAlternatingRowColors(True)
        splitter.addWidget(table)
        self.anova_canvas = FigureCanvasQTAgg(Figure(figsize=(7, 5), constrained_layout=True))
        splitter.addWidget(self.anova_canvas)
        splitter.setSizes([420, 650])
        layout.addWidget(splitter, 1)
        return page

    def _regression_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        splitter = QSplitter()
        controls = QFrame()
        controls.setObjectName("Card")
        controls_layout = QVBoxLayout(controls)
        form = QFormLayout()
        self.reg_response = QComboBox()
        self.reg_response.currentIndexChanged.connect(self.refresh_regression_predictors)
        self.reg_degree = QComboBox()
        self.reg_degree.addItem("Linear", 1)
        self.reg_degree.addItem("Quadratic numeric terms", 2)
        form.addRow("Response", self.reg_response)
        form.addRow("Model", self.reg_degree)
        controls_layout.addLayout(form)
        controls_layout.addWidget(QLabel("Predictors"))
        self.reg_predictors = QListWidget()
        self.reg_predictors.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        controls_layout.addWidget(self.reg_predictors, 1)
        self.reg_predictor_note = QLabel(
            "Unavailable predictors are excluded automatically for the selected response."
        )
        self.reg_predictor_note.setObjectName("Muted")
        self.reg_predictor_note.setWordWrap(True)
        controls_layout.addWidget(self.reg_predictor_note)
        run = QPushButton("Fit and validate")
        run.setObjectName("PrimaryButton")
        run.clicked.connect(self.run_regression)
        controls_layout.addWidget(run)
        controls_scroll = scrollable_panel(controls, minimum_width=330)
        controls_scroll.setMaximumWidth(440)
        splitter.addWidget(controls_scroll)

        results = QWidget()
        results_layout = QVBoxLayout(results)
        metric_row = QHBoxLayout()
        self.reg_rmse = ValuePill()
        self.reg_mae = ValuePill()
        self.reg_r2 = ValuePill()
        metric_row.addWidget(QLabel("RMSE")); metric_row.addWidget(self.reg_rmse)
        metric_row.addWidget(QLabel("MAE")); metric_row.addWidget(self.reg_mae)
        metric_row.addWidget(QLabel("R²")); metric_row.addWidget(self.reg_r2)
        metric_row.addStretch()
        results_layout.addLayout(metric_row)
        self.reg_method = QLabel()
        self.reg_method.setObjectName("Muted")
        results_layout.addWidget(self.reg_method)
        self.reg_canvas = FigureCanvasQTAgg(Figure(figsize=(7, 5), constrained_layout=True))
        results_layout.addWidget(self.reg_canvas, 1)
        self.coefficient_model = DataFrameModel()
        coefficients = QTableView()
        coefficients.setModel(self.coefficient_model)
        coefficients.setMaximumHeight(180)
        coefficients.setAlternatingRowColors(True)
        results_layout.addWidget(coefficients)
        splitter.addWidget(results)
        splitter.setSizes([330, 800])
        layout.addWidget(splitter, 1)
        return page

    def refresh(self) -> None:
        numeric = self.service.available_numeric(self.context.dataframe)
        factors = self.service.available_factors(self.context.dataframe)
        self._fill_check_list(self.desc_columns, numeric, checked=True)
        self._fill_combo(self.anova_response, numeric, "compressive_strength_mpa")
        self._fill_combo(self.anova_factor, factors, "record_group")
        self._fill_combo(self.reg_response, numeric, "compressive_strength_mpa")
        predictor_options = numeric + [factor for factor in factors if factor not in {"data_status"}]
        self._fill_check_list(
            self.reg_predictors, predictor_options,
            checked_items={
                *BINDER_PERCENT_COLUMNS,
                "mechanical_test_age_days",
                "aas_b_ratio",
            }
        )
        self.refresh_regression_predictors()
        self.run_descriptive()
        self.run_correlation()

    def refresh_regression_predictors(self, *_args) -> None:
        if not hasattr(self, "reg_predictors"):
            return
        response = self.reg_response.currentData()
        if not response:
            return
        values = [
            str(self.reg_predictors.item(index).data(Qt.ItemDataRole.UserRole))
            for index in range(self.reg_predictors.count())
        ]
        available, unavailable = self.service.regression_predictor_availability(
            self.context.dataframe, str(response), values
        )
        available_set = set(available)
        unavailable_set = set(unavailable)
        omitted_labels: list[str] = []
        for index in range(self.reg_predictors.count()):
            item = self.reg_predictors.item(index)
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
                        omitted_labels.append(COLUMN_LABELS.get(field, field))
        if omitted_labels:
            self.reg_predictor_note.setText(
                f"{len(omitted_labels)} unavailable parameters are excluded automatically "
                f"for {COLUMN_LABELS.get(str(response), str(response))}."
            )
        else:
            self.reg_predictor_note.setText(
                "All listed parameters have usable overlap with the selected response."
            )

    @staticmethod
    def _fill_combo(combo: QComboBox, values: list[str], preferred: str) -> None:
        combo.blockSignals(True)
        combo.clear()
        for value in values:
            combo.addItem(COLUMN_LABELS.get(value, value), value)
        index = combo.findData(preferred)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.blockSignals(False)

    @staticmethod
    def _fill_check_list(widget: QListWidget, values: list[str], checked: bool = False,
                         checked_items: set[str] | None = None) -> None:
        widget.clear()
        for value in values:
            item = QListWidgetItem(COLUMN_LABELS.get(value, value))
            item.setData(Qt.ItemDataRole.UserRole, value)
            should_check = checked if checked_items is None else value in checked_items
            item.setCheckState(
                Qt.CheckState.Checked if should_check else Qt.CheckState.Unchecked
            )
            widget.addItem(item)

    @staticmethod
    def _checked_values(widget: QListWidget) -> list[str]:
        return [
            widget.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(widget.count())
            if widget.item(i).checkState() == Qt.CheckState.Checked
        ]

    def run_descriptive(self) -> None:
        columns = self._checked_values(self.desc_columns)
        self.desc_model.set_dataframe(self.service.descriptive(self.context.dataframe, columns))

    def run_correlation(self) -> None:
        try:
            matrix = self.service.correlation(
                self.context.dataframe, method=self.corr_method.currentText()
            )
            figure = self.service.correlation_figure(matrix)
            self.current_figure = figure
            self.corr_canvas = self._replace_canvas(self.corr_canvas, figure)
        except Exception as error:
            QMessageBox.critical(self, "Correlation failed", str(error))

    def run_anova(self) -> None:
        response = self.anova_response.currentData()
        factor = self.anova_factor.currentData()
        if not response or not factor:
            return
        try:
            result = self.service.one_way_anova(self.context.dataframe, response, factor)
            self.anova_f.set_value(f"{result.statistic:.4f}")
            tone = "success" if result.p_value < 0.05 else "neutral"
            self.anova_p.set_value(f"{result.p_value:.5g}", tone)
            self.anova_eta.set_value(f"{result.effect_size_eta_squared:.4f}")
            self.anova_model.set_dataframe(result.group_summary)
            figure = self.service.anova_figure(self.context.dataframe, response, factor)
            self.current_figure = figure
            self.anova_canvas = self._replace_canvas(self.anova_canvas, figure)
        except Exception as error:
            QMessageBox.warning(self, "Group comparison unavailable", str(error))

    def run_regression(self) -> None:
        response = self.reg_response.currentData()
        predictors = [value for value in self._checked_values(self.reg_predictors) if value != response]
        if not response:
            return
        try:
            result = self.service.regression(
                self.context.dataframe, response, predictors, int(self.reg_degree.currentData())
            )
            self.reg_rmse.set_value(f"{result.rmse:.4f}")
            self.reg_mae.set_value(f"{result.mae:.4f}")
            self.reg_r2.set_value(f"{result.r2:.4f}", "success" if result.r2 >= 0.5 else "warning")
            detail = f"{result.cv_method} · {result.observations} observations"
            if result.omitted_predictors:
                labels = [
                    COLUMN_LABELS.get(field, field)
                    for field in result.omitted_predictors
                ]
                detail += " · excluded: " + ", ".join(labels)
            self.reg_method.setText(detail)
            self.coefficient_model.set_dataframe(result.coefficients)
            figure = self.service.regression_figure(result)
            self.current_figure = figure
            self.reg_canvas = self._replace_canvas(self.reg_canvas, figure)
            if result.omitted_predictors:
                labels = [
                    COLUMN_LABELS.get(field, field)
                    for field in result.omitted_predictors
                ]
                QMessageBox.warning(
                    self,
                    "Parameters excluded",
                    "Regression completed after automatically excluding parameters "
                    "without usable values for the selected response:\n\n"
                    + "\n".join(f"• {label}" for label in labels),
                )
        except Exception as error:
            QMessageBox.warning(self, "Regression unavailable", str(error))

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

    def export_table(self, dataframe, default_name: str) -> None:
        if dataframe.empty:
            QMessageBox.information(self, "Nothing to export", "The current table is empty.")
            return
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(
            self, "Export table", str(EXPORT_DIR / default_name), "CSV data (*.csv)"
        )
        if path:
            destination = Path(path).with_suffix(".csv")
            dataframe.to_csv(destination, index=False, encoding="utf-8-sig")
            self.context.message.emit(f"Table exported to {destination.name}.")

    def export_current_figure(self) -> None:
        if self.current_figure is None:
            QMessageBox.information(self, "Nothing to export", "Run an analysis first.")
            return
        open_figure_export_dialog(
            self, self.current_figure,
            suggested_name=str(EXPORT_DIR / "statistical_analysis.png"),
        )

