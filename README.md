# GPC-DTwin v0.8

GPC-DTwin is a desktop platform for structured geopolymer-concrete data management, quality
checking, visual analytics, statistical analysis, predictive modelling, uncertainty-aware digital
twins, interactive 3D exploration, non-destructive-test fusion, durability assessment,
multi-objective optimization, inverse material design, and uncertainty-guided experiment selection.

## Main workspaces

- **Overview** — dataset coverage, performance indicators, and quality status.
- **Data Explorer** — searchable records, filters, verification states, and CSV exchange.
- **Quality Check** — deterministic consistency, completeness, and range checks.
- **Visual Analytics** — mechanical, workability, NDT, durability, and heatmap views.
- **Statistical Analysis** — descriptive statistics, correlations, group comparison, and regression.
- **Predictive Models** — grouped cross-validation, algorithm comparison, diagnostics, and saved models.
- **Digital Twin** — calibrated prediction intervals, reliability classes, batch estimates, and response maps.
- **3D Explorer** — interactive response surfaces, uncertainty landscapes, reliability terrain, and estimated specimen fields.
- **NDT & Durability** — matched NDT fusion, exposure ranking, scenario estimates, and response curves.
- **Optimization** — Pareto trade-offs, engineering constraints, compromise ranking, and inverse design.
- **Active Learning** — experiment recommendation, compatible plan export, saved runs, and model-update comparison.
- **Settings** — appearance, storage paths, and active dataset information.

## Active learning

The Active Learning workspace fits an uncertainty-aware surrogate and ranks candidate material
scenarios using one of four acquisition strategies:

- maximum uncertainty,
- expected improvement,
- confidence bound,
- balanced exploration.

Latin-hypercube candidate generation, optional binder closure, distance from existing designs, and
diversity-aware selection are included. Recommended scenarios retain prediction intervals,
reliability classes, acquisition scores, and existing-design distance. A compatible experiment-plan
CSV keeps measured response fields blank so estimated values are not stored as observations.

Completed compatible records can be appended without replacing the active dataset. The closed-loop
comparison reports validation metrics before and after the newly measured records become usable.

## Figure export

Every figure export uses a square 6 × 6 inch canvas at 600 dpi. PNG, PDF, SVG, TIFF, and TIF are
supported where offered by the workspace. Raster exports are 3600 × 3600 pixels. The on-screen
interactive figure size is restored after export.

## Responsive interface

Application pages and dense control panels use scroll containers. When the available area is smaller
than the natural content size, horizontal or vertical scrollbars appear instead of compressing controls,
tables, or figures into an unreadable layout.

## Windows setup

```powershell
Set-Location "D:\GPC-DTwin-v0.8"
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\run.ps1
```

Python 3.11, 3.12, or 3.13 is supported. Setup creates `.venv`, installs the application, and runs
non-GUI tests using repository-local temporary storage.

## Validation

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\test.ps1
```

## Local storage

- Active database: `data/runtime/gpc_dtwin_v08.sqlite3`
- Predictive models: `models/trained`
- Digital twins: `models/twins`
- NDT models: `models/ndt`
- Durability estimators: `models/durability`
- Optimization and inverse-design runs: `models/optimizations`
- Active-learning runs: `models/active_learning`
- Exports: `exports`
- Temporary files: `.runtime`

The bundled reference dataset and blank template follow the same 44-field CSV schema. Imported
files are copied into the local database; source CSV files are not modified.
