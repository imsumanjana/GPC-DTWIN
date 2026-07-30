# GPC-DTwin v0.4

GPC-DTwin is a desktop platform for structured geopolymer-concrete data management,
quality checking, visual analytics, statistical analysis, predictive modeling, and
uncertainty-aware digital twins.

## Main workspaces

- **Overview** — dataset coverage, performance indicators, and quality status.
- **Data Explorer** — searchable records, filters, verification states, and CSV exchange.
- **Quality Check** — deterministic consistency, completeness, and range checks.
- **Visual Analytics** — mechanical, workability, NDT, durability, and heatmap views.
- **Statistical Analysis** — descriptive statistics, correlations, group comparison, and regression.
- **Predictive Models** — grouped cross-validation, algorithm comparison, diagnostics, and saved models.
- **Digital Twin** — calibrated prediction intervals, reliability classes, batch estimates, and response maps.
- **Settings** — appearance, storage paths, and active dataset information.

## Digital twin methods

Two uncertainty-aware methods are included:

1. **Gaussian Process** — probabilistic response estimation with model-based uncertainty.
2. **Forest Ensemble** — tree-ensemble estimation with empirical prediction intervals.

Each twin stores its fitted preprocessing, estimator, input ranges, calibration metrics,
confidence level, training-domain distances, and dataset fingerprint.

## Windows setup

```powershell
Set-Location "D:\GPC-DTwin-v0.4"
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\run.ps1
```

Python 3.11, 3.12, or 3.13 is supported. Setup creates `.venv`, installs the application,
and runs non-GUI tests using repository-local temporary storage.

## Validation

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\test.ps1
```

## Local storage

- Active database: `data/runtime/gpc_dtwin_v04.sqlite3`
- Predictive models: `models/trained`
- Digital twins: `models/twins`
- Exports: `exports`
- Temporary files: `.runtime`

The bundled reference dataset and blank template follow the same 44-field CSV schema.
Imported files are copied into the local database; source CSV files are not modified.
