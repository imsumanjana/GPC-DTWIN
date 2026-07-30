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
- PyQt6 window loading through the GUI smoke test

The scripts use repository-local temporary storage under `.runtime`.

## Digital twin checks

- grouped cross-validation and interval generation,
- prediction bounds and coverage calculations,
- scenario and batch prediction,
- response-map generation,
- reliability-class assignment,
- artifact save, load, listing, and deletion.
