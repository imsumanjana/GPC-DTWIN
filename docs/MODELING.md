# Predictive Modelling

## Algorithms

GPC-DTwin compares:

- Linear Regression
- Ridge Regression
- Elastic Net
- Support Vector Regression
- Random Forest
- Gradient Boosting
- Extra Trees

Numeric inputs use median imputation and standardisation. Categorical inputs use a dedicated missing-value category and one-hot encoding.

## Validation

When at least three mix groups are available, GroupKFold keeps each mix entirely within one fold. Otherwise, shuffled KFold is used. Model rankings report RMSE, MAE, R², MAPE, and execution time.

## Model selection

The first-ranked model has the lowest cross-validated RMSE. A fitted pipeline is created from all usable records only after cross-validation is complete.

## Feature influence

Permutation importance reports the change in prediction error when a predictor is shuffled. A higher positive value indicates stronger dependence of the fitted model on that predictor. Negative values can occur in small or noisy datasets.

## Saved models

Each saved model has:

- a `.joblib` pipeline file;
- a `.json` metadata file;
- response and predictor names;
- algorithm name;
- validation metrics;
- input defaults and known categories;
- record count and validation method.

Model predictions should be interpreted within the range and quality of the data used to fit the model.

## Uncertainty-aware twins

The Digital Twin workspace is separate from point-prediction model comparison. It adds confidence
bounds, interval coverage, nearest-data distance, range checks, and reliability classes. Gaussian
Process and Forest Ensemble methods are available.
