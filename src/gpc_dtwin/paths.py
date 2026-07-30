"""Filesystem paths for local and packaged execution."""

from __future__ import annotations
import sys
from pathlib import Path


def repository_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def bundled_root() -> Path:
    bundle = getattr(sys, "_MEIPASS", None)
    return Path(bundle) if bundle else repository_root()


REPO_ROOT = repository_root()
BUNDLED_ROOT = bundled_root()
REFERENCE_DATASET = BUNDLED_ROOT / "data" / "reference" / "GPC_Reference_Dataset.csv"
TEMPLATE_DATASET = BUNDLED_ROOT / "data" / "templates" / "GPC_Dataset_Template.csv"
RUNTIME_DIR = REPO_ROOT / "data" / "runtime"
DATABASE_PATH = RUNTIME_DIR / "gpc_dtwin_v04.sqlite3"
EXPORT_DIR = REPO_ROOT / "exports"
MODEL_DIR = REPO_ROOT / "models" / "trained"
TWIN_DIR = REPO_ROOT / "models" / "twins"
