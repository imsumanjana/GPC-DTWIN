from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QFileDialog, QFormLayout, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox, QSplitter,
    QTableView, QTabWidget, QVBoxLayout, QWidget,
)

from gpc_dtwin.metadata import COPYRIGHT_HOLDER, COPYRIGHT_TEXT, ORCID_ID, ORCID_URL
from gpc_dtwin.paths import (
    ACTIVE_LEARNING_DIR, BUNDLE_DIR, DURABILITY_DIR, MODEL_DIR, NDT_DIR,
    OPTIMIZATION_DIR, REPORT_DIR, TWIN_DIR,
)
from gpc_dtwin.services.reporting_service import (
    BundleVerificationResult, ReportOptions, ReportResult, ReportingService,
)
from gpc_dtwin.ui.models import DataFrameModel
from gpc_dtwin.ui.scrolling import scrollable_panel
from gpc_dtwin.ui.widgets import MetricCard, SectionHeader, ValuePill


class ReportingPage(QWidget):
    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.context = context
        self.service = ReportingService()
        self.last_report: ReportResult | None = None
        self.last_verification: BundleVerificationResult | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 24)
        root.setSpacing(14)
        root.addWidget(SectionHeader(
            "Reports & Provenance",
            "Create self-contained analytical reports, record reproducibility metadata, and verify exported bundles.",
        ))

        cards = QGridLayout()
        cards.setHorizontalSpacing(12)
        cards.setVerticalSpacing(12)
        self.records_card = MetricCard("R", "Records")
        self.findings_card = MetricCard("Q", "Quality findings")
        self.fingerprint_card = MetricCard("#", "Dataset fingerprint")
        self.artifact_card = MetricCard("A", "Stored artifacts")
        for index, card in enumerate((
            self.records_card, self.findings_card, self.fingerprint_card, self.artifact_card,
        )):
            cards.addWidget(card, index // 4, index % 4)
        root.addLayout(cards)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._builder_tab(), "Report builder")
        self.tabs.addTab(self._manifest_tab(), "Manifest preview")
        self.tabs.addTab(self._verification_tab(), "Bundle verification")
        self.tabs.addTab(self._history_tab(), "Report history")
        root.addWidget(self.tabs, 1)

        attribution = QLabel(
            f"{COPYRIGHT_TEXT} · ORCID: <a href=\"{ORCID_URL}\">{ORCID_ID}</a>"
        )
        attribution.setObjectName("Muted")
        attribution.setTextFormat(Qt.TextFormat.RichText)
        attribution.setOpenExternalLinks(True)
        attribution.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        root.addWidget(attribution)

        self.context.data_changed.connect(self.refresh)
        self.context.audit_changed.connect(self.refresh)
        self.refresh()

    def _artifact_roots(self) -> dict[str, Path]:
        return {
            "Predictive models": MODEL_DIR,
            "Digital twins": TWIN_DIR,
            "NDT models": NDT_DIR,
            "Durability estimators": DURABILITY_DIR,
            "Optimization runs": OPTIMIZATION_DIR,
            "Active-learning runs": ACTIVE_LEARNING_DIR,
        }

    def _builder_tab(self) -> QWidget:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        controls = QWidget()
        controls.setMinimumWidth(390)
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(6, 6, 8, 6)
        controls_layout.setSpacing(12)

        identity = QFrame()
        identity.setObjectName("Card")
        identity_form = QFormLayout(identity)
        identity_form.setContentsMargins(16, 16, 16, 16)
        self.title_edit = QLineEdit("Materials Analytics Report")
        self.project_edit = QLineEdit("GPC-DTwin Project")
        self.prepared_edit = QLineEdit(COPYRIGHT_HOLDER)
        identity_form.addRow("Report title", self.title_edit)
        identity_form.addRow("Project label", self.project_edit)
        identity_form.addRow("Prepared by", self.prepared_edit)
        controls_layout.addWidget(identity)

        content = QFrame()
        content.setObjectName("Card")
        content_form = QFormLayout(content)
        content_form.setContentsMargins(16, 16, 16, 16)
        self.figures_check = QCheckBox("Include analytical figures")
        self.figures_check.setChecked(True)
        self.preview_check = QCheckBox("Include dataset preview")
        self.preview_check.setChecked(True)
        self.inventory_check = QCheckBox("Include stored-artifact inventory")
        self.inventory_check.setChecked(True)
        self.preview_rows_spin = QSpinBox()
        self.preview_rows_spin.setRange(5, 100)
        self.preview_rows_spin.setValue(15)
        content_form.addRow(self.figures_check)
        content_form.addRow(self.preview_check)
        content_form.addRow(self.inventory_check)
        content_form.addRow("Preview rows", self.preview_rows_spin)
        controls_layout.addWidget(content)

        generate = QPushButton("Generate HTML report")
        generate.setObjectName("PrimaryButton")
        generate.clicked.connect(self.generate_report)
        bundle = QPushButton("Export reproducibility bundle")
        bundle.clicked.connect(self.export_bundle)
        refresh = QPushButton("Refresh report summary")
        refresh.clicked.connect(self.refresh)
        controls_layout.addWidget(generate)
        controls_layout.addWidget(bundle)
        controls_layout.addWidget(refresh)
        controls_layout.addStretch()
        splitter.addWidget(scrollable_panel(controls, minimum_width=390))

        results = QWidget()
        results.setMinimumWidth(620)
        results_layout = QVBoxLayout(results)
        results_layout.setContentsMargins(8, 6, 6, 6)
        results_layout.setSpacing(12)

        status_card = QFrame()
        status_card.setObjectName("Card")
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(18, 18, 18, 18)
        status_layout.addWidget(SectionHeader(
            "Latest report",
            "Generated reports contain a report page, dataset snapshot, quality findings, manifest, and optional square 600 dpi figures.",
        ))
        status_row = QHBoxLayout()
        self.report_status = ValuePill("Not generated", "neutral")
        self.report_path = QLabel("No report has been generated in this session.")
        self.report_path.setObjectName("Muted")
        self.report_path.setWordWrap(True)
        self.report_path.setTextInteractionFlags(
            self.report_path.textInteractionFlags() |
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        status_row.addWidget(self.report_status)
        status_row.addWidget(self.report_path, 1)
        status_layout.addLayout(status_row)
        action_row = QHBoxLayout()
        self.open_report_button = QPushButton("Open report")
        self.open_report_button.setEnabled(False)
        self.open_report_button.clicked.connect(self.open_latest_report)
        open_folder = QPushButton("Open reports folder")
        open_folder.clicked.connect(self.open_report_folder)
        action_row.addWidget(self.open_report_button)
        action_row.addWidget(open_folder)
        action_row.addStretch()
        status_layout.addLayout(action_row)
        results_layout.addWidget(status_card)

        summary_card = QFrame()
        summary_card.setObjectName("Card")
        summary_layout = QVBoxLayout(summary_card)
        summary_layout.setContentsMargins(18, 18, 18, 18)
        summary_layout.addWidget(SectionHeader(
            "Current report content",
            "A preview of the information that will be written to the report manifest.",
        ))
        self.report_summary_model = DataFrameModel()
        self.report_summary_table = QTableView()
        self.report_summary_table.setModel(self.report_summary_model)
        self.report_summary_table.setSortingEnabled(True)
        self.report_summary_table.setMinimumHeight(360)
        self.report_summary_table.horizontalHeader().setStretchLastSection(True)
        summary_layout.addWidget(self.report_summary_table)
        results_layout.addWidget(summary_card, 1)
        splitter.addWidget(results)
        splitter.setSizes([420, 900])
        page_layout.addWidget(splitter, 1)
        return page

    def _manifest_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        actions = QHBoxLayout()
        refresh = QPushButton("Refresh manifest preview")
        refresh.clicked.connect(self.refresh_manifest)
        export = QPushButton("Export manifest JSON")
        export.clicked.connect(self.export_manifest)
        actions.addWidget(refresh)
        actions.addWidget(export)
        actions.addStretch()
        layout.addLayout(actions)
        self.manifest_model = DataFrameModel()
        self.manifest_table = QTableView()
        self.manifest_table.setModel(self.manifest_model)
        self.manifest_table.setSortingEnabled(True)
        self.manifest_table.horizontalHeader().setStretchLastSection(True)
        self.manifest_table.setMinimumHeight(520)
        layout.addWidget(self.manifest_table, 1)
        return page

    def _verification_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        actions = QHBoxLayout()
        verify = QPushButton("Select and verify bundle")
        verify.setObjectName("PrimaryButton")
        verify.clicked.connect(self.select_and_verify_bundle)
        self.verification_status = ValuePill("No bundle checked", "neutral")
        actions.addWidget(verify)
        actions.addWidget(self.verification_status)
        actions.addStretch()
        layout.addLayout(actions)
        self.verification_path = QLabel("")
        self.verification_path.setObjectName("Muted")
        self.verification_path.setWordWrap(True)
        self.verification_path.setTextInteractionFlags(
            self.verification_path.textInteractionFlags() |
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self.verification_path)
        self.verification_model = DataFrameModel()
        self.verification_table = QTableView()
        self.verification_table.setModel(self.verification_model)
        self.verification_table.setSortingEnabled(True)
        self.verification_table.horizontalHeader().setStretchLastSection(True)
        self.verification_table.setMinimumHeight(520)
        layout.addWidget(self.verification_table, 1)
        return page

    def _history_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        actions = QHBoxLayout()
        refresh = QPushButton("Refresh history")
        refresh.clicked.connect(self.refresh_history)
        open_selected = QPushButton("Open selected item")
        open_selected.clicked.connect(self.open_selected_history)
        actions.addWidget(refresh)
        actions.addWidget(open_selected)
        actions.addStretch()
        layout.addLayout(actions)
        self.history_model = DataFrameModel()
        self.history_table = QTableView()
        self.history_table.setModel(self.history_model)
        self.history_table.setSortingEnabled(True)
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.history_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.history_table.horizontalHeader().setStretchLastSection(True)
        self.history_table.setMinimumHeight(520)
        self.history_table.doubleClicked.connect(self.open_selected_history)
        layout.addWidget(self.history_table, 1)
        return page

    def _options(self) -> ReportOptions:
        return ReportOptions(
            title=self.title_edit.text().strip() or "Materials Analytics Report",
            project_label=self.project_edit.text().strip() or "GPC-DTwin Project",
            prepared_by=self.prepared_edit.text().strip() or COPYRIGHT_HOLDER,
            include_figures=self.figures_check.isChecked(),
            include_dataset_preview=self.preview_check.isChecked(),
            include_artifact_inventory=self.inventory_check.isChecked(),
            preview_rows=self.preview_rows_spin.value(),
        )

    @staticmethod
    def _flatten_manifest(value: Any, prefix: str = "") -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        if isinstance(value, dict):
            for key, item in value.items():
                path = f"{prefix}.{key}" if prefix else str(key)
                rows.extend(ReportingPage._flatten_manifest(item, path))
        elif isinstance(value, list):
            if value and all(isinstance(item, dict) for item in value):
                rows.append({"field": prefix, "value": f"{len(value)} items"})
            else:
                rows.append({"field": prefix, "value": json.dumps(value, ensure_ascii=False)})
        else:
            rows.append({"field": prefix, "value": "" if value is None else str(value)})
        return rows

    def _manifest(self) -> dict[str, Any]:
        return self.service.manifest_preview(
            self.context.dataframe,
            self.context.audit_issues,
            self._options(),
            self._artifact_roots(),
        )

    def refresh(self) -> None:
        dataframe = self.context.dataframe
        audit = self.context.audit_issues
        manifest = self._manifest()
        self.records_card.set_value(
            len(dataframe), f"{len(dataframe.columns)} fields"
        )
        quality = manifest["quality"]
        self.findings_card.set_value(
            quality["total"],
            f"{quality['critical']} critical · {quality['warning']} warning",
        )
        fingerprint = manifest["dataset"]["sha256"]
        self.fingerprint_card.set_value(
            fingerprint[:12], "SHA-256 dataset identity"
        )
        self.artifact_card.set_value(
            manifest["stored_artifacts"]["count"], "Saved analytical artifacts"
        )
        summary = pd.DataFrame([
            {"Measure": "Report title", "Value": self._options().title},
            {"Measure": "Project label", "Value": self._options().project_label},
            {"Measure": "Prepared by", "Value": self._options().prepared_by},
            {"Measure": "Records", "Value": manifest["dataset"]["records"]},
            {"Measure": "Fields", "Value": manifest["dataset"]["fields"]},
            {"Measure": "Mixes", "Value": manifest["dataset"]["mixes"]},
            {"Measure": "Quality findings", "Value": manifest["quality"]["total"]},
            {"Measure": "Stored artifacts", "Value": manifest["stored_artifacts"]["count"]},
            {"Measure": "Square figures", "Value": "600 dpi · 3600 × 3600 pixels"},
            {"Measure": "Copyright", "Value": COPYRIGHT_TEXT},
            {"Measure": "ORCID", "Value": ORCID_URL},
        ])
        self.report_summary_model.set_dataframe(summary)
        self.refresh_manifest()
        self.refresh_history()

    def refresh_manifest(self) -> None:
        manifest = self._manifest()
        self.manifest_model.set_dataframe(pd.DataFrame(self._flatten_manifest(manifest)))

    def generate_report(self) -> None:
        try:
            REPORT_DIR.mkdir(parents=True, exist_ok=True)
            folder = REPORT_DIR / f"report_{self.service.timestamp_slug()}"
            self.last_report = self.service.generate_report_directory(
                self.context.dataframe,
                self.context.audit_issues,
                folder,
                self._options(),
                self._artifact_roots(),
            )
            self.report_status.set_value("Generated", "success")
            self.report_path.setText(str(self.last_report.html_path))
            self.open_report_button.setEnabled(True)
            self.context.message.emit(f"Report generated in {folder.name}.")
            self.refresh_history()
        except Exception as error:
            QMessageBox.critical(self, "Report generation failed", str(error))

    def export_bundle(self) -> None:
        BUNDLE_DIR.mkdir(parents=True, exist_ok=True)
        default = BUNDLE_DIR / f"GPC_DTwin_Bundle_{self.service.timestamp_slug()}.zip"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export reproducibility bundle",
            str(default),
            "ZIP archive (*.zip)",
        )
        if not path:
            return
        try:
            result = self.service.create_bundle(
                self.context.dataframe,
                self.context.audit_issues,
                path,
                self._options(),
                self._artifact_roots(),
            )
            self.context.message.emit(
                f"Bundle exported with {result.file_count} files."
            )
            QMessageBox.information(
                self,
                "Bundle exported",
                f"The reproducibility bundle was written to:\n\n{result.archive_path}",
            )
            self.refresh_history()
        except Exception as error:
            QMessageBox.critical(self, "Bundle export failed", str(error))

    def export_manifest(self) -> None:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        default = REPORT_DIR / f"GPC_DTwin_Manifest_{self.service.timestamp_slug()}.json"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export manifest", str(default), "JSON document (*.json)"
        )
        if not path:
            return
        destination = Path(path)
        if destination.suffix.lower() != ".json":
            destination = destination.with_suffix(".json")
        try:
            destination.write_text(
                json.dumps(self._manifest(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            self.context.message.emit(f"Manifest exported to {destination.name}.")
        except Exception as error:
            QMessageBox.critical(self, "Manifest export failed", str(error))

    def select_and_verify_bundle(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Verify reproducibility bundle", str(BUNDLE_DIR), "ZIP archive (*.zip)"
        )
        if not path:
            return
        try:
            self.last_verification = self.service.verify_bundle(path)
            result = self.last_verification
            self.verification_model.set_dataframe(result.checks)
            self.verification_path.setText(str(result.archive_path))
            if result.valid:
                self.verification_status.set_value("Verified", "success")
                self.context.message.emit("Bundle integrity verification passed.")
            else:
                self.verification_status.set_value("Verification failed", "danger")
                self.context.message.emit("Bundle integrity verification found differences.")
        except Exception as error:
            QMessageBox.critical(self, "Bundle verification failed", str(error))

    def refresh_history(self) -> None:
        history = self.service.report_history(REPORT_DIR, BUNDLE_DIR)
        self.history_model.set_dataframe(history)

    def open_latest_report(self) -> None:
        if self.last_report is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_report.html_path)))

    @staticmethod
    def open_report_folder() -> None:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(REPORT_DIR)))

    def open_selected_history(self, *_args) -> None:
        selection = self.history_table.selectionModel().selectedRows()
        if not selection:
            return
        row = selection[0].row()
        frame = self.history_model.dataframe
        if row >= len(frame):
            return
        path = Path(str(frame.iloc[row]["path"]))
        if path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
