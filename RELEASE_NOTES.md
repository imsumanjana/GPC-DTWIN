# GPC-DTwin 1.2.2 Release Notes

Copyright © 2026 Dr. Suman Jana. All rights reserved.  
ORCID: https://orcid.org/0000-0002-9850-2169

## Validated workflow hand-off and gating

Version 1.2.2 tightens the Prediction → Digital Twin → 3D workflow.

- Predictive Models remains the authoritative seven-model validation stage.
- Digital Twin is disabled until a successful model comparison exists.
- When unlocked, Digital Twin inherits the exact validated response, usable predictors, and review-record setting from Predictive Models instead of recreating the configuration from defaults.
- The ranked-model selector therefore immediately shows the seven validated models and their dynamic statuses without a false “No matching validated ranking” condition.
- Digital Twin Prediction and Response maps remain locked until a twin is built or loaded.
- 3D Explorer remains locked until an active Digital Twin exists.
- Predictive Models point-prediction options remain locked until a fitted model exists.
- Feature influence table and feature influence chart are now separate result tabs.

## Visualization consistency and result tabs

Version 1.2.1 adds a comparison-safe visual layer without changing the validated predictive architecture.

- Engineering units are shown on physical chart axes and colour bars; response-derived quantities such as prediction, residual, RMSE increase, uncertainty, and interval width inherit the response unit.
- Digital Twin response-map colour scales are stored with the fitted twin, so changing X/Y response-map variables no longer reinterprets the same colour.
- Physics-Informed Specimen fields use one scale across compatible mixes. Switching M1, M2, M3, etc. therefore changes colour according to the real calculated magnitude instead of rescaling each specimen independently.
- Dimensionless utilisation/damage fields and percentage fields use fixed physical bounds.
- In Predictive Models, the model-comparison table and ranking chart are peer result tabs.
- In Digital Twin > Build and calibrate, the calibration table and response charts are peer result tabs.

## Integrated predictive-model architecture

Version 1.2.1 removes the former disconnect between Predictive Models, Digital Twin, and 3D Explorer.

- Adds a shared seven-model registry for Linear Regression, Ridge Regression, Elastic Net, Support Vector Regression, Random Forest, Gradient Boosting, and Extra Trees.
- Makes Predictive Models the authoritative benchmarking stage.
- Adds fold-level RMSE, MAE, and R² mean/variation alongside the existing out-of-fold metrics.
- Adds data-derived one-word model status: Recommended, Competitive, Stable, Moderate, Mixed, Uncertain, or Weak.
- Publishes the latest matching ranking through `ApplicationContext`.
- Invalidates stale ranking/twin state whenever active experimental data or record verification state changes.

## Rank-aware Digital Twin

- Removes the new-build Gaussian-Process/Forest-only twin selector.
- Selects the Predictive Models ranking leader by default.
- Keeps all seven ranked algorithms manually selectable with their current rank and dynamic status.
- Uses the same preprocessing and estimator definition as Predictive Models.
- Adds algorithm-independent empirical uncertainty from out-of-fold residual behavior.
- Retains confidence intervals, interval coverage, nearest-training distance, fitted-range checks, and A/B/C/D reliability.
- Preserves loading/prediction support for legacy Gaussian Process and Forest Ensemble artifacts.

## 3D Explorer correction

- Response Surface now consumes the active Digital Twin directly and never refits another model.
- Removes the independent 3D method selector.
- Retains estimated-response, relative-uncertainty, interval-width, reliability, mesh, contour, camera, observation-overlay, CSV, and figure export functions.

## Physics-Informed Specimen

The former normalized sinusoidal specimen field has been removed.

- Adds a 150 × 150 × 150 mm compression cube using nominal `P/A` stress and capacity utilisation.
- Adds a 150 mm diameter × 300 mm splitting-tensile cylinder using the nominal `2P/(πLD)` relation.
- Adds a 100 × 100 × 500 mm flexural beam with 400 mm span, symmetric third-point loading, and `σ = My/I` bending fields.
- Adds an acid-degradation cube using a finite-slab Fickian diffusion calculation.
- Calibrates global acid-strength retention to matching experimental initial/residual strength records when available.
- Records geometry, field source, capacity source, supporting records, and modelling assumptions so calculated fields are not confused with measured tomography or voxel data.

## Cross-workspace model consistency

Active Learning, Optimization, inverse design, and durability estimation now use the same shared seven-model Digital Twin service instead of referring to removed Gaussian Process / Forest Ensemble new-build methods. Random Forest is the standalone default in these workflows unless another shared model is selected.

## macOS ARM64 packaging

The GitHub Actions workflow is rebuilt for complete ARM64 packaging on `macos-26`.

- Installs the pinned `requirements-lock.txt` release stack and runs `pip check`.
- Verifies ARM64 architecture and matching PyQt/Qt runtime.
- Runs non-GUI tests and source self-check before freezing.
- Builds from `src/gpc_dtwin/app.py` with `src` on the PyInstaller path.
- Bundles reference data, template data, resources, documentation, copyright, and licence files.
- Collects Matplotlib and scikit-learn package data plus required SciPy submodules.
- Runs the frozen `.app --self-check` before creating the DMG.
- Verifies the DMG and generates SHA-256 output.
- Uses `actions/upload-artifact@v6`.

## Validation

Version 1.2.1 adds/updates regression coverage for:

- seven-model ranking stability/status;
- Prediction → Digital Twin hand-off;
- manual Digital Twin model override;
- active-twin 3D reuse without retraining;
- compression, splitting-tensile, flexural, and acid specimen fields;
- existing NDT, durability, optimization, and active-learning compatibility with the shared model family.
