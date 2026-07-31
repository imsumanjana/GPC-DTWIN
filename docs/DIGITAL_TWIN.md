# Digital Twin

The Digital Twin workspace creates surrogate response models with uncertainty bounds and
training-domain checks.

## Build and calibrate

Choose a response, predictor fields, a twin method, and a confidence level. Calibration uses
grouped cross-validation by mix whenever enough mix groups are available. Reported metrics include
RMSE, MAE, R², interval coverage, mean interval width, normalized RMSE, and calibration gap.

## Prediction

Single-scenario and batch outputs include:

- estimated response,
- prediction uncertainty,
- lower and upper bounds,
- relative uncertainty,
- nearest-data distance,
- outside-range fields,
- reliability class A–D,
- a plain-language reliability note.

A means close support with low uncertainty. D indicates extrapolation, remote support, or high
uncertainty. Reliability classes are decision-support indicators and do not replace physical testing.

## Response maps

Response maps vary two numeric predictors across their fitted ranges while holding all other
predictors at fitted default values. Estimated response, relative uncertainty, and reliability are
presented in separate tabs.

The on-screen response-map host is a fixed square 720 × 720 pixels. It is not stretched to fill a
rectangular viewport. When the available space is smaller, horizontal and vertical scrollbars appear.
Exports remain square at 6 × 6 inches with selectable 150–2400 dpi quality.

The map engine stores explicit row and column coordinates before reshaping predictions. It supports
up to 100 × 100 grids and falls back to a one-dimensional response curve when only one suitable
numeric predictor varies.

## Twin library

Saved twin files use Joblib with matching JSON metadata. A twin should be rebuilt when the active
dataset or selected variables change materially.
