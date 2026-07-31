# GPC-DTwin v1.0.1

GPC-DTwin is a release-ready desktop platform for structured geopolymer-concrete data management,
quality checking, visual analytics, statistical analysis, predictive modelling, uncertainty-aware
digital twins, interactive 3D exploration, non-destructive-test fusion, durability assessment,
multi-objective optimization, inverse material design, active learning, and reproducible reporting.

## Workspaces

1. **Overview** — dataset coverage, performance indicators, and quality status.
2. **Data Explorer** — searchable records, filters, verification states, and CSV exchange.
3. **Quality Check** — deterministic consistency, completeness, and range checks.
4. **Visual Analytics** — mechanical, workability, NDT, durability, and heatmap views.
5. **Statistical Analysis** — descriptive statistics, correlations, group comparison, and regression.
6. **Predictive Models** — grouped cross-validation, algorithm comparison, diagnostics, and saved models.
7. **Digital Twin** — prediction intervals, reliability classes, batch estimates, and response maps.
8. **3D Explorer** — response surfaces, uncertainty landscapes, reliability terrain, and estimated specimen fields.
9. **NDT & Durability** — matched NDT fusion, exposure ranking, scenario estimates, and response curves.
10. **Optimization** — Pareto trade-offs, constraints, compromise ranking, and inverse design.
11. **Active Learning** — experiment recommendation, compatible plan export, saved runs, and model-update comparison.
12. **Reports & Provenance** — HTML reports, fingerprints, manifests, bundles, and integrity verification.
13. **Settings** — appearance, local storage, attribution, application checks, and folder access.

## Release interface

- Collapsible navigation automatically adapts to narrower windows.
- All workspaces are enclosed in horizontal and vertical scroll areas.
- Dense control panels retain readable natural sizes instead of being compressed.
- Top actions remain accessible through a horizontally scrollable action strip.
- Window geometry, theme, and last workspace are preserved between sessions.
- A three-resolution offscreen interface check is included for release validation.
- Light and dark themes use consistent focus, disabled, table, tab, splitter, and scrollbar styling.

## Figure export

Every figure export uses a square 6 × 6 inch canvas at exactly 600 dpi. PNG and TIFF output is
3600 × 3600 pixels. PNG, PDF, SVG, TIFF, and TIF are supported where offered. Interactive figure
sizes are restored after export.

## Data safety and storage

- Replacing the active dataset creates an automatic SQLite backup first.
- Manual database backup and restore are available from the File menu.
- Packaged builds store writable data under `%LOCALAPPDATA%\GPC-DTwin` by default.
- Source checkouts remain portable and store writable data in the repository folder.
- `GPC_DTWIN_HOME` can define a custom writable location.
- Logs rotate automatically in the local `logs` folder.

## Windows setup

```powershell
Set-Location "D:\GPC-DTwin-v1.0.1"
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\run.ps1
```

Python 3.11, 3.12, or 3.13 is supported.

## Validation

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\test.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\ui_check.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\release_check.ps1
```

The interface check opens all 13 workspaces at 1024 × 720, 1366 × 768, and 1920 × 1080 and can
capture screenshots for review.

## Windows build

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1
```

The build includes application icon and Windows version metadata, bundled datasets, documentation,
and required analytical libraries. `RELEASE_MANIFEST.sha256` lists the SHA-256 fingerprint of every
source release file.

## Copyright and attribution

Copyright © 2026 Dr. Suman Jana. All rights reserved.

ORCID: https://orcid.org/0000-0002-9850-2169
