from __future__ import annotations

from pathlib import Path
import zipfile

import pandas as pd
from PIL import Image

from gpc_dtwin.figure_export import EXPORT_DPI, EXPORT_SIZE_INCHES
from gpc_dtwin.metadata import COPYRIGHT_TEXT, ORCID_URL
from gpc_dtwin.paths import REFERENCE_DATASET
from gpc_dtwin.services.audit_service import AuditService
from gpc_dtwin.services.data_service import DataService
from gpc_dtwin.services.reporting_service import ReportOptions, ReportingService


def _dataset_and_audit():
    dataframe = DataService.load_csv(REFERENCE_DATASET)
    audit = AuditService().run(dataframe)
    return dataframe, audit


def test_manifest_preview_contains_fingerprints_and_attribution(tmp_path):
    dataframe, audit = _dataset_and_audit()
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    (artifact_root / "sample.json").write_text('{"ok": true}', encoding="utf-8")

    manifest = ReportingService.manifest_preview(
        dataframe,
        audit,
        ReportOptions(include_figures=False),
        {"Models": artifact_root},
    )

    assert manifest["application"]["version"] == "1.1.5"
    assert manifest["dataset"]["records"] == len(dataframe)
    assert len(manifest["dataset"]["sha256"]) == 64
    assert manifest["quality"]["total"] == len(audit)
    assert manifest["attribution"]["copyright"] == COPYRIGHT_TEXT
    assert manifest["attribution"]["orcid_url"] == ORCID_URL
    assert manifest["stored_artifacts"]["count"] == 1


def test_report_directory_contains_html_snapshots_and_manifest(tmp_path):
    dataframe, audit = _dataset_and_audit()
    result = ReportingService.generate_report_directory(
        dataframe,
        audit,
        tmp_path / "report",
        ReportOptions(include_figures=False, preview_rows=8),
    )

    assert result.html_path.exists()
    assert result.manifest_path.exists()
    assert result.dataset_path.exists()
    assert result.audit_path.exists()
    html_text = result.html_path.read_text(encoding="utf-8")
    assert COPYRIGHT_TEXT in html_text
    assert ORCID_URL in html_text
    assert "Dataset SHA-256" in html_text
    assert result.manifest["files"]["active_dataset.csv"]["sha256"]


def test_report_figures_are_square_and_600_dpi(tmp_path):
    dataframe, audit = _dataset_and_audit()
    figures = ReportingService.create_report_figures(
        dataframe, audit, tmp_path / "figures"
    )
    assert len(figures) == 4
    expected_pixels = int(EXPORT_SIZE_INCHES * EXPORT_DPI)
    for path in figures:
        with Image.open(path) as image:
            assert image.size == (expected_pixels, expected_pixels)
            dpi = image.info.get("dpi", (0, 0))
            assert abs(float(dpi[0]) - EXPORT_DPI) < 1.0
            assert abs(float(dpi[1]) - EXPORT_DPI) < 1.0


def test_bundle_creation_verification_and_tamper_detection(tmp_path):
    dataframe, audit = _dataset_and_audit()
    bundle = ReportingService.create_bundle(
        dataframe,
        audit,
        tmp_path / "bundle.zip",
        ReportOptions(include_figures=False),
    )
    assert bundle.archive_path.exists()
    verified = ReportingService.verify_bundle(bundle.archive_path)
    assert verified.valid
    assert verified.checks["status"].eq("MATCH").all()

    tampered_path = tmp_path / "tampered.zip"
    with zipfile.ZipFile(bundle.archive_path, "r") as source, zipfile.ZipFile(
        tampered_path, "w", compression=zipfile.ZIP_DEFLATED
    ) as target:
        for name in source.namelist():
            payload = source.read(name)
            if name.endswith("active_dataset.csv"):
                payload += b"\nTAMPERED"
            target.writestr(name, payload)

    tampered = ReportingService.verify_bundle(tampered_path)
    assert not tampered.valid
    assert tampered.checks["status"].eq("MISMATCH").any()


def test_report_history_lists_reports_and_bundles(tmp_path):
    report_dir = tmp_path / "reports"
    bundle_dir = tmp_path / "bundles"
    report = report_dir / "report_1"
    report.mkdir(parents=True)
    (report / ReportingService.REPORT_NAME).write_text("<html></html>", encoding="utf-8")
    bundle_dir.mkdir(parents=True)
    (bundle_dir / "bundle_1.zip").write_bytes(b"zip")

    history = ReportingService.report_history(report_dir, bundle_dir)
    assert len(history) == 2
    assert set(history["type"]) == {"HTML report", "Reproducibility bundle"}
