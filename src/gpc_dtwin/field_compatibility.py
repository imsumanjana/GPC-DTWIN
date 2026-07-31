"""Response-aware selection of usable analytical input fields."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd

from gpc_dtwin.columns import COLUMN_LABELS


@dataclass(frozen=True, slots=True)
class FieldCompatibilityReport:
    """Describe requested fields that can and cannot support an analysis."""

    requested: tuple[str, ...]
    usable: tuple[str, ...]
    omitted: tuple[str, ...]
    reasons: dict[str, str]
    support_counts: dict[str, int]

    def warning_text(self, *, prefix: str = "Excluded parameters") -> str:
        if not self.omitted:
            return ""
        details = []
        for field in self.omitted:
            label = COLUMN_LABELS.get(field, field)
            reason = self.reasons.get(field, "no usable values")
            details.append(f"{label} ({reason})")
        return f"{prefix}: " + ", ".join(details) + "."


def _usable_series(series: pd.Series, *, numeric: bool) -> pd.Series:
    if numeric:
        return pd.to_numeric(series, errors="coerce")
    values = series.astype("string").str.strip()
    values = values.mask(values.eq(""))
    # sklearn is more reliable with ordinary object arrays and np.nan than pd.NA.
    return values.astype(object).where(values.notna(), np.nan)


def assess_usable_fields(
    dataframe: pd.DataFrame,
    fields: Iterable[str],
    *,
    numeric_fields: Iterable[str] = (),
    excluded_fields: Iterable[str] = (),
    minimum_support: int = 1,
) -> FieldCompatibilityReport:
    """Return response-overlapping fields with at least ``minimum_support`` values.

    The caller supplies an already filtered frame, normally containing only rows
    where the chosen response is available and where the record state is allowed.
    Missing columns, explicitly excluded fields, and fields with no usable values
    are omitted rather than allowed to terminate an otherwise valid analysis.
    """

    requested = tuple(dict.fromkeys(str(field) for field in fields))
    numeric = set(numeric_fields)
    excluded = set(excluded_fields)
    usable: list[str] = []
    omitted: list[str] = []
    reasons: dict[str, str] = {}
    support_counts: dict[str, int] = {}

    for field in requested:
        if field in excluded:
            omitted.append(field)
            reasons[field] = "same as the selected response"
            support_counts[field] = 0
            continue
        if field not in dataframe.columns:
            omitted.append(field)
            reasons[field] = "field is not present in the active dataset"
            support_counts[field] = 0
            continue
        values = _usable_series(dataframe[field], numeric=field in numeric)
        support = int(values.notna().sum())
        support_counts[field] = support
        if support >= max(int(minimum_support), 1):
            usable.append(field)
        else:
            omitted.append(field)
            reasons[field] = "no usable values for the selected response"

    return FieldCompatibilityReport(
        requested=requested,
        usable=tuple(usable),
        omitted=tuple(omitted),
        reasons=reasons,
        support_counts=support_counts,
    )


def clean_selected_frame(
    dataframe: pd.DataFrame,
    fields: Iterable[str],
    *,
    numeric_fields: Iterable[str] = (),
) -> pd.DataFrame:
    """Return selected columns converted to sklearn-compatible values."""

    numeric = set(numeric_fields)
    result = dataframe.loc[:, list(dict.fromkeys(fields))].copy()
    for field in result.columns:
        result[field] = _usable_series(result[field], numeric=field in numeric)
    return result
