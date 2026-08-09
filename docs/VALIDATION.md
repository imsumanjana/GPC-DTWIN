# Validation

Run the complete Windows validation suite with:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\test.ps1
```

The suite covers service calculations, persistence, export, reporting, GUI smoke checks, and multi-resolution interface checks using repository-local temporary storage.

The automated checks cover:

- schema loading, database persistence, backup, and restore;
- deterministic quality checks;
- analytics and statistical calculations;
- seven-model predictive comparison, fold variability, dynamic status, and persistence;
- Prediction → Digital Twin ranking hand-off and manual model override;
- uncertainty-aware Digital Twin estimates and reliability;
- 3D active-twin response surfaces without retraining;
- physics-informed compression, splitting-tensile, flexural, and acid specimen calculations;
- NDT fusion and durability assessment;
- optimization and inverse design;
- active-learning recommendations and update comparison;
- square figure export with selectable 150–2400 dpi quality;
- report generation, dataset fingerprinting, bundle creation, and integrity verification;
- ten scrollable primary workspaces plus four Data Explorer tabs;
- adaptive navigation at common window sizes.

For a screenshot-based interface review:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\ui_check.ps1
```

For final release verification:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\release_check.ps1
```

The macOS GitHub Actions workflow additionally validates the pinned ARM64 dependency stack, runs source and frozen-app self-checks, verifies bundled data/templates, verifies the DMG, and emits a SHA-256 checksum.
