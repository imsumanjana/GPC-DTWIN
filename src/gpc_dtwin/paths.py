"""Filesystem paths for source, portable, and packaged execution."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from gpc_dtwin.metadata import APP_NAME


def repository_root() -> Path:
    """Return the source checkout or executable folder."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def bundled_root() -> Path:
    """Return the read-only resource root used by PyInstaller."""
    bundle = getattr(sys, "_MEIPASS", None)
    return Path(bundle) if bundle else repository_root()


def user_data_root() -> Path:
    """Return a writable application-data root.

    Source checkouts remain portable by default. Packaged builds use LocalAppData,
    avoiding permission failures when the executable is installed in a protected folder.
    GPC_DTWIN_HOME can override the location for managed or portable installations.
    """
    override = os.environ.get("GPC_DTWIN_HOME", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    if not getattr(sys, "frozen", False):
        return repository_root()
    local = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if local:
        return Path(local) / APP_NAME
    return Path.home() / f".{APP_NAME.lower()}"


INSTALL_ROOT = repository_root()
BUNDLED_ROOT = bundled_root()
APP_DATA_ROOT = user_data_root()

REFERENCE_DATASET = BUNDLED_ROOT / "data" / "reference" / "GPC_Reference_Dataset.csv"
TEMPLATE_DATASET = BUNDLED_ROOT / "data" / "templates" / "GPC_Dataset_Template.csv"
ICON_PATH = BUNDLED_ROOT / "resources" / "GPC-DTwin.ico"
ICON_PNG_PATH = BUNDLED_ROOT / "resources" / "GPC-DTwin.png"

RUNTIME_DIR = APP_DATA_ROOT / "data" / "runtime"
DATABASE_PATH = RUNTIME_DIR / "gpc_dtwin.sqlite3"
LEGACY_DATABASE_PATHS = (
    RUNTIME_DIR / "gpc_dtwin_v09.sqlite3",
    INSTALL_ROOT / "data" / "runtime" / "gpc_dtwin_v09.sqlite3",
)
EXPORT_DIR = APP_DATA_ROOT / "exports"
BUNDLE_DIR = EXPORT_DIR / "bundles"
BACKUP_DIR = APP_DATA_ROOT / "backups"
LOG_DIR = APP_DATA_ROOT / "logs"
UI_CHECK_DIR = APP_DATA_ROOT / "ui-check"
MODEL_ROOT = APP_DATA_ROOT / "models"
MODEL_DIR = MODEL_ROOT / "trained"
TWIN_DIR = MODEL_ROOT / "twins"
NDT_DIR = MODEL_ROOT / "ndt"
DURABILITY_DIR = MODEL_ROOT / "durability"
OPTIMIZATION_DIR = MODEL_ROOT / "optimizations"
ACTIVE_LEARNING_DIR = MODEL_ROOT / "active_learning"
REPORT_DIR = APP_DATA_ROOT / "reports"

WRITABLE_DIRECTORIES = (
    RUNTIME_DIR, EXPORT_DIR, BUNDLE_DIR, BACKUP_DIR, LOG_DIR, UI_CHECK_DIR,
    MODEL_DIR, TWIN_DIR, NDT_DIR, DURABILITY_DIR, OPTIMIZATION_DIR,
    ACTIVE_LEARNING_DIR, REPORT_DIR,
)


def ensure_user_directories() -> None:
    """Create all writable application folders."""
    for directory in WRITABLE_DIRECTORIES:
        directory.mkdir(parents=True, exist_ok=True)
