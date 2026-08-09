# NDT and Durability

## NDT fusion

NDT fusion combines non-destructive indicators with a user-selected destructive-strength reference.
The reference is controlled by record group, test age, and curing-text filter. Matching is performed by
mix identity, and repeated records are represented by their median values.

Five input sets are compared under the same regression algorithm:

1. UPV only
2. Rebound only
3. UPV and rebound
4. Binder composition only
5. Binder composition with NDT

The available algorithms are Ridge Regression, Support Vector Regression, Random Forest, and
Gradient Boosting. Leave-one-mix-out cross-validation is used when at least five distinct mixes are
matched. The first-ranked input set has the lowest cross-validated RMSE.

### NDT estimate reliability

- **A** — strong validation support and all required inputs inside the fitted ranges.
- **B** — moderate validation support inside the fitted ranges.
- **C** — limited support, a range boundary issue, or elevated validation error.
- **D** — missing input support, multiple range violations, or high validation error.

A saved NDT model contains the fitted pipeline, selected input set, reference condition, validation
metrics, input defaults, and fitted numeric ranges.

## Durability profile

Exposure records are used to calculate:

- strength retention,
- strength loss,
- signed and absolute mass change,
- mass-stability score,
- configurable durability score.

The default screening formula is:

`0.80 × strength retention + 0.20 × max(0, 100 − 10 × |mass change|)`

Both weights and the mass-change penalty are adjustable. Weights are normalized before the score is
calculated. The score supports transparent comparison only and is not a prescribed material standard.

## Durability estimator

The estimator supports these responses:

- residual compressive strength,
- strength loss,
- mass change,
- strength retention.

Default inputs include binder composition, initial compressive strength, exposure medium,
concentration, and exposure duration. The durability estimator uses the same seven shared regression
algorithms as the core prediction engine. Random Forest is the default standalone durability surrogate,
and any of the seven models may be selected. The common Digital Twin uncertainty layer supplies point
estimates, empirical prediction intervals, relative uncertainty, range checks, nearest-data distance, and
reliability classes.

Global cross-validation performance limits scenario reliability. An apparently close scenario is not
assigned a strong reliability class when the selected response has weak cross-validated accuracy.

## Response curve

A response curve varies one fitted numeric input across its calibrated range while other inputs remain
at the entered scenario values or fitted defaults. A curve is unavailable when the selected input has
only one calibrated value.

## Recommended use

1. Resolve quality findings where possible.
2. Select a destructive-strength reference that corresponds to the NDT condition.
3. Compare NDT input sets rather than assuming that more inputs always improve accuracy.
4. Review RMSE, R², residuals, and range support together.
5. Treat durability score weights as explicit user choices.
6. Use physical testing for confirmation of important material decisions.
