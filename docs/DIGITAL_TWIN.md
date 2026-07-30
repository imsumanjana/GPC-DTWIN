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
predictors at fitted default values. The map presents estimated response, relative uncertainty, and
reliability class.

## Twin library

Saved twin files use Joblib with matching JSON metadata. A twin should be rebuilt when the active
dataset or selected variables change materially.
