# Change Log

## Version 1.1.3

- Consolidated Data Explorer, Quality Check, Visual Analysis, and Statistical Analysis into four tabs.
- Reduced the primary navigation from thirteen pages to ten workspaces.
- Added navigation-index migration for existing user settings.
- Added response-aware predictor availability in Predictive Models.
- Automatically omits response-incompatible predictors and records them in metadata.
- Added regression tests for the unified data workspace and predictive-model correction.

## Version 1.1.2

- Removed duplicate page-level title and subtitle blocks from all thirteen workspaces.
- Kept the main top bar as the single workspace header.
- Removed the unwanted top rule above tab rows.
- Restored a subtle lower tab-row baseline.
- Preserved selected-tab accents and all square, scrollable figure behavior.
- Added source and GUI regression checks for the corrected hierarchy.

## Version 1.1.1

- Removed the unsupported `QEvent.Type.Destroy` enum access.
- Added runtime-safe Qt event-type discovery.
- Hardened chart-overlay positioning during native widget teardown.
- Added a regression test for PyQt6 event-enum compatibility.
- Updated release and Windows executable metadata to 1.1.1.

## Version 1.1.0

- Added application-wide chart, workspace, and application style persistence.
- Added five built-in publication and presentation presets plus custom named presets.
- Added advanced legend anchoring, typography, palette, axis-margin, colour-bar, and layout controls.
- Added export preview with fixed-dimension metadata and clipping-risk guidance.
- Added reorderable, non-stretching figure tabs with expand, export-current, and export-all actions.
- Added reset-to-workspace and reset-all-style controls while keeping chart controls icon-driven.
- Removed the full-width horizontal line beneath tab bars throughout the interface.
- Added a fixed square, scrollable Digital Twin response-map presentation.
- Added response-specific predictor adaptation for Optimization and inverse-design surrogates.
- Added used-predictor and omitted-predictor reporting in surrogate validation.
- Replaced application-wide native chart event filtering with timer-based canvas discovery.
- Added orderly chart-helper shutdown, software rendering, native fault logging, matching PyQt/Qt pins, and a tested dependency lock.
- Switched ensemble fitting to a single worker to avoid native thread-pool teardown conflicts.
- Reused Optimization canvases to avoid queued-paint callbacks into deleted widgets.
- Retained square 6 × 6 inch, 600 dpi figure export and all 1.0.2 response-map corrections.

## Version 1.0.2

- Repaired response-map shape handling with explicit grid row and column coordinates.
- Added one-dimensional response curves for twins with only one varying numeric predictor.
- Added tabbed calibration, response-map, model-diagnostic, active-learning, and inverse-design figures.
- Added application-wide icon-driven chart styling with Times New Roman defaults.
- Added editable legends, typography, lines, markers, axes, ticks, grids, colours, and backgrounds.
- Refined tab separators and preserved natural interface dimensions through scrollable containers.
- Added regression tests for 100 × 100 maps, constant-axis rejection, chart styling, and tabbed-figure service outputs.

## Version 1.0.1

- Added compatibility with pandas 3.x when measured values are entered into exported active-learning experiment plans.
- Replaced Windows file-level SQLite restoration with SQLite's native backup API.
- Added regression coverage for editable numeric result fields and database restoration.
- Filtered a specific upstream Joblib/NumPy deprecation warning during automated tests.

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
