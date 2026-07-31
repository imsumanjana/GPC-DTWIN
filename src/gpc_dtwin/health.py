"""Local application health checks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
import tempfile

from matplotlib.figure import Figure

from gpc_dtwin.columns import DATA_COLUMNS
from gpc_dtwin.figure_export import save_square_figure
from gpc_dtwin.paths import (
    DATABASE_PATH, REFERENCE_DATASET, TEMPLATE_DATASET, WRITABLE_DIRECTORIES,
    ensure_user_directories,
)
from gpc_dtwin.services.data_service import DataService


@dataclass(frozen=True)
class HealthCheckItem:
    name: str
    passed: bool
    detail: str


def run_health_check(database_path: Path | str = DATABASE_PATH) -> list[HealthCheckItem]:
    """Run non-destructive checks of resources, storage, schema, and figure export."""
    items: list[HealthCheckItem] = []
    ensure_user_directories()

    try:
        from PyQt6.QtCore import PYQT_VERSION_STR, QT_VERSION_STR, qVersion
        runtime = qVersion()
        matched = runtime == QT_VERSION_STR
        items.append(HealthCheckItem(
            "Qt runtime", matched,
            f"PyQt {PYQT_VERSION_STR} · compiled Qt {QT_VERSION_STR} · runtime Qt {runtime}",
        ))
    except ModuleNotFoundError:
        # Service-only validation environments may not include Qt. The Windows
        # release check executes this item after the pinned GUI dependencies install.
        pass
    except Exception as error:
        items.append(HealthCheckItem("Qt runtime", False, str(error)))

    for label, path in (("Reference dataset", REFERENCE_DATASET), ("CSV template", TEMPLATE_DATASET)):
        items.append(HealthCheckItem(label, path.is_file(), str(path)))

    try:
        frame = DataService.load_csv(REFERENCE_DATASET)
        passed = list(frame.columns) == DATA_COLUMNS and len(frame) > 0
        items.append(HealthCheckItem(
            "Reference schema", passed, f"{len(frame)} records · {len(frame.columns)} fields"
        ))
    except Exception as error:
        items.append(HealthCheckItem("Reference schema", False, str(error)))

    unwritable = []
    for directory in WRITABLE_DIRECTORIES:
        try:
            directory.mkdir(parents=True, exist_ok=True)
            probe = directory / ".write-check"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
        except Exception:
            unwritable.append(str(directory))
    items.append(HealthCheckItem(
        "Writable storage", not unwritable,
        "All application folders are writable" if not unwritable else "; ".join(unwritable),
    ))

    try:
        path = Path(database_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as connection:
            connection.execute("PRAGMA quick_check")
        items.append(HealthCheckItem("Database access", True, str(path)))
    except Exception as error:
        items.append(HealthCheckItem("Database access", False, str(error)))

    try:
        with tempfile.TemporaryDirectory() as temporary:
            figure = Figure(figsize=(4, 3), dpi=100)
            axis = figure.add_subplot(111)
            axis.plot([0, 1], [0, 1])
            output = save_square_figure(figure, Path(temporary) / "check.png")
            items.append(HealthCheckItem("Figure export", output.is_file(), "Square 600 dpi export"))
    except Exception as error:
        items.append(HealthCheckItem("Figure export", False, str(error)))
    return items


def health_check_text(items: list[HealthCheckItem]) -> str:
    lines = []
    for item in items:
        mark = "PASS" if item.passed else "FAIL"
        lines.append(f"{mark}  {item.name}: {item.detail}")
    return "\n".join(lines)
