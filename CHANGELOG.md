# Change Log

## Version 1.0.1

- Added compatibility with pandas 3.x when measured values are entered into exported active-learning experiment plans.
- Replaced Windows file-level SQLite restoration with SQLite's native backup API.
- Added regression coverage for editable numeric result fields and database restoration.
- Filtered a specific upstream joblib/NumPy 2.5 deprecation warning during automated tests.
- Updated package, executable, report, and release metadata to version 1.0.1.

## Version 1.0.0

- Finalized the thirteen-workspace release interface.
- Added adaptive collapsible navigation and horizontally scrollable top actions.
- Preserved theme, window geometry, navigation state, and last workspace.
- Added application icon, Windows file metadata, and improved light/dark styling.
- Added writable per-user storage for packaged builds and portable storage for source runs.
- Added stable database naming with automatic migration from the latest pre-release database.
- Added automatic backup before dataset replacement and manual database backup/restore.
- Added rotating diagnostic logs and a global error dialog with local log location.
- Added local application health checks.
- Added automated multi-resolution interface checking and optional screenshot capture.
- Added release-check and improved Windows-build scripts.
- Retained square 6 × 6 inch, 600 dpi figure export across every analytical workspace.
- Retained scrollable workspaces and dense panels so content is not compressed unnecessarily.

Copyright © 2026 Dr. Suman Jana. All rights reserved.

ORCID: https://orcid.org/0000-0002-9850-2169
