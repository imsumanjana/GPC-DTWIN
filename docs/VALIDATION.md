# Validation

Run the complete test suite with:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\test.ps1
```

The automated checks cover:

- CSV schema and numeric conversion
- SQLite import, retrieval, export, and status update
- deterministic quality findings
- analytical figure generation
- descriptive statistics, correlation, ANOVA, and regression
- multi-model comparison and grouped cross-validation
- batch and single-scenario prediction
- model save, load, listing, and deletion
- uncertainty-aware twin calibration and response maps
- 3D surface and specimen-field generation
- NDT matching and input-set comparison
- NDT scenario prediction and model persistence
- durability metrics, ranking, heatmaps, and score calculation
- durability estimator prediction intervals, response curves, and persistence
- active-learning recommendations, plans, persistence, and closed-loop comparison
- square 600 dpi figure export and canvas restoration
- PyQt6 window loading and scroll-container checks through the GUI smoke test

The scripts use repository-local temporary storage under `.runtime`.

## NDT checks

- destructive-reference filtering,
- matching by mix identity,
- five input-set comparisons,
- leave-one-mix-out validation,
- observed-versus-estimated and residual figures,
- scenario reliability and fitted-range checks,
- model save, load, listing, and deletion.

## Durability checks

- derivation of strength retention and mass change,
- configurable score normalization,
- descending condition ranking,
- initial-versus-residual and heatmap figures,
- uncertainty-aware estimator fitting,
- scenario bounds and reliability,
- one-variable response curves,
- estimator save, load, listing, and deletion.

## Optimization checks

Automated checks cover:

- constraint-aware Pareto search,
- binder closure at 100%,
- population and candidate accounting,
- inverse-design ranking,
- target satisfaction fields,
- reliability classes,
- run save, load, list, and delete operations,
- Pareto, profile, and inverse-design figures.

## Active-learning checks

Automated checks cover:

- candidate generation within selected bounds,
- binder closure at 100%,
- uncertainty, expected-improvement, novelty, and acquisition fields,
- diversity-aware recommendation ranking,
- compatible plan export with blank measured responses,
- model-update comparison after additional usable records,
- run save, load, list, and delete operations,
- acquisition, priority-profile, and update figures.

## Figure and interface checks

The export test verifies a 3600 × 3600 pixel PNG with approximately 600 dpi metadata and confirms
that the interactive figure dimensions are restored. Source scanning ensures figure actions route
through the common square-export helper. The GUI smoke test confirms twelve scroll-wrapped pages.

