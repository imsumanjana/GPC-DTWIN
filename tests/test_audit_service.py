from pathlib import Path

from gpc_dtwin.services.audit_service import AuditService
from gpc_dtwin.services.data_service import DataService

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data" / "reference" / "GPC_Reference_Dataset.csv"


def test_quality_check_preserves_review_flags_without_false_composition_errors():
    dataframe = DataService.load_csv(DATASET)
    issues = AuditService().run(dataframe)
    rules = set(issues["rule"])
    assert "REVIEW_FLAG" in rules
    assert "BINDER_SUM" not in rules
    assert "MIX_LABEL_MISMATCH" not in rules
    assert "MASS_CHANGE_CALCULATION" not in rules
    assert "STRENGTH_LOSS_CALCULATION" not in rules
    summary = AuditService.summary(issues)
    assert summary.critical == 0
    assert summary.warning >= 1
