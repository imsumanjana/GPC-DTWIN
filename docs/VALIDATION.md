# Validation

Run the complete Windows validation suite with:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\test.ps1
```

This runs service, persistence, export, reporting, GUI smoke, and multi-resolution interface checks
using repository-local temporary storage.

The automated checks cover:

- schema loading, database persistence, backup, and restore,
- deterministic quality checks,
- analytics and statistical calculations,
- predictive-model comparison and persistence,
- uncertainty-aware digital-twin estimates,
- 3D response and specimen-field calculations,
- NDT fusion and durability assessment,
- optimization and inverse design,
- active-learning recommendations and update comparison,
- square figure export with selectable 150–2400 dpi quality,
- report generation and dataset fingerprinting,
- reproducibility-bundle creation and integrity verification,
- ten scrollable primary workspaces plus four Data Explorer tabs,
- adaptive navigation at common window sizes,
- readable button sizing and interface screenshot capture.

For a screenshot-based interface review:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\ui_check.ps1
```

For final release verification:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\release_check.ps1
```
## Version 1.1.1 regression checks

The suite verifies that active-learning plan response fields accept numeric values under pandas 3.x and that SQLite backup restoration succeeds on Windows without replacing an open database file.

