"""Statistical summaries, group comparison, and regression utilities."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from scipy import stats
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold, KFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, PolynomialFeatures, StandardScaler

from gpc_dtwin.columns import ANALYSIS_FACTOR_COLUMNS, ANALYSIS_NUMERIC_COLUMNS, COLUMN_LABELS, quantity_label
from gpc_dtwin.field_compatibility import assess_usable_fields, clean_selected_frame


@dataclass(frozen=True)
class AnovaResult:
    response: str
    factor: str
    groups: int
    observations: int
    statistic: float
    p_value: float
    effect_size_eta_squared: float
    group_summary: pd.DataFrame


@dataclass(frozen=True)
class RegressionResult:
    response: str
    requested_predictors: tuple[str, ...]
    predictors: tuple[str, ...]
    omitted_predictors: tuple[str, ...]
    omitted_reasons: dict[str, str]
    degree: int
    observations: int
    rmse: float
    mae: float
    r2: float
    cv_method: str
    predictions: pd.DataFrame
    coefficients: pd.DataFrame


class StatisticsService:
    """Provide transparent analyses suitable for small structured datasets."""

    @staticmethod
    def available_numeric(dataframe: pd.DataFrame) -> list[str]:
        return [column for column in ANALYSIS_NUMERIC_COLUMNS if column in dataframe.columns]

    @staticmethod
    def available_factors(dataframe: pd.DataFrame) -> list[str]:
        return [column for column in ANALYSIS_FACTOR_COLUMNS if column in dataframe.columns]

    @staticmethod
    def descriptive(dataframe: pd.DataFrame, columns: list[str] | None = None) -> pd.DataFrame:
        selected = columns or StatisticsService.available_numeric(dataframe)
        selected = [column for column in selected if column in dataframe.columns]
        if not selected:
            return pd.DataFrame()
        numeric = dataframe[selected].apply(pd.to_numeric, errors="coerce")
        result = numeric.describe(percentiles=[0.25, 0.5, 0.75]).T
        result["missing"] = numeric.isna().sum()
        result["cv_percent"] = np.where(
            result["mean"].abs() > 1e-12,
            result["std"] / result["mean"].abs() * 100,
            np.nan,
        )
        result.index.name = "variable"
        return result.reset_index()

    @staticmethod
    def correlation(dataframe: pd.DataFrame, columns: list[str] | None = None,
                    method: str = "pearson") -> pd.DataFrame:
        selected = columns or StatisticsService.available_numeric(dataframe)
        selected = [column for column in selected if column in dataframe.columns]
        if not selected:
            return pd.DataFrame()
        numeric = dataframe[selected].apply(pd.to_numeric, errors="coerce")
        return numeric.corr(method=method, min_periods=3)

    @staticmethod
    def correlation_figure(correlation: pd.DataFrame) -> Figure:
        figure = Figure(figsize=(8.5, 6.2), constrained_layout=True)
        axis = figure.add_subplot(111)
        if correlation.empty:
            axis.text(0.5, 0.5, "No correlation matrix available", ha="center", va="center")
            axis.set_axis_off()
            return figure
        image = axis.imshow(correlation.values, vmin=-1, vmax=1, aspect="auto")
        labels = [COLUMN_LABELS.get(column, column) for column in correlation.columns]
        axis.set_xticks(range(len(labels)), labels, rotation=45, ha="right", fontsize=8)
        axis.set_yticks(range(len(labels)), labels, fontsize=8)
        for row in range(len(labels)):
            for column in range(len(labels)):
                value = correlation.iat[row, column]
                if not pd.isna(value):
                    axis.text(column, row, f"{value:.2f}", ha="center", va="center", fontsize=7)
        figure.colorbar(image, ax=axis, label="Correlation (–)")
        return figure

    @staticmethod
    def one_way_anova(dataframe: pd.DataFrame, response: str, factor: str) -> AnovaResult:
        if response not in dataframe.columns or factor not in dataframe.columns:
            raise ValueError("Selected response or factor is not available.")
        working = dataframe[[response, factor]].copy()
        working[response] = pd.to_numeric(working[response], errors="coerce")
        working[factor] = working[factor].astype("string")
        working = working.dropna()
        grouped = [group[response].to_numpy(dtype=float) for _, group in working.groupby(factor)]
        grouped = [values for values in grouped if len(values) >= 2]
        if len(grouped) < 2:
            raise ValueError("ANOVA requires at least two groups with two observations each.")
        statistic, p_value = stats.f_oneway(*grouped)
        grand_mean = float(working[response].mean())
        ss_between = sum(
            len(group) * (float(group[response].mean()) - grand_mean) ** 2
            for _, group in working.groupby(factor)
        )
        ss_total = float(((working[response] - grand_mean) ** 2).sum())
        eta_squared = ss_between / ss_total if ss_total > 0 else math.nan
        summary = working.groupby(factor)[response].agg(["count", "mean", "std", "min", "max"]).reset_index()
        return AnovaResult(
            response=response,
            factor=factor,
            groups=len(grouped),
            observations=len(working),
            statistic=float(statistic),
            p_value=float(p_value),
            effect_size_eta_squared=float(eta_squared),
            group_summary=summary,
        )

    @staticmethod
    def anova_figure(dataframe: pd.DataFrame, response: str, factor: str) -> Figure:
        working = dataframe[[response, factor]].copy()
        working[response] = pd.to_numeric(working[response], errors="coerce")
        working = working.dropna()
        figure = Figure(figsize=(8.5, 5.5), constrained_layout=True)
        axis = figure.add_subplot(111)
        groups = [(str(name), group[response].to_numpy(dtype=float))
                  for name, group in working.groupby(factor) if len(group) > 0]
        if not groups:
            axis.text(0.5, 0.5, "No groups available", ha="center", va="center")
            axis.set_axis_off()
            return figure
        axis.boxplot([values for _, values in groups], tick_labels=[name for name, _ in groups], showmeans=True)
        axis.set_xlabel(COLUMN_LABELS.get(factor, factor))
        axis.set_ylabel(COLUMN_LABELS.get(response, response))
        axis.tick_params(axis="x", rotation=30)
        axis.grid(True, axis="y", alpha=0.25)
        return figure

    @staticmethod
    def regression_predictor_availability(
        dataframe: pd.DataFrame,
        response: str,
        predictors: list[str],
    ) -> tuple[list[str], list[str]]:
        if response not in dataframe.columns:
            return [], list(dict.fromkeys(predictors))
        response_values = pd.to_numeric(dataframe[response], errors="coerce")
        subset = dataframe.loc[response_values.notna()].copy()
        report = assess_usable_fields(
            subset,
            predictors,
            numeric_fields=ANALYSIS_NUMERIC_COLUMNS,
            excluded_fields={response},
        )
        return list(report.usable), list(report.omitted)

    @staticmethod
    def regression(dataframe: pd.DataFrame, response: str, predictors: list[str],
                   degree: int = 1, group_column: str = "mix_id") -> RegressionResult:
        requested_predictors = list(dict.fromkeys(predictors))
        if not requested_predictors:
            raise ValueError("Select at least one predictor.")
        if response not in dataframe.columns:
            raise ValueError(f"Missing selected response: {response}")

        response_values = pd.to_numeric(dataframe[response], errors="coerce")
        response_rows = dataframe.loc[response_values.notna()].copy()
        report = assess_usable_fields(
            response_rows,
            requested_predictors,
            numeric_fields=ANALYSIS_NUMERIC_COLUMNS,
            excluded_fields={response},
        )
        predictors = list(report.usable)
        if not predictors:
            raise ValueError(
                "None of the selected predictors has usable values for "
                f"{COLUMN_LABELS.get(response, response)}."
            )

        working_columns = list(dict.fromkeys([
            response,
            *predictors,
            *([group_column] if group_column in dataframe.columns else []),
        ]))
        working = dataframe.loc[:, working_columns].copy()
        working[response] = pd.to_numeric(working[response], errors="coerce")
        working = working.dropna(subset=[response]).copy()
        if len(working) < 5:
            raise ValueError("Regression requires at least five response observations.")

        numeric_predictors = [column for column in predictors if column in ANALYSIS_NUMERIC_COLUMNS]
        categorical_predictors = [column for column in predictors if column not in numeric_predictors]
        cleaned = clean_selected_frame(
            working,
            predictors,
            numeric_fields=ANALYSIS_NUMERIC_COLUMNS,
        )
        for column in predictors:
            working[column] = cleaned[column]

        numeric_steps = [("imputer", SimpleImputer(strategy="median", keep_empty_features=True))]
        if degree > 1:
            numeric_steps.append(("polynomial", PolynomialFeatures(degree=degree, include_bias=False)))
        numeric_steps.append(("scale", StandardScaler()))
        transformers = []
        if numeric_predictors:
            transformers.append(("numeric", Pipeline(numeric_steps), numeric_predictors))
        if categorical_predictors:
            transformers.append((
                "categorical",
                Pipeline([
                    ("imputer", SimpleImputer(
                        strategy="constant", fill_value="Missing", keep_empty_features=True
                    )),
                    ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
                ]),
                categorical_predictors,
            ))
        preprocessing = ColumnTransformer(transformers=transformers, remainder="drop")
        model = Pipeline([("preprocess", preprocessing), ("model", LinearRegression())])

        x = working.loc[:, predictors].copy()
        y = working[response].to_numpy(dtype=float).reshape(-1)
        groups = None
        if group_column in working.columns:
            groups = (
                working[group_column]
                .astype("string")
                .fillna("Missing")
                .astype(str)
                .to_numpy()
                .reshape(-1)
            )
        unique_groups = len(np.unique(groups)) if groups is not None else 0
        if groups is not None and unique_groups >= 3:
            splits = min(5, unique_groups)
            cv = GroupKFold(n_splits=splits)
            predictions = cross_val_predict(model, x, y, cv=cv, groups=groups)
            cv_method = f"Grouped {splits}-fold cross-validation by {group_column}"
        else:
            splits = min(5, len(working))
            if splits < 2:
                raise ValueError("Insufficient observations for cross-validation.")
            cv = KFold(n_splits=splits, shuffle=True, random_state=42)
            predictions = cross_val_predict(model, x, y, cv=cv)
            cv_method = f"{splits}-fold cross-validation"

        predictions = np.asarray(predictions, dtype=float).reshape(-1)
        rmse = float(np.sqrt(mean_squared_error(y, predictions)))
        mae = float(mean_absolute_error(y, predictions))
        r2 = float(r2_score(y, predictions))

        model.fit(x, y)
        feature_names = model.named_steps["preprocess"].get_feature_names_out()
        coefficients = np.asarray(model.named_steps["model"].coef_, dtype=float).reshape(-1)
        coefficient_table = pd.DataFrame({
            "feature": [str(name).replace("numeric__", "").replace("categorical__", "") for name in feature_names],
            "coefficient": coefficients,
        }).sort_values("coefficient", key=lambda values: values.abs(), ascending=False).reset_index(drop=True)

        prediction_table = pd.DataFrame({
            "observed": y,
            "predicted": predictions,
            "residual": y - predictions,
        }, index=working.index)
        if group_column in working.columns:
            prediction_table[group_column] = working[group_column].astype(str).values

        return RegressionResult(
            response=response,
            requested_predictors=tuple(requested_predictors),
            predictors=tuple(predictors),
            omitted_predictors=tuple(report.omitted),
            omitted_reasons=dict(report.reasons),
            degree=int(degree),
            observations=len(working),
            rmse=rmse,
            mae=mae,
            r2=r2,
            cv_method=cv_method,
            predictions=prediction_table,
            coefficients=coefficient_table,
        )

    @staticmethod
    def regression_figure(result: RegressionResult) -> Figure:
        figure = Figure(figsize=(7.5, 5.5), constrained_layout=True)
        axis = figure.add_subplot(111)
        observed = result.predictions["observed"]
        predicted = result.predictions["predicted"]
        axis.scatter(observed, predicted, label="Cross-validated predictions")
        minimum = min(float(observed.min()), float(predicted.min()))
        maximum = max(float(observed.max()), float(predicted.max()))
        axis.plot([minimum, maximum], [minimum, maximum], linestyle="--", linewidth=1, label="Ideal agreement")
        axis.set_xlabel(quantity_label("Observed", result.response))
        axis.set_ylabel(quantity_label("Cross-validated prediction", result.response))
        axis.grid(True, alpha=0.25)
        axis.set_title(f"RMSE {result.rmse:.3f} · MAE {result.mae:.3f} · R² {result.r2:.3f}")
        axis.legend()
        return figure
