# GPC-DTwin v1.2.6

GPC-DTwin is a release-ready desktop platform for structured geopolymer-concrete data management,
quality checking, visual analytics, statistical analysis, predictive modelling, uncertainty-aware
digital twins, interactive 3D exploration, non-destructive-test fusion, durability assessment,
multi-objective optimization, inverse material design, active learning, and reproducible reporting.

## Workspaces

1. **Overview** — dataset coverage, performance indicators, and quality status.
2. **Data Explorer** — a unified four-tab workspace containing Data Explorer, Quality Check, Visual Analysis, and Statistical Analysis.
3. **Predictive Models** — seven-model grouped cross-validation, fold stability, dynamic ranking/status, diagnostics, and saved models.
4. **Digital Twin** — inherits the matching predictive-model ranking, recommends rank #1, adds empirical uncertainty, domain support, reliability, batch estimates, and response maps.
5. **3D Explorer** — visualizes the active Digital Twin without retraining and provides theory-based physics-informed specimen fields.
6. **NDT & Durability** — matched NDT fusion, exposure ranking, scenario estimates, and response curves.
7. **Optimization** — Pareto trade-offs, constraints, compromise ranking, and inverse design.
8. **Active Learning** — experiment recommendation, compatible plan export, saved runs, and model-update comparison.
9. **Reports & Provenance** — HTML reports, fingerprints, manifests, bundles, and integrity verification.
10. **Settings** — appearance, local storage, attribution, application checks, and folder access.

The Data Explorer tabs share the same active dataset and refresh automatically after import, editing, verification, or replacement.

## Compact result toolbars

Major analytical result areas now use one horizontally scrollable row containing metrics, selectors,
and icon-only actions. Export, save, and related commands retain descriptive tooltips and accessible
names without consuming a second or third row. If the window is narrow, the toolbar scrolls instead
of wrapping or compressing controls.

Full-width tab separator lines have been removed application-wide. Only the short selected-tab accent
remains, preserving orientation without drawing a line across the workspace.

## Universal parameter compatibility

Every response-driven workflow evaluates selected parameters against rows where the chosen response is available. Parameters with no usable overlapping values are excluded automatically, the analysis continues with valid inputs, and a warning lists every excluded field. This policy applies to statistical regression, predictive models, digital twins, 3D response surfaces, durability estimators, optimization surrogates, and active-learning surrogates. Requested, used, and omitted fields are retained in result metadata where applicable.

Regression also deduplicates grouping fields before grouped cross-validation, preventing duplicate two-dimensional group arrays and the former `object too deep for desired array` failure.

## First-class FA–GGBS–SF binder composition

FA (%), GGBS (%), and SF (%) are one shared binder-composition group across analytics, Predictive Models, Digital Twin, 3D Explorer, Optimization, and Active Learning. The bundled reference study uses SF = 10% for every mix, but SF is still retained as a normal predictor and visible scenario input. Future datasets containing multiple SF levels automatically use those values in model fitting and expose SF as a response-map/3D sweep axis without any code or schema change. In Digital Twin and 3D response-space exploration, the three binder percentages are compositionally coupled. A binder/non-binder pair uses an explicit Balance binder. A two-binder 2D surface is enabled only when the fitted data contain two independent binder-composition directions; otherwise it is blocked because such a surface would be dominated by extrapolation. When supported, the third binder is derived from `FA + GGBS + SF = 100%` and impossible compositions are masked rather than predicted.

## Selectable figure quality

Every manual figure export opens a square-export preview and quality selector. Available resolutions are 150, 300, 600, 1200, and 2400 dpi. The 6 × 6 inch canvas therefore produces raster images from 900 × 900 through 14400 × 14400 pixels. Batch figure-tab export asks for the common format and quality once before saving all tabs. Automated report figures retain the documented default of 600 dpi.

## Publication graphics system

Version 1.2.1 retains the application-wide, icon-driven chart presentation system:

- one compact palette icon on every Matplotlib chart;
- Times New Roman as the default chart typeface;
- built-in Publication Colour, Publication Monochrome, Presentation, High Contrast, and Minimal presets;
- custom named presets stored locally;
- persistent chart, workspace, and application style scopes;
- advanced legend placement, including outside and custom anchored positions;
- editable typography, lines, markers, axes, ticks, grids, colours, colour maps, and layout spacing;
- export preview with clipping-risk guidance;
- reset-to-workspace and reset-all-style controls without adding chart menus to the main menu bar.

See `docs/CHART_APPEARANCE.md` and `docs/PUBLICATION_GRAPHICS.md`.

## Figure tabs and export

- Multi-figure outputs use non-stretching, reorderable tabs.
- Each tab keeps one full-size figure visible at a time.
- Figure groups provide compact expand, export-current, and export-all controls.
- Figure hosts scroll when their natural minimum size exceeds the available area.
- Digital Twin response maps use a fixed square 720 × 720 pixel display host with horizontal and vertical scrolling as required.
- Every user-triggered figure export opens a quality popup with 150, 300, 600, 1200, and 2400 dpi options while retaining a square 6 × 6 inch canvas.
- PNG and TIFF output is 3600 × 3600 pixels.
- PNG, PDF, SVG, TIFF, and TIF are supported where offered.

## Interface behavior

- Collapsible navigation adapts to narrower windows.
- All workspaces support horizontal and vertical scrolling.
- Dense control panels retain readable natural sizes instead of being compressed.
- Top actions remain accessible through a horizontally scrollable action strip.
- Window geometry, theme, last workspace, and chart styles persist between sessions.
- Light and dark themes use consistent focus, table, tab, splitter, and scrollbar styling.
- Workspace identity appears once in the main top bar; duplicate page-level title blocks are removed.
- No rule is drawn above tab rows; a single low-contrast baseline remains below each tab row.


## Units, fixed colour scales, and comparison tabs

Version 1.2.1 makes visual comparisons explicit and reproducible. Engineering units are carried into chart axes and colour bars wherever a physical quantity is shown. Digital Twin response maps retain a fixed colour normalization from the fitted twin, while Physics-Informed Specimen fields use a shared scale across compatible mixes rather than independently rescaling M1, M2, and subsequent specimens. Fixed natural bounds are used for percentage and dimensionless utilisation/damage fields.

The Predictive Models workspace now presents **Comparison table** and **Ranking chart** as peer result tabs. Digital Twin > Build and calibrate similarly presents **Calibration table** and **Response charts** as peer tabs, keeping large tables and charts full-width and easier to inspect.

## Integrated Prediction → Digital Twin → 3D workflow

GPC-DTwin 1.2.1 uses one shared registry of seven regression algorithms. Predictive Models is the
authoritative benchmarking stage: it evaluates all seven algorithms with the same grouped validation
splits, records fold variability, creates a dynamic ranking, and publishes that result to the application
context. The ranking leader is marked **Recommended** for that exact response and predictor setup.

Digital Twin accepts a matching ranking, selects rank #1 by default, and keeps all seven models
selectable with their current rank and one-word validation status. It adds an algorithm-independent
out-of-fold residual uncertainty interval, nearest-training distance, fitted-range checks, and A/B/C/D
reliability. Dataset or verification-state changes invalidate stale shared model state.

The 3D Response Surface consumes the active twin directly and never fits a separate surrogate. Every
numeric active-twin predictor is exposed as a response-space axis, including SF when the present fitted
range is 10–10%. Axis limits initialize from the fitted data; flat ranges require an explicit user-defined
exploration span. Binder axes enforce FA + GGBS + SF = 100%, using an automatically derived third
component or a user-selected Balance binder, and invalid compositions are left blank instead of being
predicted. Valid extrapolative points retain the Digital Twin reliability/extrapolation flags. The second 3D view is now **Physics-Informed Specimen**: the former sinusoidal synthetic cube is
removed and replaced by explicit compression, splitting-tensile, flexural-bending, and acid-diffusion
fields with field-source and capacity-source provenance.

See `docs/MODELING.md`, `docs/DIGITAL_TWIN.md`, and `docs/THREE_D_EXPLORER.md`.

## Predictive-model input compatibility

Predictors are evaluated against the selected response before model fitting. Fields with no usable
response-overlapping values are disabled in the interface and omitted safely if they remain selected.
The result summary and saved model metadata record every omitted predictor. Valid predictors continue
through grouped cross-validation without forcing unrelated durability, NDT, or exposure fields into a
mechanical-property model.

## Optimization predictor compatibility

Each objective, constraint, or target receives a response-specific surrogate. When a selected input is
blank for one response family but valid for another, GPC-DTwin automatically omits it only from the
unsupported surrogate. The Surrogate validation table records the used and omitted predictors. This
allows mixed mechanical-property searches without forcing unrelated test fields into every model.

## Native Windows stability

- PyQt6 and the Qt runtime are pinned to matching 6.11.0 builds.
- The tested dependency stack is preserved in `requirements-lock.txt`.
- Ensemble models use one worker for deterministic desktop execution and clean native shutdown.
- Software rendering is enabled by default to avoid graphics-driver-dependent failures.
- Chart canvases are discovered by a safe timer instead of an application-wide native event filter.
- Chart helpers detach before Qt and Matplotlib widget destruction.
- Python fault diagnostics are enabled for all launch threads.
- Native launch details are written to `.runtime/native-crash.log`.
- Exit code `-1073741819` is reported explicitly as a Windows access violation.

## Data safety and storage

- Replacing the active dataset creates an automatic SQLite backup first.
- Manual database backup and restore are available from the File menu.
- Packaged builds store writable data under `%LOCALAPPDATA%\GPC-DTwin` by default.
- Source checkouts remain portable and store writable data in the repository folder.
- `GPC_DTWIN_HOME` can define a custom writable location.
- Logs rotate automatically in the local `logs` folder.

## Windows setup

```powershell
Set-Location "D:\GPC-DTwin"
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\run.ps1
```

Python 3.11, 3.12, or 3.13 is supported. `requirements-lock.txt` preserves the tested Windows release stack.

## Validation

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\test.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\ui_check.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\release_check.ps1
```

The interface check opens all 10 primary workspaces and all four Data Explorer tabs at 1024 × 720, 1366 × 768, and 1920 × 1080. It checks
scroll containers, chart-style icons, reorderable figure tabs, non-stretching tab behavior, figure
action controls, readable chart dimensions, and optional screenshots.

## Windows build

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1
```

The build includes the application icon, Windows version metadata, bundled datasets, documentation,
and required analytical libraries. `RELEASE_MANIFEST.sha256` lists the SHA-256 fingerprint of each
source release file.

## macOS ARM64 build

The GitHub Actions workflow `.github/workflows/build-macos.yml` builds the Apple-silicon `.app` and DMG on `macos-26`. It installs the pinned release dependencies, runs tests and self-checks, freezes from `src/gpc_dtwin/app.py`, bundles the reference/template datasets plus resources/docs/licence files, verifies the Cocoa Qt plugin, runs the frozen-app self-check, verifies the DMG, and uploads the DMG with its SHA-256 checksum.

The source workflow does not embed Apple Developer ID credentials; signing/notarization can be added separately when those credentials are available.

## Copyright and attribution

Copyright © 2026 Dr. Suman Jana. All rights reserved.

ORCID: https://orcid.org/0000-0002-9850-2169
