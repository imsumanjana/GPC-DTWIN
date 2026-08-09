# Predictive Modelling

Predictive Modelling is the **authoritative model-benchmarking stage** in GPC-DTwin. The same validated ranking is handed to the Digital Twin workspace for the matching dataset, response, predictor set, review-record policy, and grouping configuration.

## Candidate algorithms

GPC-DTwin compares seven regression algorithms from one shared model registry:

- Linear Regression
- Ridge Regression
- Elastic Net
- Support Vector Regression
- Random Forest
- Gradient Boosting
- Extra Trees

Numeric inputs use median imputation and standardisation. Categorical inputs use a dedicated missing-value category and one-hot encoding. Because Predictive Modelling and Digital Twin read the same registry, an algorithm has the same preprocessing and estimator configuration in both workspaces.

## Validation

When at least three mix groups are available, `GroupKFold` keeps each mix entirely within one fold. Otherwise shuffled `KFold` is used. Each algorithm produces out-of-fold predictions and the following metrics:

- RMSE, MAE, R², and MAPE where applicable;
- mean and standard deviation of fold RMSE;
- mean and standard deviation of fold MAE;
- mean and standard deviation of fold R² when defined;
- fitting time.

The fold variability is retained because a slightly lower average error can be less convincing when performance changes strongly between folds.

## Ranking and dynamic model note

The main ranking remains ordered by cross-validated RMSE, with MAE and algorithm name used as deterministic tie-breakers. The ranking table also generates a **one-word, data-derived status** for the current run:

- **Recommended** — the current ranking leader;
- **Competitive** — very close to the leader with acceptable fold variation;
- **Stable** — good fold consistency with a modest error gap;
- **Moderate** — usable but clearly behind stronger candidates;
- **Mixed** — the validation indicators do not support a stronger label;
- **Uncertain** — fold-to-fold variation is large;
- **Weak** — substantially poorer validation error than the leader.

These words are **not fixed properties of algorithms**. A model can receive a different status for another response, predictor set, or dataset.

## Model hand-off to Digital Twin

After comparison, the result is published to `ApplicationContext`. Digital Twin will only accept it when all of the following match:

- active dataset state;
- response;
- effective predictor set;
- include-review-records setting;
- grouping field.

The ranking leader is selected by default in Digital Twin, while all seven models remain manually selectable with their current rank and one-word status.

If the dataset is imported, appended, restored, or a verification status changes, the shared ranking and active twin are invalidated and must be rebuilt.

## Feature influence

Permutation importance reports the change in prediction error when a predictor is shuffled. A higher positive value indicates stronger dependence of the fitted model on that predictor. Negative values can occur in small or noisy datasets and should not be interpreted as physical causation.

## Saved point-prediction models

Each saved point-prediction model includes:

- a `.joblib` fitted pipeline;
- a `.json` metadata file;
- response and predictor names;
- selected algorithm;
- validation metrics;
- input defaults, known categories, and numeric ranges;
- record count, validation method, dataset fingerprint, and current ranking.

Model predictions should be interpreted within the range and quality of the observations used to fit the model.
