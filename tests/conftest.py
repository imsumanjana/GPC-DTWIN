from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
RUNTIME_TEMP = ROOT / ".runtime" / "pytest-python-temp"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

RUNTIME_TEMP.mkdir(parents=True, exist_ok=True)
os.environ["TEMP"] = str(RUNTIME_TEMP)
os.environ["TMP"] = str(RUNTIME_TEMP)
os.environ["TMPDIR"] = str(RUNTIME_TEMP)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
tempfile.tempdir = str(RUNTIME_TEMP)
