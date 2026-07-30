# Changelog

## 0.1.2 — Windows pytest temporary-directory permission fix

- Fixed `PermissionError: [WinError 5] Access is denied` under
  `AppData\Local\Temp\pytest-of-<user>`.
- Setup and test scripts now use repository-local writable temporary directories.
- Added a `tests/conftest.py` fallback so direct pytest runs also use local temp storage.
- Removed duplicate pytest configuration from `pyproject.toml`.
- Setup now captures and validates each native process exit code before reporting success.
- Runtime temporary files are excluded through `.gitignore`.

## 0.1.1 — Windows Python runtime detection fix

- Fixed `setup.ps1` terminating before fallback when Python 3.12 was not installed.
- Added safe detection of Python 3.11, 3.12, and 3.13.
- Added clear installation guidance when no supported runtime is available.
- Added automatic cleanup of an incomplete `.venv`.
- Added exit-code checks for virtual-environment creation, dependency installation, and tests.

## v0.1.0 — Foundation and Data Audit

- Added modern PyQt6 application shell with sidebar navigation.
- Added dark and light themes.
- Added automatic first-run import of the bundled experimental dataset.
- Added SQLite persistence for all 44 dataset columns.
- Added searchable and filterable experimental database page.
- Added verification-status updates without modifying source CSV files.
- Added deterministic audit rules and severity summaries.
- Added dashboard charts and metrics.
- Added eight analytical chart modes and publication-image export.
- Added CSV database export.
- Added Windows setup, run, test, and build scripts.
- Added service-layer and optional GUI smoke tests.
