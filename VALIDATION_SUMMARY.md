# GPC-DTwin v1.2.6 Validation Summary

## Scope

Version 1.2.6 retains the validated Prediction → Digital Twin → 3D architecture and the first-class FA–GGBS–SF composition model. Response-space exploration now also checks the empirical dimensionality of the fitted binder cloud so a 2D binder–binder surface is only rendered when the data support two independent composition directions.

## Core architecture checks

- Seven candidate algorithms are defined once in `services/model_registry.py`.
- Predictive Modelling evaluates all seven with shared cross-validation folds.
- Ranking output includes overall error, fold-level variability, rank, dynamic one-word status, and status explanation.
- Rank #1 is always marked `Recommended` for that specific comparison.
- Digital Twin receives a matching Prediction result through `ApplicationContext` and defaults to its ranking leader.
- All seven ranked algorithms remain manually selectable.
- Dataset/status changes invalidate stale comparison/twin state.
- 3D Response Surface consumes the active Digital Twin artifact directly rather than fitting another surrogate.

## Digital Twin checks

- New twins use any shared prediction model rather than the former GP/Forest-only new-build path.
- Empirical uncertainty and intervals are derived from out-of-fold residual behavior for every supported algorithm.
- Distance adjustment, nearest-training distance, numeric range violations, and A/B/C/D reliability are retained.
- Scenario, batch, response-map, persistence, and calibration-figure paths are covered by service tests.
- Legacy Gaussian Process / Forest Ensemble artifacts retain load/prediction compatibility.

## Physics-informed specimen checks

- Compression cube: nominal `P/A` stress/utilisation is deterministic and spatially uniform under the stated ideal loading assumption.
- Splitting cylinder: nominal `2P/(πLD)` relation is implemented on a cylindrical geometry.
- Flexural beam: third-point moment distribution and `σ = My/I` produce the expected neutral axis and tension/compression field.
- Acid cube: finite-slab Fickian penetration produces stronger surface than core exposure for positive time; global strength loss can be calibrated to matching experimental residual-strength data.
- Every specimen result includes geometry, dimensions, field source, capacity source, supporting record count, and modelling assumptions.
- The former sine-wave synthetic specimen field is removed.

## Response-axis validation

- `map_axis_candidates()` now exposes every finite numeric predictor used by the active twin, including SF when its fitted range is 10–10%.
- Digital Twin Response Maps and 3D Response Surface provide editable X/Y minimum and maximum controls initialized from fitted ranges.
- A flat range is not silently expanded: an explicit nonzero exploration interval is required before generation.
- Explicit ranges outside fitted limits are recorded as extrapolative and continue through the existing outside-range and A/B/C/D reliability logic.
- Future datasets with varying SF use their actual fitted SF limits automatically.

## Packaging checks

### Windows

The Windows PyInstaller build continues to include bundled reference/template data, resources, documentation, copyright/licence files, Matplotlib, scikit-learn, and SciPy submodules using the pinned release environment.

### macOS ARM64

The GitHub Actions workflow now:

- uses `macos-26` ARM64 and Python 3.12;
- installs `requirements-lock.txt` and runs `pip check`;
- verifies ARM64 and matching PyQt/Qt versions;
- runs non-GUI tests and source self-check;
- builds from `src/gpc_dtwin/app.py` with `src` on the PyInstaller path;
- bundles `data/reference`, `data/templates`, `resources`, `docs`, copyright and licence notice;
- collects required Matplotlib/scikit-learn/SciPy content;
- runs the frozen application self-check before DMG creation;
- verifies the DMG and writes SHA-256 output;
- uploads with `actions/upload-artifact@v6`.

## Release test baseline

Service tests cover predictive modelling, Digital Twin, 3D/physics, Active Learning, NDT/durability, optimization/inverse design, reporting, storage, analytics, statistics, export, and release-source regressions. GUI-marked tests remain available for environments with a suitable Qt display/offscreen configuration.

## Version 1.2.1 visual-consistency validation

- Response-dependent figure labels inherit canonical engineering units.
- Digital Twin response maps retain fitted-twin colour scales across axis changes.
- Physics-Informed Specimen colour scales are locked across compatible mixes for the same field.
- Natural fixed scales are used for utilisation, damage, acid-penetration, and strength-retention fields.
- Predictive Models exposes separate Comparison table and Ranking chart tabs.
- Digital Twin Build and calibrate exposes separate Calibration table and Response charts tabs.
- Dedicated v1.2.1 visual-consistency tests were added and pass in the source test environment.


## Version 1.2.2 workflow validation

- Feature influence table and chart are separate peer result tabs.
- Digital Twin inherits the exact active Predictive Models response, usable predictors, and review-record policy, eliminating default-setting mismatch.
- Digital Twin navigation remains disabled until a validated Prediction comparison exists.
- Digital Twin Prediction and Response maps tabs remain disabled until an active twin exists.
- 3D Explorer navigation remains disabled until an active twin exists.
- Predictive Models point-prediction tab remains disabled until an active fitted model exists.
- Publishing a new Predictive Models ranking invalidates the previous active twin, preventing stale downstream visualisation.
- Dataset or verification-state invalidation automatically returns the UI to the nearest valid upstream workflow stage.

Focused v1.2.2 source/service validation: **32/32 tests passed** across modelling, Digital Twin, 3D/physics, visual-consistency, and workflow-gating suites. All source/test Python files were also syntax-compiled successfully. GUI-marked Qt tests remain intended for the packaged Windows/macOS or a PyQt6-enabled test environment.


## Version 1.2.5 binder-composition validation

- FA (%), GGBS (%), and SF (%) are defined centrally as one binder-composition group and are present in the default prediction inputs.
- The bundled reference dataset keeps SF = 10% in model fitting, feature influence, saved model metadata, Digital Twin metadata, prediction scenarios, and 3D provenance.
- The current SF fitted range is retained as 10–10%; SF is not disabled or removed from the model.
- A synthetic future dataset with multiple SF levels was used to verify that SF automatically appears as a Digital Twin response-map/3D axis.
- Visual Analytics now includes a dedicated FA–GGBS–SF composition chart and shows all three binder components alongside 28-day compressive strength and UPV.
- Statistical regression defaults now select FA, GGBS, and SF together.
- Report strength figures show compressive strength with all three binder components.

Focused v1.2.4 response-axis validation: **13/13 tests passed** across the SF/binder suite, 3D visualization service, flat-range Digital Twin response-map handling, and the dedicated response-axis visibility regression. All **86** source/test Python files syntax-compiled successfully. GUI-marked Qt tests remain intended for a PyQt6-enabled Windows/macOS environment.

## Version 1.2.5 composition-aware response validation

- Two-binder-axis grids derive the third binder exactly from closure.
- One-binder-axis grids/curves support an explicit balance binder while holding the remaining binder at its fitted default.
- Invalid compositions are masked before model evaluation and carry `composition_valid = False` with no predicted response.
- Valid grid rows preserve FA + GGBS + SF = 100% within numerical tolerance.
- The 3D Explorer consumes the same composition-aware Digital Twin grid and reports valid versus total grid nodes.
- Flat fitted ranges remain visible but cannot be built until the user enters a nonzero exploration span.


Focused v1.2.5 composition-aware validation: **25/25 relevant tests passed** across Digital Twin services, SF/response-axis behavior, composition-closure regressions, and 3D visualization. All **87** source/test Python files syntax-compiled successfully. The release manifest contains **147** verified source/release entries.

## Version 1.2.6 response-surface geometry validation

- New twins store `binder_composition_rank`, the numerical rank of the centered FA–GGBS–SF training compositions (maximum 2 under closure).
- The bundled reference twin correctly reports rank 1 because SF is 10% and FA/GGBS move along a single balance direction.
- Two-binder response maps/3D surfaces are blocked when binder rank is below 2, preventing the extrapolation-dominated triangular surface that previously appeared for FA × GGBS.
- `preferred_response_axes()` selects a supported rectangular cross-section; for the reference compressive-strength configuration it prefers GGBS (%) × AAS:B when both are active predictors.
- One-binder surfaces preserve closure with a balance binder and no invalid-composition triangle; for the reference GGBS × AAS:B view SF remains 10% and FA is derived.
- SF remains present in all response-axis selectors and can be paired with an independently varying non-binder predictor. Flat SF ranges still require a deliberate exploration interval.
- Future synthetic data with independently varying SF were verified to produce binder rank 2 and enable two-binder surfaces with the third binder derived by closure.
- 3D observed-point overlays are filtered to the same held-default cross-section as the response surface, preventing measurements from different age/curing/default conditions from being mixed onto one surface.

Focused v1.2.6 geometry/composition/SF-axis/response-axis validation: **19/19 tests passed**. Digital Twin service tests passed **8/8**, 3D visualization service tests passed **5/5**, and release-readiness/GUI-smoke/reporting tests passed **11/11**. All **88** source/test Python files syntax-compiled successfully. The release manifest contains **148** verified source/release entries.
