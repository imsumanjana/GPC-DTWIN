"""Report, provenance, and reproducibility-bundle services."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import html
import json
import platform
from pathlib import Path
import re
import tempfile
from typing import Any, Iterable, Mapping
import zipfile

from matplotlib.figure import Figure
import matplotlib
import numpy as np
import pandas as pd

from gpc_dtwin import __version__
from gpc_dtwin.columns import COLUMN_LABELS, MODEL_RESPONSE_COLUMNS
from gpc_dtwin.figure_export import save_square_figure
from gpc_dtwin.metadata import (
    APP_NAME, COPYRIGHT_HOLDER, COPYRIGHT_TEXT, ORCID_ID, ORCID_URL,
)
from gpc_dtwin.services.audit_service import AuditService


@dataclass(frozen=True)
class ReportOptions:
    """User-selectable report content."""

    title: str = "Materials Analytics Report"
    project_label: str = "GPC-DTwin Project"
    prepared_by: str = COPYRIGHT_HOLDER
    include_figures: bool = True
    include_dataset_preview: bool = True
    include_artifact_inventory: bool = True
    preview_rows: int = 15


@dataclass
class ReportResult:
    report_directory: Path
    html_path: Path
    manifest_path: Path
    dataset_path: Path
    audit_path: Path
    figures: tuple[Path, ...]
    manifest: dict[str, Any]


@dataclass
class BundleResult:
    archive_path: Path
    manifest: dict[str, Any]
    file_count: int


@dataclass
class BundleVerificationResult:
    archive_path: Path
    valid: bool
    manifest: dict[str, Any]
    checks: pd.DataFrame


class ReportingService:
    """Create transparent reports and integrity-verifiable project bundles."""

    MANIFEST_NAME = "manifest.json"
    REPORT_NAME = "GPC_DTwin_Report.html"
    DATASET_NAME = "active_dataset.csv"
    AUDIT_NAME = "quality_findings.csv"
    BUNDLE_ROOT = "GPC_DTwin_Reproducibility_Bundle"

    @staticmethod
    def utc_now() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    @staticmethod
    def timestamp_slug() -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    @staticmethod
    def safe_name(value: str, fallback: str = "report") -> str:
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value).strip()).strip("._-")
        return cleaned or fallback

    @staticmethod
    def sha256_bytes(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @classmethod
    def sha256_file(cls, path: Path | str) -> str:
        path = Path(path)
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def canonical_csv_bytes(dataframe: pd.DataFrame) -> bytes:
        return dataframe.to_csv(
            index=False,
            lineterminator="\n",
            na_rep="",
        ).encode("utf-8")

    @classmethod
    def dataframe_fingerprint(cls, dataframe: pd.DataFrame) -> str:
        return cls.sha256_bytes(cls.canonical_csv_bytes(dataframe))

    @staticmethod
    def dataset_summary(dataframe: pd.DataFrame) -> dict[str, Any]:
        return {
            "records": int(len(dataframe)),
            "fields": int(len(dataframe.columns)),
            "mixes": int(dataframe["mix_id"].nunique()) if "mix_id" in dataframe else 0,
            "record_groups": int(dataframe["record_group"].nunique())
            if "record_group" in dataframe else 0,
        }

    @staticmethod
    def quality_summary(audit_issues: pd.DataFrame) -> dict[str, int]:
        summary = AuditService.summary(audit_issues)
        return {
            "critical": summary.critical,
            "warning": summary.warning,
            "information": summary.information,
            "total": summary.total,
        }

    @classmethod
    def artifact_inventory(
        cls,
        artifact_roots: Mapping[str, Path | str] | None,
    ) -> list[dict[str, Any]]:
        inventory: list[dict[str, Any]] = []
        if not artifact_roots:
            return inventory
        for category, root_value in artifact_roots.items():
            root = Path(root_value)
            if not root.exists():
                continue
            for path in sorted(root.rglob("*")):
                if not path.is_file() or path.name == ".gitkeep":
                    continue
                stat = path.stat()
                inventory.append({
                    "category": str(category),
                    "name": path.name,
                    "relative_path": path.relative_to(root).as_posix(),
                    "size_bytes": int(stat.st_size),
                    "modified_utc": datetime.fromtimestamp(
                        stat.st_mtime, tz=timezone.utc
                    ).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    "sha256": cls.sha256_file(path),
                })
        return inventory

    @classmethod
    def manifest_preview(
        cls,
        dataframe: pd.DataFrame,
        audit_issues: pd.DataFrame,
        options: ReportOptions | None = None,
        artifact_roots: Mapping[str, Path | str] | None = None,
    ) -> dict[str, Any]:
        options = options or ReportOptions()
        inventory = cls.artifact_inventory(artifact_roots) if options.include_artifact_inventory else []
        return {
            "schema": "gpc-dtwin-reproducibility-manifest-1",
            "application": {
                "name": APP_NAME,
                "version": __version__,
            },
            "attribution": {
                "copyright": COPYRIGHT_TEXT,
                "holder": COPYRIGHT_HOLDER,
                "orcid": ORCID_ID,
                "orcid_url": ORCID_URL,
            },
            "generated_utc": cls.utc_now(),
            "report": asdict(options),
            "environment": {
                "python": platform.python_version(),
                "platform": platform.platform(),
                "numpy": np.__version__,
                "pandas": pd.__version__,
                "matplotlib": matplotlib.__version__,
            },
            "dataset": {
                **cls.dataset_summary(dataframe),
                "sha256": cls.dataframe_fingerprint(dataframe),
            },
            "quality": {
                **cls.quality_summary(audit_issues),
                "sha256": cls.dataframe_fingerprint(audit_issues),
            },
            "stored_artifacts": {
                "count": len(inventory),
                "items": inventory,
            },
            "files": {},
        }

    @staticmethod
    def _new_figure() -> tuple[Figure, Any]:
        figure = Figure(figsize=(6.0, 6.0), constrained_layout=True)
        return figure, figure.add_subplot(111)

    @staticmethod
    def _empty_figure(message: str) -> Figure:
        figure, axis = ReportingService._new_figure()
        axis.text(0.5, 0.5, message, ha="center", va="center", wrap=True)
        axis.set_axis_off()
        return figure

    @classmethod
    def _status_figure(cls, dataframe: pd.DataFrame) -> Figure:
        if "data_status" not in dataframe or dataframe.empty:
            return cls._empty_figure("No data-status values are available")
        counts = dataframe["data_status"].fillna("UNSPECIFIED").astype(str).value_counts()
        figure, axis = cls._new_figure()
        axis.barh(range(len(counts)), counts.values)
        axis.set_yticks(range(len(counts)), counts.index)
        axis.invert_yaxis()
        axis.set_xlabel("Records (count)")
        axis.set_title("Data-status distribution")
        axis.grid(True, axis="x", alpha=0.25)
        return figure

    @classmethod
    def _coverage_figure(cls, dataframe: pd.DataFrame) -> Figure:
        fields = [field for field in MODEL_RESPONSE_COLUMNS if field in dataframe.columns]
        if not fields:
            return cls._empty_figure("No response fields are available")
        coverage = pd.Series({
            COLUMN_LABELS.get(field, field): int(pd.to_numeric(
                dataframe[field], errors="coerce"
            ).notna().sum())
            for field in fields
        }).sort_values()
        figure, axis = cls._new_figure()
        axis.barh(range(len(coverage)), coverage.values)
        axis.set_yticks(range(len(coverage)), coverage.index)
        axis.set_xlabel("Usable records (count)")
        axis.set_title("Measured-property coverage")
        axis.grid(True, axis="x", alpha=0.25)
        return figure

    @classmethod
    def _quality_figure(cls, audit_issues: pd.DataFrame) -> Figure:
        if audit_issues.empty or "severity" not in audit_issues:
            return cls._empty_figure("No quality findings are available")
        order = ["CRITICAL", "WARNING", "INFO"]
        counts = audit_issues["severity"].value_counts().reindex(order, fill_value=0)
        figure, axis = cls._new_figure()
        axis.bar(counts.index, counts.values)
        axis.set_ylabel("Findings (count)")
        axis.set_title("Quality findings by severity")
        axis.grid(True, axis="y", alpha=0.25)
        return figure

    @classmethod
    def _strength_figure(cls, dataframe: pd.DataFrame) -> Figure:
        required = {"ggbs_percent_numeric", "compressive_strength_mpa"}
        if not required.issubset(dataframe.columns):
            return cls._empty_figure("Compressive-strength values are unavailable")
        subset = dataframe.copy()
        if "record_group" in subset.columns:
            preferred = subset[subset["record_group"] == "AMBIENT_28D_MECHANICAL"]
            if not preferred.empty:
                subset = preferred
        subset = subset[[
            column for column in ("mix_id", "ggbs_percent_numeric", "compressive_strength_mpa")
            if column in subset.columns
        ]].copy()
        subset["ggbs_percent_numeric"] = pd.to_numeric(
            subset["ggbs_percent_numeric"], errors="coerce"
        )
        subset["compressive_strength_mpa"] = pd.to_numeric(
            subset["compressive_strength_mpa"], errors="coerce"
        )
        subset = subset.dropna(subset=["ggbs_percent_numeric", "compressive_strength_mpa"])
        if subset.empty:
            return cls._empty_figure("Compressive-strength values are unavailable")
        subset = subset.sort_values("ggbs_percent_numeric")
        figure, axis = cls._new_figure()
        axis.plot(
            subset["ggbs_percent_numeric"],
            subset["compressive_strength_mpa"],
            marker="o",
        )
        if "mix_id" in subset.columns:
            for _, row in subset.iterrows():
                axis.annotate(
                    str(row["mix_id"]),
                    (row["ggbs_percent_numeric"], row["compressive_strength_mpa"]),
                    xytext=(4, 5),
                    textcoords="offset points",
                    fontsize=8,
                )
        axis.set_xlabel("GGBS content (%)")
        axis.set_ylabel("Compressive strength (MPa)")
        axis.set_title("Compressive-strength profile")
        axis.grid(True, alpha=0.25)
        return figure

    @classmethod
    def create_report_figures(
        cls,
        dataframe: pd.DataFrame,
        audit_issues: pd.DataFrame,
        destination: Path | str,
    ) -> tuple[Path, ...]:
        destination = Path(destination)
        destination.mkdir(parents=True, exist_ok=True)
        builders = (
            ("data_status.png", cls._status_figure(dataframe)),
            ("property_coverage.png", cls._coverage_figure(dataframe)),
            ("quality_findings.png", cls._quality_figure(audit_issues)),
            ("strength_profile.png", cls._strength_figure(dataframe)),
        )
        paths: list[Path] = []
        for filename, figure in builders:
            paths.append(save_square_figure(figure, destination / filename))
        return tuple(paths)

    @staticmethod
    def _format_value(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, float):
            if np.isnan(value):
                return ""
            return f"{value:.6g}"
        return str(value)

    @classmethod
    def _dataframe_html(
        cls,
        dataframe: pd.DataFrame,
        max_rows: int = 15,
        max_columns: int = 12,
    ) -> str:
        if dataframe.empty:
            return '<p class="muted">No rows are available.</p>'
        subset = dataframe.head(max(1, int(max_rows))).iloc[:, :max_columns]
        headers = "".join(
            f"<th>{html.escape(COLUMN_LABELS.get(column, str(column)))}</th>"
            for column in subset.columns
        )
        body_rows = []
        for row in subset.itertuples(index=False, name=None):
            cells = "".join(
                f"<td>{html.escape(cls._format_value(value))}</td>" for value in row
            )
            body_rows.append(f"<tr>{cells}</tr>")
        return (
            '<div class="table-wrap"><table><thead><tr>' + headers +
            "</tr></thead><tbody>" + "".join(body_rows) + "</tbody></table></div>"
        )

    @classmethod
    def _render_html(
        cls,
        dataframe: pd.DataFrame,
        audit_issues: pd.DataFrame,
        manifest: dict[str, Any],
        options: ReportOptions,
        figure_paths: Iterable[Path],
    ) -> str:
        dataset = manifest["dataset"]
        quality = manifest["quality"]
        inventory = manifest["stored_artifacts"]["items"]
        statuses = dataframe.get("data_status", pd.Series(dtype=str)).fillna("UNSPECIFIED")
        status_rows = pd.DataFrame({
            "Data status": statuses.value_counts().index,
            "Records": statuses.value_counts().values,
        })
        group_rows = pd.DataFrame({
            "Record group": dataframe.get("record_group", pd.Series(dtype=str)).value_counts().index,
            "Records": dataframe.get("record_group", pd.Series(dtype=str)).value_counts().values,
        })
        inventory_frame = pd.DataFrame(inventory)
        figure_html = ""
        if figure_paths:
            cards = []
            for path in figure_paths:
                label = path.stem.replace("_", " ").title()
                cards.append(
                    f'<figure><img src="figures/{html.escape(path.name)}" alt="{html.escape(label)}">'
                    f"<figcaption>{html.escape(label)} · square 600 dpi export</figcaption></figure>"
                )
            figure_html = '<section><h2>Analytical figures</h2><div class="figure-grid">' + "".join(cards) + "</div></section>"

        preview_html = ""
        if options.include_dataset_preview:
            preview_html = (
                "<section><h2>Dataset preview</h2>"
                f"<p class=\"muted\">First {min(options.preview_rows, len(dataframe))} records and up to 12 fields.</p>"
                f"{cls._dataframe_html(dataframe, options.preview_rows, 12)}</section>"
            )

        inventory_html = ""
        if options.include_artifact_inventory:
            inventory_html = (
                "<section><h2>Stored artifact inventory</h2>"
                f"<p>{len(inventory)} files were indexed at report generation.</p>"
                f"{cls._dataframe_html(inventory_frame, 100, 6)}</section>"
            )

        return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(options.title)}</title>
<style>
:root {{ color-scheme: light; --ink:#172033; --muted:#5f6b7a; --line:#d8dee8; --panel:#f5f7fa; --accent:#3157d5; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; font-family:Segoe UI, Arial, sans-serif; color:var(--ink); background:#fff; line-height:1.55; }}
main {{ max-width:1180px; margin:0 auto; padding:44px 34px 30px; }}
header {{ border-bottom:3px solid var(--accent); padding-bottom:22px; margin-bottom:28px; }}
h1 {{ margin:0 0 7px; font-size:34px; }}
h2 {{ margin-top:30px; font-size:23px; }}
h3 {{ margin-top:22px; }}
.meta {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:12px; margin-top:18px; }}
.meta div, .metric {{ background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:13px 15px; }}
.metrics {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:12px; }}
.metric strong {{ display:block; font-size:25px; }}
.muted {{ color:var(--muted); }}
.table-wrap {{ overflow:auto; border:1px solid var(--line); border-radius:9px; }}
table {{ border-collapse:collapse; width:100%; min-width:640px; font-size:13px; }}
th,td {{ padding:9px 10px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }}
th {{ background:var(--panel); position:sticky; top:0; }}
.figure-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(350px,1fr)); gap:22px; }}
figure {{ margin:0; border:1px solid var(--line); border-radius:12px; padding:12px; }}
figure img {{ display:block; width:100%; height:auto; aspect-ratio:1/1; object-fit:contain; }}
figcaption {{ color:var(--muted); font-size:12px; margin-top:8px; }}
code {{ overflow-wrap:anywhere; }}
footer {{ margin-top:42px; padding-top:18px; border-top:1px solid var(--line); color:var(--muted); font-size:13px; }}
@media print {{ main {{ max-width:none; padding:18mm; }} .table-wrap {{ overflow:visible; }} }}
</style>
</head>
<body><main>
<header>
<h1>{html.escape(options.title)}</h1>
<p>{html.escape(options.project_label)}</p>
<div class="meta">
<div><b>Prepared by</b><br>{html.escape(options.prepared_by)}</div>
<div><b>Generated</b><br>{html.escape(manifest['generated_utc'])}</div>
<div><b>Software</b><br>{APP_NAME} v{html.escape(__version__)}</div>
<div><b>Dataset SHA-256</b><br><code>{html.escape(dataset['sha256'])}</code></div>
</div>
</header>
<section>
<h2>Project summary</h2>
<div class="metrics">
<div class="metric"><strong>{dataset['records']}</strong>Records</div>
<div class="metric"><strong>{dataset['fields']}</strong>Fields</div>
<div class="metric"><strong>{dataset['mixes']}</strong>Material mixes</div>
<div class="metric"><strong>{dataset['record_groups']}</strong>Measurement groups</div>
<div class="metric"><strong>{quality['total']}</strong>Quality findings</div>
<div class="metric"><strong>{manifest['stored_artifacts']['count']}</strong>Stored artifacts</div>
</div>
</section>
<section><h2>Data coverage</h2>{cls._dataframe_html(group_rows, 100, 2)}</section>
<section><h2>Data status</h2>{cls._dataframe_html(status_rows, 100, 2)}</section>
<section>
<h2>Quality summary</h2>
<div class="metrics">
<div class="metric"><strong>{quality['critical']}</strong>Critical</div>
<div class="metric"><strong>{quality['warning']}</strong>Warning</div>
<div class="metric"><strong>{quality['information']}</strong>Information</div>
</div>
{cls._dataframe_html(audit_issues, options.preview_rows, 8)}
</section>
{figure_html}
{preview_html}
{inventory_html}
<section>
<h2>Reproducibility information</h2>
<p>The accompanying manifest records the software version, environment, fingerprints, report options, stored-artifact inventory, and file checksums.</p>
<p><b>Python:</b> {html.escape(manifest['environment']['python'])}<br>
<b>Platform:</b> {html.escape(manifest['environment']['platform'])}<br>
<b>Dataset fingerprint:</b> <code>{html.escape(dataset['sha256'])}</code></p>
</section>
<footer>
{html.escape(COPYRIGHT_TEXT)}<br>
ORCID: <a href="{html.escape(ORCID_URL)}">{html.escape(ORCID_ID)}</a>
</footer>
</main></body></html>"""

    @classmethod
    def _write_csv(cls, dataframe: pd.DataFrame, path: Path) -> None:
        path.write_bytes(b"\xef\xbb\xbf" + cls.canonical_csv_bytes(dataframe))

    @classmethod
    def generate_report_directory(
        cls,
        dataframe: pd.DataFrame,
        audit_issues: pd.DataFrame,
        destination: Path | str,
        options: ReportOptions | None = None,
        artifact_roots: Mapping[str, Path | str] | None = None,
    ) -> ReportResult:
        options = options or ReportOptions()
        if dataframe.empty:
            raise ValueError("A report requires at least one data record.")
        destination = Path(destination)
        destination.mkdir(parents=True, exist_ok=True)
        figures_dir = destination / "figures"
        dataset_path = destination / cls.DATASET_NAME
        audit_path = destination / cls.AUDIT_NAME
        html_path = destination / cls.REPORT_NAME
        manifest_path = destination / cls.MANIFEST_NAME

        cls._write_csv(dataframe, dataset_path)
        cls._write_csv(audit_issues, audit_path)
        figure_paths: tuple[Path, ...] = ()
        if options.include_figures:
            figure_paths = cls.create_report_figures(dataframe, audit_issues, figures_dir)

        manifest = cls.manifest_preview(dataframe, audit_issues, options, artifact_roots)
        html_text = cls._render_html(dataframe, audit_issues, manifest, options, figure_paths)
        html_path.write_text(html_text, encoding="utf-8")

        files = [dataset_path, audit_path, html_path, *figure_paths]
        manifest["files"] = {
            path.relative_to(destination).as_posix(): {
                "size_bytes": int(path.stat().st_size),
                "sha256": cls.sha256_file(path),
            }
            for path in files
        }
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return ReportResult(
            report_directory=destination,
            html_path=html_path,
            manifest_path=manifest_path,
            dataset_path=dataset_path,
            audit_path=audit_path,
            figures=figure_paths,
            manifest=manifest,
        )

    @classmethod
    def create_bundle(
        cls,
        dataframe: pd.DataFrame,
        audit_issues: pd.DataFrame,
        destination: Path | str,
        options: ReportOptions | None = None,
        artifact_roots: Mapping[str, Path | str] | None = None,
    ) -> BundleResult:
        destination = Path(destination)
        if destination.suffix.lower() != ".zip":
            destination = destination.with_suffix(".zip")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="gpc_dtwin_bundle_") as temporary:
            report_root = Path(temporary) / cls.BUNDLE_ROOT
            result = cls.generate_report_directory(
                dataframe,
                audit_issues,
                report_root,
                options,
                artifact_roots,
            )
            readme = report_root / "README.txt"
            readme.write_text(
                "GPC-DTwin reproducibility bundle\n\n"
                "Open GPC_DTwin_Report.html in a web browser.\n"
                "Use manifest.json to verify file fingerprints and environment details.\n\n"
                f"{COPYRIGHT_TEXT}\nORCID: {ORCID_URL}\n",
                encoding="utf-8",
            )
            result.manifest["files"]["README.txt"] = {
                "size_bytes": int(readme.stat().st_size),
                "sha256": cls.sha256_file(readme),
            }
            result.manifest_path.write_text(
                json.dumps(result.manifest, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            if destination.exists():
                destination.unlink()
            with zipfile.ZipFile(
                destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
            ) as archive:
                for path in sorted(report_root.rglob("*")):
                    if path.is_file():
                        archive.write(
                            path,
                            (Path(cls.BUNDLE_ROOT) / path.relative_to(report_root)).as_posix(),
                        )
        with zipfile.ZipFile(destination, "r") as archive:
            file_count = len([name for name in archive.namelist() if not name.endswith("/")])
        return BundleResult(destination, result.manifest, file_count)

    @classmethod
    def verify_bundle(cls, archive_path: Path | str) -> BundleVerificationResult:
        archive_path = Path(archive_path)
        if not archive_path.exists():
            raise FileNotFoundError(archive_path)
        checks: list[dict[str, Any]] = []
        manifest: dict[str, Any] = {}
        with zipfile.ZipFile(archive_path, "r") as archive:
            manifest_candidates = [
                name for name in archive.namelist()
                if name == cls.MANIFEST_NAME or name.endswith("/" + cls.MANIFEST_NAME)
            ]
            if len(manifest_candidates) != 1:
                checks.append({
                    "path": cls.MANIFEST_NAME,
                    "status": "INVALID",
                    "expected_sha256": "",
                    "actual_sha256": "",
                    "message": "Exactly one manifest.json file is required.",
                })
                return BundleVerificationResult(
                    archive_path, False, manifest, pd.DataFrame(checks)
                )
            manifest_name = manifest_candidates[0]
            manifest = json.loads(archive.read(manifest_name).decode("utf-8"))
            prefix = Path(manifest_name).parent
            for relative, expected in manifest.get("files", {}).items():
                archive_name = (prefix / relative).as_posix()
                if archive_name not in archive.namelist():
                    checks.append({
                        "path": relative,
                        "status": "MISSING",
                        "expected_sha256": expected.get("sha256", ""),
                        "actual_sha256": "",
                        "message": "File is not present in the archive.",
                    })
                    continue
                payload = archive.read(archive_name)
                actual_hash = cls.sha256_bytes(payload)
                actual_size = len(payload)
                expected_hash = str(expected.get("sha256", ""))
                expected_size = int(expected.get("size_bytes", -1))
                valid = actual_hash == expected_hash and actual_size == expected_size
                checks.append({
                    "path": relative,
                    "status": "MATCH" if valid else "MISMATCH",
                    "expected_sha256": expected_hash,
                    "actual_sha256": actual_hash,
                    "message": "Fingerprint and size match." if valid else "Fingerprint or size differs.",
                })
        frame = pd.DataFrame(checks)
        valid = bool(not frame.empty and frame["status"].eq("MATCH").all())
        return BundleVerificationResult(archive_path, valid, manifest, frame)

    @classmethod
    def report_history(cls, report_dir: Path | str, bundle_dir: Path | str) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        report_dir = Path(report_dir)
        bundle_dir = Path(bundle_dir)
        if report_dir.exists():
            for directory in sorted(report_dir.iterdir(), reverse=True):
                if directory.is_dir() and (directory / cls.REPORT_NAME).exists():
                    rows.append({
                        "type": "HTML report",
                        "name": directory.name,
                        "path": str(directory / cls.REPORT_NAME),
                        "modified_utc": datetime.fromtimestamp(
                            directory.stat().st_mtime, tz=timezone.utc
                        ).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    })
        if bundle_dir.exists():
            for path in sorted(bundle_dir.glob("*.zip"), reverse=True):
                rows.append({
                    "type": "Reproducibility bundle",
                    "name": path.name,
                    "path": str(path),
                    "modified_utc": datetime.fromtimestamp(
                        path.stat().st_mtime, tz=timezone.utc
                    ).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                })
        return pd.DataFrame(rows, columns=["type", "name", "path", "modified_utc"])
