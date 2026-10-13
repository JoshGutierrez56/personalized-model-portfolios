"""Synthetic malformed-release cases; no licensed observations or real ledgers."""
from copy import deepcopy
import csv
import hashlib
import json
from pathlib import Path

import pytest

from release_evidence import (
    ATTRIBUTION_MAPS, ATTRIBUTION_SCALARS,
    PUBLIC_ARTIFACTS, SCENARIO_NUMBERS, SCENARIO_RECONCILIATION, SOURCE_PATHS,
    ReleaseEvidenceError, validate_release_bundle,
)


def _check(identifier, blocked=False):
    return {"id": identifier, "status": "BLOCK" if blocked else "PASS", "count": 2,
            "max_abs_error": 2.0 if blocked else 0.0, "tolerance": 0.1, "detail": "Synthetic check"}


def _attribution(client, method):
    # A zero net return after fees, but nonzero linked contributions.
    return {"client": client, "method": method,
            "portfolio_total_return": 0.0, "benchmark_total_return": 0.03,
            "active_total_return_difference": -0.03,
            "linked_asset_pnl": {"AA": 0.03, "BB": -0.02},
            "linked_benchmark_pnl": {"AA": 0.01, "BB": 0.02},
            "linked_active_asset_pnl": {"AA": 0.02, "BB": -0.04},
            "linked_cost_contribution": -0.01, "active_linking_residual": 0.0}


@pytest.fixture
def bundle():
    sources = {key: hashlib.sha256(f"fictional input {key}".encode()).hexdigest() for key in SOURCE_PATHS}
    pairs = [("Synthetic A", "Illustrative method"), ("Synthetic B", "Illustrative method")]
    baseline = {
        "status": "PASS", "blockers": [], "checks": [_check("nav"), _check("fee"), _check("keys")],
        "provenance": {"source_sha256": sources, "override_sha256": {}, "engine_imported": False},
        "aggregate": {"paths": 2, "evaluation_dates": 3, "execution_dates": 1, "source_dates": 4,
                      "assets": 2, "returns_rows": 8, "calendar_rows": 4, "daily_rows": 6,
                      "decisions_rows": 2, "trades_rows": 4, "benchmark_rows": 3,
                      "attribution_totals": [_attribution(client, method) for client, method in pairs]},
    }
    cases = [{"id": f"SYN-{index}", "severity": "BLOCK", "expected_status": "BLOCK",
              "observed_status": "BLOCK", "detected": True, "expected_domain_failure_observed": True,
              "expected_domain_checks_any": [identifier], "failed_checks": [_check(identifier, True)],
              "blockers": [identifier], "corrected_retest": "PASS", "closure": "CLOSED_TEST_CASE"}
             for index, identifier in enumerate(("nav", "fee"), start=1)]
    incidents = {"cases": cases, "injected_case_count": 2, "detected_case_count": 2,
                 "corrected_retest_status": "PASS", "original_inputs_unchanged": True}
    receipt = {"status": "PASS", "baseline_status": "PASS", "injected_cases": 2, "detected_cases": 2,
               "corrected_retest_status": "PASS", "original_inputs_unchanged": True,
               "input_sha256": {SOURCE_PATHS[key]: value for key, value in sources.items()}}
    scenarios = []
    for client, method in pairs:
        row = {"client": client, "method": method, **{key: 0.0 for key in SCENARIO_NUMBERS}}
        row.update(days=3, rebalance_count=1, terminal_nav=100.0, total_cost_dollars=1.0)
        scenarios.append(row)
    baseline["aggregate"]["path_metrics"] = [
        {"client": row["client"], "method": row["method"],
         **{reconstructed: row[published] / scale
            for published, (reconstructed, scale, _) in SCENARIO_RECONCILIATION.items()}}
        for row in scenarios
    ]
    stress = [{"episode": episode, "client": client, "method": method, "sessions": 1,
               "start_close_exclusive": "2001-01-02", "end_close_inclusive": "2001-01-03",
               "net_return_pct": -1.0, "benchmark_return_pct": -1.2,
               "active_cumulative_return_pp": 0.2, "window_max_drawdown_pct": -1.0}
              for episode in ("Fictional window A", "Fictional window B") for client, method in pairs]
    return {"baseline": baseline, "incidents": incidents, "receipt": receipt, "scenarios": scenarios, "stress": stress}


def _save(root: Path, bundle):
    """Seal exact bytes after each mutation so semantic tests go beyond hashes."""
    for name, relative in PUBLIC_ARTIFACTS.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if name == "scenarios":
            with path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=["client", "method", *SCENARIO_NUMBERS])
                writer.writeheader()
                writer.writerows(bundle[name])
        else:
            path.write_text(json.dumps(bundle[name], indent=2), encoding="utf-8")
    receipt = deepcopy(bundle["receipt"])
    receipt["public_artifact_sha256"] = {
        relative: hashlib.sha256((root / relative).read_bytes()).hexdigest()
        for relative in PUBLIC_ARTIFACTS.values()
    }
    (root / "outputs/oversight/run_receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")


def _receipt(root, edit):
    path = root / "outputs/oversight/run_receipt.json"
    receipt = json.loads(path.read_text(encoding="utf-8"))
    edit(receipt)
    path.write_text(json.dumps(receipt), encoding="utf-8")


def test_public_only_bundle_validates_without_private_data_or_production_code(tmp_path, bundle):
    _save(tmp_path, bundle)
    loaded = validate_release_bundle(tmp_path)
    assert set(loaded) == {"baseline", "incidents", "receipt", "stress", "scenarios"}
    assert loaded["baseline"] == bundle["baseline"]
    assert loaded["scenarios"][0]["terminal_nav"] == 100.0
    assert type(loaded["scenarios"][0]["days"]) is int
    assert not (tmp_path / "data").exists()
    assert not (tmp_path / "portfolio_engine.py").exists()
    assert not (tmp_path / "outputs/wrds_private").exists()


@pytest.mark.parametrize("name", list(PUBLIC_ARTIFACTS))
def test_each_changed_artifact_is_rejected_before_presentation(tmp_path, bundle, name):
    _save(tmp_path, bundle)
    path = tmp_path / PUBLIC_ARTIFACTS[name]
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ReleaseEvidenceError, match="fingerprint mismatch"):
        validate_release_bundle(tmp_path)


@pytest.mark.parametrize("mutation", ["missing_manifest", "missing_digest", "malformed_digest", "wrong_digest"])
def test_hash_manifest_is_mandatory_and_well_formed(tmp_path, bundle, mutation):
    _save(tmp_path, bundle)
    key = PUBLIC_ARTIFACTS["baseline"]
    def edit(receipt):
        if mutation == "missing_manifest":
            del receipt["public_artifact_sha256"]
        elif mutation == "missing_digest":
            del receipt["public_artifact_sha256"][key]
        else:
            receipt["public_artifact_sha256"][key] = "not-a-hash" if mutation == "malformed_digest" else "0" * 64
    _receipt(tmp_path, edit)
    with pytest.raises(ReleaseEvidenceError, match="public_artifact|fingerprint"):
        validate_release_bundle(tmp_path)


@pytest.mark.parametrize("mutation,match", [
    (lambda b: b["baseline"].update(status="BLOCK"), "status disagreement"),
    (lambda b: b["baseline"].update(blockers=["nav"]), "contains blockers"),
    (lambda b: b["baseline"]["checks"][0].update(status="BLOCK"), "must be PASS"),
    (lambda b: b["baseline"]["checks"][0].update(max_abs_error=0.2), "residual contradicts"),
    (lambda b: b["baseline"]["checks"][0].update(tolerance=-1), "nonnegative"),
    (lambda b: b["baseline"]["checks"].append(deepcopy(b["baseline"]["checks"][0])), "duplicate IDs"),
    (lambda b: b["baseline"].update(checks=[]), "must not be empty"),
    (lambda b: b["receipt"].update(baseline_status="BLOCK"), "status disagreement"),
])
def test_contradictory_baseline_pass_is_rejected(tmp_path, bundle, mutation, match):
    mutation(bundle)
    _save(tmp_path, bundle)
    with pytest.raises(ReleaseEvidenceError, match=match):
        validate_release_bundle(tmp_path)


@pytest.mark.parametrize("source,key,value", [
    ("receipt", "status", "BLOCK"),
    ("receipt", "original_inputs_unchanged", False),
    ("incidents", "original_inputs_unchanged", False),
    ("receipt", "original_inputs_unchanged", 1),
    ("receipt", "corrected_retest_status", "BLOCK"),
    ("incidents", "corrected_retest_status", "BLOCK"),
    ("receipt", "injected_cases", 3),
    ("receipt", "detected_cases", 1),
    ("incidents", "injected_case_count", 3),
    ("incidents", "detected_case_count", 1),
    ("receipt", "injected_cases", True),
])
def test_release_flags_and_counts_are_not_taken_on_trust(tmp_path, bundle, source, key, value):
    bundle[source][key] = value
    _save(tmp_path, bundle)
    with pytest.raises(ReleaseEvidenceError, match=key):
        validate_release_bundle(tmp_path)


@pytest.mark.parametrize("key,value", [
    ("expected_status", "PASS"), ("observed_status", "PASS"), ("severity", "WARN"),
    ("detected", False), ("detected", "true"), ("expected_domain_failure_observed", False),
    ("corrected_retest", "BLOCK"), ("closure", "OPEN"),
])
def test_incident_must_be_a_detected_and_closed_block(tmp_path, bundle, key, value):
    bundle["incidents"]["cases"][0][key] = value
    _save(tmp_path, bundle)
    with pytest.raises(ReleaseEvidenceError, match=key):
        validate_release_bundle(tmp_path)


@pytest.mark.parametrize("mutation,match", [
    (lambda c: c.update(expected_domain_checks_any=["fee"]), "actual expected domain failure"),
    (lambda c: c.update(expected_domain_checks_any=[]), "must not be empty"),
    (lambda c: c.update(failed_checks=[]), "must not be empty"),
    (lambda c: c["failed_checks"][0].update(status="PASS"), "must be BLOCK"),
    (lambda c: c["failed_checks"][0].update(max_abs_error=0.01), "residual contradicts"),
    (lambda c: c.update(blockers=["fee"]), "blockers disagree"),
    (lambda c: c.update(blockers=["nav", "nav"]), "blockers disagree"),
])
def test_domain_detection_requires_actual_failed_controls(tmp_path, bundle, mutation, match):
    mutation(bundle["incidents"]["cases"][0])
    _save(tmp_path, bundle)
    with pytest.raises(ReleaseEvidenceError, match=match):
        validate_release_bundle(tmp_path)


def test_duplicate_incident_ids_rejected(tmp_path, bundle):
    bundle["incidents"]["cases"][1]["id"] = bundle["incidents"]["cases"][0]["id"]
    _save(tmp_path, bundle)
    with pytest.raises(ReleaseEvidenceError, match="duplicate IDs"):
        validate_release_bundle(tmp_path)


@pytest.mark.parametrize("alias", list(SOURCE_PATHS))
def test_source_fingerprints_match_receipt_without_reading_sources(tmp_path, bundle, alias):
    bundle["baseline"]["provenance"]["source_sha256"][alias] = "0" * 64
    _save(tmp_path, bundle)
    with pytest.raises(ReleaseEvidenceError, match=f"source fingerprint disagreement: {alias}"):
        validate_release_bundle(tmp_path)


@pytest.mark.parametrize("key,value", [("override_sha256", {"returns": "0" * 64}), ("engine_imported", True)])
def test_baseline_independence_claims_checked(tmp_path, bundle, key, value):
    bundle["baseline"]["provenance"][key] = value
    _save(tmp_path, bundle)
    with pytest.raises(ReleaseEvidenceError, match="baseline must not"):
        validate_release_bundle(tmp_path)


@pytest.mark.parametrize("where", ["baseline", "incident", "stress", "receipt", "csv"])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_numeric_outputs_rejected_even_when_hashes_match(tmp_path, bundle, where, value):
    if where == "baseline":
        bundle["baseline"]["aggregate"]["unexpected_nested"] = {"values": [value]}
    elif where == "incident":
        bundle["incidents"]["cases"][0]["aggregate_impact"] = {"unexpected": value}
    elif where == "stress":
        bundle["stress"][0]["net_return_pct"] = value
    elif where == "receipt":
        bundle["receipt"]["elapsed_seconds"] = value
    else:
        bundle["scenarios"][0]["terminal_nav"] = value
    _save(tmp_path, bundle)
    with pytest.raises(ReleaseEvidenceError, match="finite number"):
        validate_release_bundle(tmp_path)


@pytest.mark.parametrize("key", ["returns_rows", "calendar_rows", "daily_rows", "decisions_rows", "trades_rows", "benchmark_rows"])
def test_baseline_row_counts_reconcile(tmp_path, bundle, key):
    bundle["baseline"]["aggregate"][key] += 1
    _save(tmp_path, bundle)
    with pytest.raises(ReleaseEvidenceError, match="count disagreement"):
        validate_release_bundle(tmp_path)


@pytest.mark.parametrize("mutation,match", [
    (lambda b: b["scenarios"].pop(), "path count disagreement"),
    (lambda b: b["scenarios"].__setitem__(1, deepcopy(b["scenarios"][0])), "duplicate path"),
    (lambda b: b["scenarios"][0].update(days=2), "evaluation/rebalance count disagreement"),
    (lambda b: b["scenarios"][0].update(rebalance_count=2), "evaluation/rebalance count disagreement"),
    (lambda b: b["baseline"]["aggregate"]["attribution_totals"].pop(), "attribution path"),
    (lambda b: b["stress"].pop(), "stress episode path coverage"),
    (lambda b: b["stress"].append(deepcopy(b["stress"][0])), "duplicate path"),
    (lambda b: b["stress"][0].update(method="unknown"), "unknown portfolio path"),
])
def test_public_path_coverage_and_counts_are_consistent(tmp_path, bundle, mutation, match):
    mutation(bundle)
    _save(tmp_path, bundle)
    with pytest.raises(ReleaseEvidenceError, match=match):
        validate_release_bundle(tmp_path)


def test_missing_public_file_has_clear_error(tmp_path, bundle):
    _save(tmp_path, bundle)
    (tmp_path / PUBLIC_ARTIFACTS["stress"]).unlink()
    with pytest.raises(ReleaseEvidenceError, match="cannot read historical_stress.json"):
        validate_release_bundle(tmp_path)


@pytest.mark.parametrize("mutation,match", [
    (lambda b: b["baseline"]["aggregate"]["attribution_totals"][0].update(client=[]), "client must be nonempty text"),
    (lambda b: b["stress"][0].update(method={}), "method must be nonempty text"),
    (lambda b: b["stress"][0].update(sessions=True), "sessions must be a positive integer"),
    (lambda b: b["stress"][0].update(start_close_exclusive="2001/01/02"), "ISO YYYY-MM-DD"),
    (lambda b: b["stress"][0].update(end_close_inclusive="2001-01-01"), "inconsistent window"),
    (lambda b: b["stress"][0].update(end_close_inclusive="2001-01-04"), "window/count disagreement"),
])
def test_malformed_path_and_stress_metadata_fail_clearly(tmp_path, bundle, mutation, match):
    mutation(bundle)
    _save(tmp_path, bundle)
    with pytest.raises(ReleaseEvidenceError, match=match):
        validate_release_bundle(tmp_path)


def test_duplicate_json_keys_rejected(tmp_path, bundle):
    _save(tmp_path, bundle)
    path = tmp_path / PUBLIC_ARTIFACTS["baseline"]
    raw = path.read_text(encoding="utf-8").replace('"status": "PASS"', '"status": "BLOCK", "status": "PASS"', 1)
    path.write_text(raw, encoding="utf-8")
    _receipt(tmp_path, lambda r: r["public_artifact_sha256"].update({PUBLIC_ARTIFACTS["baseline"]: hashlib.sha256(path.read_bytes()).hexdigest()}))
    with pytest.raises(ReleaseEvidenceError, match="duplicate JSON key"):
        validate_release_bundle(tmp_path)


@pytest.mark.parametrize("field", list(SCENARIO_RECONCILIATION))
def test_rehashed_but_economically_wrong_scenario_metric_is_blocked(tmp_path, bundle, field):
    # Updating the manifest must not conceal an incorrectly computed report.
    bundle["scenarios"][0][field] += 1
    _save(tmp_path, bundle)
    with pytest.raises(ReleaseEvidenceError, match="scenario/reconstructed metric disagreement"):
        validate_release_bundle(tmp_path)


def test_duplicated_reconstructed_path_cannot_replace_missing_path(tmp_path, bundle):
    bundle["baseline"]["aggregate"]["path_metrics"][1] = deepcopy(bundle["baseline"]["aggregate"]["path_metrics"][0])
    _save(tmp_path, bundle)
    with pytest.raises(ReleaseEvidenceError, match="metric path count/coverage"):
        validate_release_bundle(tmp_path)


@pytest.mark.parametrize("field", ATTRIBUTION_SCALARS + ATTRIBUTION_MAPS)
def test_attribution_requires_complete_schema_after_resealing(tmp_path, bundle, field):
    del bundle["baseline"]["aggregate"]["attribution_totals"][0][field]
    _save(tmp_path, bundle)
    with pytest.raises(ReleaseEvidenceError, match=field):
        validate_release_bundle(tmp_path)


@pytest.mark.parametrize("field", ATTRIBUTION_SCALARS + ATTRIBUTION_MAPS)
@pytest.mark.parametrize("value", [True, "0.0", None, float("nan"), float("inf")])
def test_attribution_numbers_are_finite_and_not_coerced(tmp_path, bundle, field, value):
    row = bundle["baseline"]["aggregate"]["attribution_totals"][0]
    if field in ATTRIBUTION_MAPS:
        row[field]["AA"] = value
    else:
        row[field] = value
    _save(tmp_path, bundle)
    with pytest.raises(ReleaseEvidenceError, match="finite number"):
        validate_release_bundle(tmp_path)


@pytest.mark.parametrize("field", ATTRIBUTION_MAPS)
@pytest.mark.parametrize("mutation", ["empty", "missing", "renamed", "blank", "array"])
def test_attribution_asset_schema_matches_all_maps_and_paths(tmp_path, bundle, field, mutation):
    row = bundle["baseline"]["aggregate"]["attribution_totals"][1]
    if mutation == "array":
        row[field] = [0.01, 0.02]
    elif mutation == "empty":
        row[field] = {}
    elif mutation == "missing":
        del row[field]["AA"]
    else:
        row[field]["CC" if mutation == "renamed" else " "] = row[field].pop("AA")
    _save(tmp_path, bundle)
    with pytest.raises(ReleaseEvidenceError, match="asset|must be an object"):
        validate_release_bundle(tmp_path)


@pytest.mark.parametrize("field,match", [
    ("portfolio_total_return", "portfolio linking"),
    ("benchmark_total_return", "benchmark linking"),
    ("active_total_return_difference", "active return difference"),
    ("active_linking_residual", "active linking residual"),
    ("linked_asset_pnl", "portfolio linking"),
    ("linked_benchmark_pnl", "benchmark linking"),
    ("linked_active_asset_pnl", "per-asset active linking"),
])
def test_attribution_linking_identities_reject_resealed_changes(tmp_path, bundle, field, match):
    row = bundle["baseline"]["aggregate"]["attribution_totals"][0]
    if field in ATTRIBUTION_MAPS:
        row[field]["AA"] += 0.1
    else:
        row[field] += 0.1
    _save(tmp_path, bundle)
    with pytest.raises(ReleaseEvidenceError, match=match):
        validate_release_bundle(tmp_path)


def test_attribution_positive_cost_rejected_even_when_identities_hold(tmp_path, bundle):
    row = bundle["baseline"]["aggregate"]["attribution_totals"][0]
    row.update(linked_cost_contribution=0.01, portfolio_total_return=0.02,
               active_total_return_difference=-0.01)
    _save(tmp_path, bundle)
    with pytest.raises(ReleaseEvidenceError, match="cost must be nonpositive"):
        validate_release_bundle(tmp_path)


@pytest.mark.parametrize("offset_total", [False, True])
def test_shared_benchmark_rejected_even_when_path_linking_holds(tmp_path, bundle, offset_total):
    row = bundle["baseline"]["aggregate"]["attribution_totals"][1]
    row["linked_benchmark_pnl"]["AA"] += 0.01
    row["linked_active_asset_pnl"]["AA"] -= 0.01
    if offset_total:
        row["benchmark_total_return"] += 0.01
        row["active_total_return_difference"] -= 0.01
    else:
        row["linked_benchmark_pnl"]["BB"] -= 0.01
        row["linked_active_asset_pnl"]["BB"] += 0.01
    _save(tmp_path, bundle)
    with pytest.raises(ReleaseEvidenceError, match="shared benchmark disagreement"):
        validate_release_bundle(tmp_path)


def test_actual_active_residual_cannot_hide_behind_zero_reported_residual(tmp_path, bundle):
    # Each per-asset error is within tolerance, but their sum is not.
    row = bundle["baseline"]["aggregate"]["attribution_totals"][0]
    for ticker in row["linked_active_asset_pnl"]:
        row["linked_active_asset_pnl"][ticker] += 0.75e-10
    _save(tmp_path, bundle)
    with pytest.raises(ReleaseEvidenceError, match="active linking residual disagreement"):
        validate_release_bundle(tmp_path)


@pytest.mark.parametrize("updates,match", [
    ({"active_cumulative_return_pp": 987}, "active gap disagreement"),
    ({"benchmark_return_pct": -0.2, "active_cumulative_return_pp": -0.8}, "shared benchmark disagreement"),
    ({"window_max_drawdown_pct": 25}, "drawdown range"),
    ({"window_max_drawdown_pct": -101}, "drawdown range"),
    ({"window_max_drawdown_pct": -0.5}, "drawdown range"),
    ({"net_return_pct": -150, "active_cumulative_return_pp": -148.8}, "return below"),
    ({"benchmark_return_pct": -150, "active_cumulative_return_pp": 149}, "return below"),
])
def test_stress_economic_contradictions_rejected_after_resealing(tmp_path, bundle, updates, match):
    bundle["stress"][1].update(updates)
    _save(tmp_path, bundle)
    with pytest.raises(ReleaseEvidenceError, match=match):
        validate_release_bundle(tmp_path)


def test_linking_and_stress_tolerate_roundoff_in_declared_units(tmp_path, bundle):
    bundle["baseline"]["aggregate"]["attribution_totals"][0]["active_linking_residual"] = 0.5e-10
    bundle["stress"][0]["active_cumulative_return_pp"] += 0.5e-8
    _save(tmp_path, bundle)
    validate_release_bundle(tmp_path)


@pytest.mark.parametrize("net,drawdown", [(-100, -100), (0, 0), (150, 0)])
def test_stress_valid_boundary_returns_and_drawdowns(tmp_path, bundle, net, drawdown):
    row = bundle["stress"][0]
    row.update(net_return_pct=net, window_max_drawdown_pct=drawdown,
               active_cumulative_return_pp=net - row["benchmark_return_pct"])
    _save(tmp_path, bundle)
    validate_release_bundle(tmp_path)


@pytest.mark.parametrize("where", ["map", "scalar", "stress"])
def test_finite_huge_json_integers_fail_closed_without_arithmetic_exception(tmp_path, bundle, where):
    huge = 10 ** 308
    row = bundle["baseline"]["aggregate"]["attribution_totals"][0]
    if where == "map":
        row["linked_asset_pnl"] = {"AA": huge, "BB": huge}
        row["linked_cost_contribution"] = 0.0
    elif where == "scalar":
        row["portfolio_total_return"] = huge
        row["benchmark_total_return"] = -huge
        row["linked_asset_pnl"] = {"AA": huge, "BB": 0}
        row["linked_benchmark_pnl"] = {"AA": -huge, "BB": 0}
        row["linked_cost_contribution"] = 0.0
    else:
        bundle["stress"][0].update(net_return_pct=huge, benchmark_return_pct=huge,
                                   active_cumulative_return_pp=-huge, window_max_drawdown_pct=0)
    _save(tmp_path, bundle)
    with pytest.raises(ReleaseEvidenceError, match="disagreement"):
        validate_release_bundle(tmp_path)


@pytest.mark.parametrize("field,value", [("total_cost_dollars", 2.0), ("terminal_nav", 200.0)])
def test_matching_scenario_and_reconstructed_values_must_match_linked_cost(tmp_path, bundle, field, value):
    # Both tables and all hashes agree, but the unchanged linked cost contradicts them.
    bundle["scenarios"][0][field] = value
    bundle["baseline"]["aggregate"]["path_metrics"][0][field] = value
    _save(tmp_path, bundle)
    with pytest.raises(ReleaseEvidenceError, match="cost-NAV disagreement"):
        validate_release_bundle(tmp_path)


@pytest.mark.parametrize("field,value", [("total_cost_dollars", -1.0), ("terminal_nav", 0.0), ("terminal_nav", -100.0)])
def test_cross_table_funded_path_domain(tmp_path, bundle, field, value):
    bundle["scenarios"][0][field] = value
    bundle["baseline"]["aggregate"]["path_metrics"][0][field] = value
    _save(tmp_path, bundle)
    with pytest.raises(ReleaseEvidenceError, match="funded-path domain"):
        validate_release_bundle(tmp_path)


@pytest.mark.parametrize("growth,cost,capital", [(1.1, 2.0, 100.0), (0.8, 0.0, 250.0), (1.0, 10.0, 1000.0)])
def test_cross_table_identity_accepts_gains_losses_zero_cost_and_different_capital(tmp_path, bundle, growth, cost, capital):
    row = bundle["baseline"]["aggregate"]["attribution_totals"][0]
    total = growth - 1.0
    linked_cost = -cost / capital
    row.update(portfolio_total_return=total, active_total_return_difference=total - 0.03,
               linked_cost_contribution=linked_cost)
    row["linked_asset_pnl"] = {"AA": total - linked_cost, "BB": 0.0}
    row["linked_active_asset_pnl"] = {"AA": total - linked_cost - 0.01, "BB": -0.02}
    for target in (bundle["scenarios"][0], bundle["baseline"]["aggregate"]["path_metrics"][0]):
        target.update(terminal_nav=capital * growth, total_cost_dollars=cost)
    _save(tmp_path, bundle)
    validate_release_bundle(tmp_path)


def test_cross_table_cost_identity_accepts_fraction_roundoff(tmp_path, bundle):
    for target in (bundle["scenarios"][0], bundle["baseline"]["aggregate"]["path_metrics"][0]):
        target["total_cost_dollars"] += 0.5e-10 * 100
    _save(tmp_path, bundle)
    validate_release_bundle(tmp_path)


@pytest.mark.parametrize("total", [0.1, -1.0, -1.1])
def test_coherent_attribution_change_cannot_bypass_cross_table_check(tmp_path, bundle, total):
    row = bundle["baseline"]["aggregate"]["attribution_totals"][0]
    row["portfolio_total_return"] += total
    row["active_total_return_difference"] += total
    row["linked_asset_pnl"]["AA"] += total
    row["linked_active_asset_pnl"]["AA"] += total
    _save(tmp_path, bundle)
    with pytest.raises(ReleaseEvidenceError, match="attribution/reconstructed"):
        validate_release_bundle(tmp_path)
