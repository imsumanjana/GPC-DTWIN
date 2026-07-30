"""Deterministic quality checks for material-test datasets."""

from __future__ import annotations

from dataclasses import dataclass
import re

import numpy as np
import pandas as pd

from gpc_dtwin.columns import NONNEGATIVE_COLUMNS, REQUIRED_ID_COLUMNS

ISSUE_COLUMNS = [
    "severity",
    "rule",
    "record_id",
    "mix_id",
    "field",
    "message",
    "data_block",
    "data_locator",
]


@dataclass(frozen=True)
class AuditSummary:
    critical: int
    warning: int
    information: int
    total: int


class AuditService:
    """Run transparent, repeatable checks without changing the dataset."""

    GROUP_REQUIRED_FIELDS = {
        "AASB_WORKABILITY_AND_28D_COMPRESSIVE": [
            "aas_b_ratio", "slump_mm", "workability_class", "compressive_strength_mpa"
        ],
        "AMBIENT_7D_MECHANICAL": [
            "compressive_strength_mpa", "split_tensile_strength_mpa", "flexural_strength_mpa"
        ],
        "AMBIENT_28D_MECHANICAL": [
            "compressive_strength_mpa", "split_tensile_strength_mpa", "flexural_strength_mpa"
        ],
        "OVEN_100C_24H_MECHANICAL": [
            "curing_temperature_C", "curing_duration_hours", "compressive_strength_mpa",
            "split_tensile_strength_mpa", "flexural_strength_mpa"
        ],
        "NON_DESTRUCTIVE_TESTS": ["upv_m_s", "rebound_estimated_strength_mpa"],
        "ACID_DURABILITY_28D": [
            "acid_type", "acid_concentration_percent", "acid_exposure_days",
            "initial_mass_kg", "exposed_mass_kg", "initial_compressive_strength_mpa",
            "residual_compressive_strength_mpa"
        ],
    }

    def run(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        issues: list[dict[str, object]] = []
        if dataframe.empty:
            return pd.DataFrame(
                [self._issue("CRITICAL", "EMPTY_DATASET", None, "dataset", "No records are available.")],
                columns=ISSUE_COLUMNS,
            )

        self._check_required_identity(dataframe, issues)
        self._check_duplicate_record_ids(dataframe, issues)
        self._check_binder_sum(dataframe, issues)
        self._check_nonnegative_values(dataframe, issues)
        self._check_group_requirements(dataframe, issues)
        self._check_provenance(dataframe, issues)
        self._check_status_flags(dataframe, issues)
        self._check_mix_label_consistency(dataframe, issues)
        self._check_derived_durability_values(dataframe, issues)
        self._check_activator_ratio(dataframe, issues)
        self._check_ranges(dataframe, issues)

        if not issues:
            return pd.DataFrame(columns=ISSUE_COLUMNS)

        severity_order = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}
        result = pd.DataFrame(issues, columns=ISSUE_COLUMNS)
        result["_order"] = result["severity"].map(severity_order).fillna(3)
        result = result.sort_values(
            by=["_order", "record_id", "rule"], kind="stable", na_position="last"
        ).drop(columns="_order")
        return result.reset_index(drop=True)

    @staticmethod
    def summary(issues: pd.DataFrame) -> AuditSummary:
        if issues.empty:
            return AuditSummary(0, 0, 0, 0)
        counts = issues["severity"].value_counts()
        return AuditSummary(
            critical=int(counts.get("CRITICAL", 0)),
            warning=int(counts.get("WARNING", 0)),
            information=int(counts.get("INFO", 0)),
            total=int(len(issues)),
        )

    def _check_required_identity(self, df: pd.DataFrame, issues: list[dict]) -> None:
        for column in REQUIRED_ID_COLUMNS:
            if column not in df.columns:
                issues.append(self._issue(
                    "CRITICAL", "MISSING_SCHEMA_COLUMN", None, column,
                    f"Required schema field '{column}' is absent."
                ))
                continue
            missing = df[column].isna() | (df[column].astype(str).str.strip() == "")
            for _, row in df.loc[missing].iterrows():
                issues.append(self._issue(
                    "CRITICAL", "MISSING_IDENTITY", row, column,
                    f"Required identity field '{column}' is empty."
                ))

    def _check_duplicate_record_ids(self, df: pd.DataFrame, issues: list[dict]) -> None:
        if "record_id" not in df.columns:
            return
        duplicates = df[df["record_id"].duplicated(keep=False)]
        for _, row in duplicates.iterrows():
            issues.append(self._issue(
                "CRITICAL", "DUPLICATE_RECORD_ID", row, "record_id",
                f"Record identifier '{row.get('record_id', '')}' is duplicated."
            ))

    def _check_binder_sum(self, df: pd.DataFrame, issues: list[dict]) -> None:
        columns = ["fa_percent_numeric", "ggbs_percent_numeric", "sf_percent_numeric"]
        if not set(columns).issubset(df.columns):
            return
        values = df[columns].apply(pd.to_numeric, errors="coerce")
        sums = values.sum(axis=1, min_count=3)
        invalid = sums.notna() & ~np.isclose(sums, 100.0, atol=0.01)
        for index in df.index[invalid]:
            row = df.loc[index]
            issues.append(self._issue(
                "CRITICAL", "BINDER_SUM", row,
                "fa_percent_numeric/ggbs_percent_numeric/sf_percent_numeric",
                f"Binder percentages sum to {sums.loc[index]:.3f}, not 100."
            ))

    def _check_nonnegative_values(self, df: pd.DataFrame, issues: list[dict]) -> None:
        for column in NONNEGATIVE_COLUMNS.intersection(df.columns):
            values = pd.to_numeric(df[column], errors="coerce")
            for index in df.index[values < 0]:
                row = df.loc[index]
                issues.append(self._issue(
                    "CRITICAL", "NEGATIVE_VALUE", row, column,
                    f"Physical quantity '{column}' is negative."
                ))

    def _check_group_requirements(self, df: pd.DataFrame, issues: list[dict]) -> None:
        if "record_group" not in df.columns:
            return
        for group, fields in self.GROUP_REQUIRED_FIELDS.items():
            group_df = df[df["record_group"] == group]
            for field in fields:
                if field not in group_df.columns:
                    issues.append(self._issue(
                        "CRITICAL", "MISSING_SCHEMA_COLUMN", None, field,
                        f"Expected field '{field}' is absent."
                    ))
                    continue
                missing = group_df[field].isna() | (group_df[field].astype(str).str.strip() == "")
                for _, row in group_df.loc[missing].iterrows():
                    issues.append(self._issue(
                        "CRITICAL", "GROUP_REQUIRED_VALUE", row, field,
                        f"'{field}' is required for record group '{group}'."
                    ))

    def _check_provenance(self, df: pd.DataFrame, issues: list[dict]) -> None:
        for column in ("dataset_origin", "data_block", "data_locator"):
            if column not in df.columns:
                continue
            missing = df[column].isna() | (df[column].astype(str).str.strip() == "")
            for _, row in df.loc[missing].iterrows():
                issues.append(self._issue(
                    "WARNING", "MISSING_PROVENANCE", row, column,
                    f"Provenance field '{column}' is empty."
                ))

    def _check_status_flags(self, df: pd.DataFrame, issues: list[dict]) -> None:
        if "data_status" not in df.columns:
            return
        status = df["data_status"].fillna("").astype(str)
        flagged = status.str.contains("REVIEW|CONFLICT", case=False, regex=True)
        for _, row in df.loc[flagged].iterrows():
            issues.append(self._issue(
                "WARNING", "REVIEW_FLAG", row, "data_status",
                f"Record is marked '{row.get('data_status', '')}'."
            ))

    def _check_mix_label_consistency(self, df: pd.DataFrame, issues: list[dict]) -> None:
        required = {
            "mix_proportion_label", "fa_percent_numeric", "ggbs_percent_numeric", "sf_percent_numeric"
        }
        if not required.issubset(df.columns):
            return
        checked: set[str] = set()
        for _, row in df.iterrows():
            mix_id = str(row.get("mix_id", ""))
            if mix_id in checked:
                continue
            checked.add(mix_id)
            label = str(row.get("mix_proportion_label", ""))
            numbers = re.findall(r"-?\d+(?:\.\d+)?", label)
            if len(numbers) != 3:
                issues.append(self._issue(
                    "WARNING", "MIX_LABEL_FORMAT", row, "mix_proportion_label",
                    "Mix label should contain FA:GGBS:SF values."
                ))
                continue
            reported = tuple(float(number) for number in numbers)
            numeric = tuple(self._number(row.get(column)) for column in (
                "fa_percent_numeric", "ggbs_percent_numeric", "sf_percent_numeric"
            ))
            if any(value is None for value in numeric):
                continue
            if not all(np.isclose(a, b, atol=0.01) for a, b in zip(reported, numeric)):
                issues.append(self._issue(
                    "WARNING", "MIX_LABEL_MISMATCH", row, "mix_proportion_label",
                    f"Mix label {reported} differs from numeric values {numeric}."
                ))

    def _check_derived_durability_values(self, df: pd.DataFrame, issues: list[dict]) -> None:
        if "record_group" not in df.columns:
            return
        durable = df[df["record_group"] == "ACID_DURABILITY_28D"]
        for _, row in durable.iterrows():
            initial_mass = self._number(row.get("initial_mass_kg"))
            exposed_mass = self._number(row.get("exposed_mass_kg"))
            stored_change = self._number(row.get("mass_change_percent_derived"))
            if initial_mass not in (None, 0) and exposed_mass is not None and stored_change is not None:
                calculated = (exposed_mass - initial_mass) / initial_mass * 100
                if not np.isclose(calculated, stored_change, atol=0.01):
                    issues.append(self._issue(
                        "CRITICAL", "MASS_CHANGE_CALCULATION", row,
                        "mass_change_percent_derived",
                        f"Stored value {stored_change:.4f}% differs from calculated {calculated:.4f}%."
                    ))

            initial_strength = self._number(row.get("initial_compressive_strength_mpa"))
            residual = self._number(row.get("residual_compressive_strength_mpa"))
            stored_loss = self._number(row.get("strength_loss_percent_derived"))
            if initial_strength not in (None, 0) and residual is not None and stored_loss is not None:
                calculated = (initial_strength - residual) / initial_strength * 100
                if not np.isclose(calculated, stored_loss, atol=0.01):
                    issues.append(self._issue(
                        "CRITICAL", "STRENGTH_LOSS_CALCULATION", row,
                        "strength_loss_percent_derived",
                        f"Stored value {stored_loss:.4f}% differs from calculated {calculated:.4f}%."
                    ))

    def _check_activator_ratio(self, df: pd.DataFrame, issues: list[dict]) -> None:
        if "activator_ratio_label" not in df.columns:
            return
        labels = df["activator_ratio_label"].fillna("").astype(str).str.strip()
        for _, row in df.loc[labels == ""].iterrows():
            issues.append(self._issue(
                "INFO", "MISSING_ACTIVATOR_RATIO", row, "activator_ratio_label",
                "Activator-ratio description is not available."
            ))

    def _check_ranges(self, df: pd.DataFrame, issues: list[dict]) -> None:
        for column in ("fa_percent_numeric", "ggbs_percent_numeric", "sf_percent_numeric"):
            if column not in df.columns:
                continue
            values = pd.to_numeric(df[column], errors="coerce")
            invalid = (values > 100) | (values < 0)
            for _, row in df.loc[invalid].iterrows():
                issues.append(self._issue(
                    "CRITICAL", "PERCENTAGE_RANGE", row, column,
                    f"'{column}' must be between 0 and 100."
                ))

        if "aas_b_ratio" in df.columns:
            values = pd.to_numeric(df["aas_b_ratio"], errors="coerce")
            unusual = values.notna() & ((values <= 0) | (values > 2))
            for _, row in df.loc[unusual].iterrows():
                issues.append(self._issue(
                    "WARNING", "AAS_B_RANGE", row, "aas_b_ratio",
                    "AAS:B ratio is outside the expected positive working range."
                ))

    @staticmethod
    def _number(value: object) -> float | None:
        try:
            if pd.isna(value) or str(value).strip() == "":
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _issue(
        severity: str,
        rule: str,
        row: pd.Series | dict | None,
        field: str,
        message: str,
    ) -> dict[str, object]:
        getter = row.get if row is not None else lambda key, default="": default
        return {
            "severity": severity,
            "rule": rule,
            "record_id": getter("record_id", ""),
            "mix_id": getter("mix_id", ""),
            "field": field,
            "message": message,
            "data_block": getter("data_block", ""),
            "data_locator": getter("data_locator", ""),
        }
