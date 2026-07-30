# Active Learning

## Purpose

The Active Learning workspace identifies material scenarios that can improve a response surrogate or
explore a promising region with a limited number of new experiments.

## Experiment recommendations

1. Select a response and uncertainty method.
2. Select predictors with sufficient usable observations.
3. Choose an acquisition strategy and response direction.
4. Set candidate-pool size, recommendation count, diversity weight, and random seed.
5. Define numeric experiment-variable bounds.
6. Enable binder closure when FA, GGBS, and SF must total 100%.
7. Select **Recommend experiments**.

Each recommendation reports the estimated response, prediction standard deviation, interval bounds,
relative uncertainty, range support, reliability class, distance from existing designs, expected
improvement, and acquisition score.

## Acquisition strategies

- **Maximum uncertainty** prioritizes poorly supported regions while retaining a novelty component.
- **Expected improvement** balances predicted improvement and uncertainty relative to the best
  observed response.
- **Confidence bound** ranks optimistic or conservative bounds according to the selected direction.
- **Balanced exploration** combines improvement, uncertainty, response potential, and novelty.

A diversity step reduces near-duplicate recommendations.

## Compatible experiment plan

The exported plan follows the 44-field dataset schema. Estimated values are written only in the notes;
the measured response field remains blank. After testing, enter the measured response, review the
metadata, assign an appropriate data status, and append the completed CSV.

## Closed-loop comparison

The comparison rebuilds the same surrogate settings with the current dataset and reports RMSE, MAE,
R², interval coverage, mean interval width, normalized RMSE, and calibration gap before and after the
new usable records. A comparison requires at least one additional usable response record.

## Run library

Saved runs retain recommendations, the candidate pool, surrogate validation, fitted artifact, settings,
and data fingerprint. Files are stored under `models/active_learning`.
