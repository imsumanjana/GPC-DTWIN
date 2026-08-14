# GPC-DTwin 1.2.6 Release Notes

Copyright © 2026 Dr. Suman Jana. All rights reserved.  
ORCID: https://orcid.org/0000-0002-9850-2169


## Response-surface geometry correction

Version 1.2.6 prevents misleading triangular/extrapolation-dominated response surfaces when the fitted binder data do not span two independent composition directions.

- Stores the empirical rank of the FA–GGBS–SF composition cloud in each newly built Digital Twin.
- The bundled reference data have one binder-composition degree of freedom because SF is 10% while FA and GGBS trade off; a two-binder 2D surface is therefore disabled for this dataset rather than rendered as a mostly unsupported simplex.
- SF remains a first-class selectable predictor. It can be paired with an independently varying process/condition predictor and can be explored beyond 10% only by entering an explicit range; reliability still flags extrapolation.
- Chooses a supported default surface automatically. With the reference compressive-strength twin this is GGBS (%) × AAS:B ratio when both are fitted predictors, while FA is derived by closure and SF is held at 10%.
- Future datasets with genuine independent SF variation automatically obtain binder-composition rank 2, at which point two-binder composition surfaces become available.
- Removes the generic invalid-composition warning from ordinary one-binder response surfaces; an explicit blocking explanation is shown only when the selected axis pair is unsupported.
- Filters the 3D observation overlay to the same fitted cross-section as the surface, so observations from different ages, curing regimes, or other held predictor values are not plotted on an unrelated response slice.

## Composition-aware response space

Version 1.2.5 enforces the physical binder closure `FA + GGBS + SF = 100%` whenever binder percentages are explored in Digital Twin Response Maps or the 3D Response Surface.

- With two binder axes, the third binder is derived automatically at every grid point.
- With one binder axis and one non-binder axis, a **Balance binder** selector determines which second binder changes while the third binder stays at its fitted default.
- Compositionally impossible points are masked, exported as `composition_valid = False`, assigned no prediction, and shown as blank regions rather than being passed to the surrogate model.
- Response-grid exports preserve all three binder percentages plus the closure rule, derived/balance binder, and valid/invalid point counts.
- 3D Explorer reports valid/total grid nodes so triangular or clipped composition domains are explicit.
- Flat fitted ranges such as current-reference SF = 10–10% now produce a non-blocking warning and keep Build/Generate disabled until the user enters a genuine exploration span.
- Custom/legacy twins that do not contain all three binder predictors continue to work, but their response view states that binder closure is not enforceable until FA, GGBS, and SF are all included.

## FA–GGBS–SF first-class binder composition

Version 1.2.5 makes silica fume visibly and structurally equivalent to fly ash and GGBS throughout the analytics pipeline.

- Introduces one shared FA/GGBS/SF binder-composition definition used by modelling, Digital Twin, optimisation, active learning, analytics, reporting, and 3D provenance.
- Keeps `SF (%)` in the default Predictive Models input set even when the current reference dataset contains only 10% SF.
- Keeps SF in saved model/twin metadata, prediction scenarios, feature-influence tables/charts, training ranges, and binder provenance.
- Adds a dedicated FA–GGBS–SF binder-composition chart.
- Updates 28-day strength and UPV analytical charts to show the response together with FA, GGBS, and SF rather than presenting GGBS alone.
- Updates report strength graphics to include all three binder components.
- Makes Statistical Analysis regression defaults include FA, GGBS, and SF together.
- Shows active FA/GGBS/SF composition in Digital Twin and 3D Explorer provenance.
- Retains the current fitted SF value/range (10%, 10–10%) without disabling or removing SF.
- Exposes SF in Digital Twin Response Maps and the 3D Response Surface even when the fitted SF range is currently 10–10%.
- Adds editable X/Y exploration minimum and maximum controls. A flat fitted parameter such as SF starts at 10–10%; the user can explicitly expand the exploration interval when a what-if sweep is required.
- Keeps all extrapolative SF sweep points inside the existing Digital Twin domain/reliability checks instead of silently treating them as in-domain evidence.
- Future imported datasets with genuine SF variation automatically populate the fitted SF limits, so no manual range expansion is needed.

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
