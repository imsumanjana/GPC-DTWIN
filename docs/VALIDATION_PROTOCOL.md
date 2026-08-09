# Validation Protocol

## Data ingestion and audit

- Confirm the required 44-column schema.
- Confirm unique, non-empty record identifiers.
- Confirm source rows are imported without changing the bundled reference CSV.
- Recalculate durability percentages from source masses and strengths where applicable.
- Surface conflicting verification states, missing provenance, invalid negatives, and composition inconsistencies.

## Predictive Modelling validation

- Use grouped cross-validation by `mix_id` whenever at least three groups are available.
- Confirm all seven shared algorithms are evaluated with the same fold splits.
- Retain out-of-fold predictions and residuals.
- Report overall RMSE, MAE, R², MAPE plus fold-level mean/standard deviation metrics.
- Confirm rank #1 receives the dynamic status `Recommended`.
- Confirm other model-status labels are generated from current validation results, not hard-coded by algorithm.
- Confirm incompatible predictors are omitted and recorded.

## Prediction-to-twin hand-off

- Confirm Digital Twin accepts only a matching Prediction result.
- Confirm the ranking leader is selected by default.
- Confirm all seven ranked models remain selectable with rank/status labels.
- Confirm manual override uses the selected model and does not alter the Prediction ranking.
- Confirm changing/importing/restoring data or verification status invalidates the shared ranking/twin state.

## Digital Twin validation

- Confirm the selected shared model pipeline is refitted to all usable records after cross-validation.
- Confirm uncertainty derives from out-of-fold residual behavior and is available for all seven algorithms.
- Confirm interval coverage and width are reported.
- Confirm nearest-training distance and training-range violations are retained.
- Confirm reliability A–D responds to uncertainty and domain support.
- Confirm batch and single-scenario outputs contain the same provenance fields.

## 3D response validation

- Confirm Response Surface requires an active twin.
- Confirm it uses the exact active twin artifact and does not retrain a new model.
- Confirm estimated response, uncertainty, interval-width, and reliability surfaces use the same grid coordinates.
- Confirm observation overlays are displayed only from available experimental information.

## Physics-informed specimen validation

- Compression cube: verify `P/A` nominal stress and utilisation against the supplied bulk capacity.
- Splitting cylinder: verify `2P/(πLD)` nominal tensile relation and cylindrical point mask.
- Flexural beam: verify third-point bending moment and `σ = My/I`, neutral axis, and maximum utilisation.
- Acid cube: verify diffusion field is bounded and surface penetration exceeds core penetration for positive exposure time; when calibration data exist, verify volume-average retention matches the measured global retention.
- Confirm every field records geometry, field source, capacity source, and assumptions.
- Confirm no synthetic sine-wave specimen field remains.

## Packaging validation

### Windows

- Install the pinned release dependency stack.
- Run non-GUI tests and UI audit.
- Bundle datasets, templates, resources, documentation, licences, Matplotlib, scikit-learn, and required SciPy submodules.

### macOS ARM64

- Use the pinned `requirements-lock.txt` stack on the `macos-26` ARM64 runner.
- Verify Python package integrity with `pip check`.
- Verify PyQt/Qt runtime compatibility and ARM64 architecture.
- Run non-GUI tests and the source application self-check.
- Build from `src/gpc_dtwin/app.py` with `src` on the PyInstaller path.
- Bundle reference data, template data, resources, docs, copyright, and licence notice.
- Collect Matplotlib/scikit-learn data and SciPy submodules needed by the frozen app.
- Run the frozen `.app --self-check` before DMG creation.
- Verify the DMG and generate a SHA-256 checksum.

## GUI acceptance

- All workspaces open without exceptions.
- Scrollable layouts retain readable controls at supported window sizes.
- Charts render and quality-selectable export succeeds.
- Model/twin status changes are reflected in dependent workspaces.
- Theme, window geometry, sidebar state, and chart-style settings persist.
