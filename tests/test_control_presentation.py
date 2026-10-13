"""Protect financial interpretation when new controls enter public reports."""
import json
from pathlib import Path

import pytest

from control_metadata import CATEGORY_LABELS, describe_control


def test_every_published_control_and_incident_has_reviewed_units_and_category():
    root = Path(__file__).resolve().parents[1] / "outputs/oversight"
    baseline = json.loads((root / "validation_summary.json").read_text())
    incidents = json.loads((root / "incident_summary.json").read_text())
    records = baseline["checks"] + [c for case in incidents["cases"] for c in case["failed_checks"]]
    for record in records:
        meta = describe_control(record["id"])
        assert meta["category"] in CATEGORY_LABELS
        assert meta["unit"]
    # An unchecked future residual must not acquire a guessed financial unit.
    with pytest.raises(ValueError, match="No reviewed residual unit"):
        describe_control("future_currency_adjustment")


def test_boolean_nav_checks_are_not_mislabeled_as_currency_or_failure_counts():
    assert describe_control("positive_saved_nav")["unit"] == "flag (0/1)"
    assert describe_control("daily_nav_reconstruction")["unit"] == "USD"
    assert describe_control("sql_missing_join_count")["unit"] == "rows"
    assert describe_control("risk_shrinkage_reconciliation")["unit"] == "fraction"
    assert describe_control("risk_te_reconciliation")["unit"] == "annual TE fraction"
