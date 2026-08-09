# GPC-DTwin v1.2.2 Validation Summary

## Scope

Version 1.2.2 integrates predictive ranking, Digital Twin selection, 3D response visualization, and physics-informed specimen calculations while retaining the existing data, analytics, NDT, durability, optimization, active-learning, reporting, and publication-graphics workspaces.

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
