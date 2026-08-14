# Digital Twin

The Digital Twin workspace converts the validated predictive-model ranking into an **uncertainty-aware, domain-aware material-response model**. It no longer maintains a separate Gaussian-Process/Forest-only model family.

## Required Predictive Modelling result

Before a new twin can be built, run Predictive Modelling for the same:

- response;
- effective predictors;
- active dataset;
- review-record policy;
- grouping configuration.

The Digital Twin model selector is populated from that ranking. Rank #1 is selected automatically and shown as **Recommended**. The user can override the recommendation and select any of the other six models; its rank and dynamic status remain visible.

## What the twin adds to the point predictor

For the selected ranked algorithm the twin refits the shared model pipeline and adds:

1. **Cross-validated empirical uncertainty** from out-of-fold residuals;
2. **Prediction intervals** at the selected confidence level;
3. **Distance adjustment** when a requested point is remote from observed training cases;
4. **Nearest-training distance** in transformed predictor space;
5. **Outside-range detection** for numeric predictors;
6. **A/B/C/D reliability classification** combining uncertainty and experimental support.

The interval implementation is algorithm-independent, so Linear Regression, Ridge, Elastic Net, SVR, Random Forest, Gradient Boosting, and Extra Trees can all be used as the prediction engine.

## Build and calibrate

Calibration uses grouped cross-validation by mix whenever enough mix groups are available. Reported outputs include:

- selected algorithm, prediction rank, and dynamic status;
- RMSE, MAE, and R²;
- empirical interval coverage;
- mean interval width;
- normalized RMSE;
- calibration gap;
- number of usable observations.

The calibration table retains observed response, out-of-fold predicted mean, residual, prediction standard deviation, lower and upper bounds, interval width, and whether the observation falls within the interval.

## Scenario and batch prediction

Single-scenario and batch outputs include:

- estimated response;
- prediction uncertainty;
- lower and upper bounds;
- interval width and relative uncertainty;
- nearest-data distance;
- outside-range count and fields;
- reliability class A–D;
- plain-language reliability reason.

A indicates close experimental support with comparatively low uncertainty. D indicates extrapolation, remote support, or high uncertainty. Reliability is a decision-support indicator and does not replace laboratory testing.

## Response maps

Response maps vary two compatible numeric predictors across their fitted ranges while holding other predictors at fitted defaults. They can display:

- estimated response;
- relative uncertainty;
- prediction interval width;
- reliability.

The response-map host is a fixed square 720 × 720 pixels and becomes scrollable when required. Exports remain square at 6 × 6 inches with selectable 150–2400 dpi quality.

The map engine stores explicit row and column coordinates before reshaping predictions. It supports up to 100 × 100 grids and exposes every finite numeric predictor used by the active twin. Axis limits initialize from fitted ranges; when a fitted range is flat, the user must explicitly enter a nonzero exploration span before generation.

### Binder-composition closure

When any FA (%), GGBS (%), or SF (%) predictor is used as a response-view axis, the current twin treats the three binder fractions as a composition rather than independent percentages. If only one binder component is an axis, the **Balance binder** selector chooses which second binder absorbs the change while the remaining binder is held at its fitted default. A two-binder 2D map is enabled only when the fitted binder compositions span two independent directions. With the bundled reference data, SF is fixed at 10% and FA/GGBS provide only one independent direction, so two-binder 2D maps are blocked rather than rendered as extrapolation-dominated triangles. Future data with independent SF variation automatically enable such maps; the third binder is then derived as `100 - X - Y`, and physically impossible points are masked before prediction.

## Twin hand-off to 3D Explorer

When a twin is built or loaded, it is published as the **active twin artifact**. The 3D Response Surface consumes that artifact directly. It does not refit another model and does not offer an independent model-method selector.

## Saved twins

Saved twin files use Joblib with matching JSON metadata. New-format metadata records the selected prediction algorithm, prediction rank/status, empirical uncertainty method, training-domain information, and validation metrics. Legacy Gaussian Process / Forest Ensemble artifacts can still be loaded for backward compatibility, but new twins are created from the shared seven-model architecture.

## Calibration result tabs and fixed map scales (v1.2.1)

The Build and calibrate workspace presents the calibration table and response charts as peer tabs rather than a compressed side-by-side splitter. Response-map colour limits are stored with the fitted twin, providing consistent colour meaning across alternative response-map axis selections.


## Validated upstream prerequisite (v1.2.2)

Digital Twin is a downstream workflow and is enabled only after Predictive Models has completed a validated model comparison. On entry, the response, usable predictor set, and review-record policy are inherited directly from that comparison and displayed read-only. Changing these modelling inputs therefore requires returning to Predictive Models and validating the new configuration. The **Prediction** and **Response maps** tabs are enabled only after a twin has been built or loaded.

FA, GGBS, and SF remain part of the inherited binder composition whenever they were validated upstream. In the bundled reference dataset the fitted SF range is 10–10%, but `SF (%)` is still exposed in the response-map axis selectors just like FA and GGBS. Its axis limits initially show 10–10%; an explicit nonzero exploration range is required for a what-if sweep, and points outside the fitted range retain the Digital Twin extrapolation/reliability warnings. If future data provide a wider SF range, those fitted limits are used automatically.
