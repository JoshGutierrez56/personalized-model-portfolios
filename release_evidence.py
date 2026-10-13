"""Fail-closed consistency checks for the public, aggregate-only evidence bundle.

This verifies a receipt-bound snapshot, not the truth of its source observations or
an authenticated signature. It never opens licensed inputs or hashes current code.
Hash-bound public artifacts must retain their exact bytes in a Git checkout.
"""
from __future__ import annotations

import csv
from datetime import date
import hashlib
import io
import json
import math
from pathlib import Path
import re


PUBLIC_ARTIFACTS = {
    "baseline": "outputs/oversight/validation_summary.json",
    "incidents": "outputs/oversight/incident_summary.json",
    "stress": "outputs/oversight/historical_stress.json",
    "scenarios": "outputs/wrds/scenario_summary.csv",
}
SOURCE_PATHS = {
    "returns": "data/wrds/daily.csv",
    "calendar": "data/wrds/calendar.csv",
    "daily": "outputs/wrds_private/daily.csv",
    "decisions": "outputs/wrds_private/decisions.csv",
    "trades": "outputs/wrds_private/trades.csv",
    "benchmark": "outputs/wrds_private/benchmark.csv",
}
SCENARIO_NUMBERS = (
    "days", "net_cagr_pct", "net_volatility_pct", "max_drawdown_pct",
    "gross_te_pct", "net_te_pct", "annual_one_way_turnover_pct",
    "annual_incurred_cost_bps", "total_cost_dollars", "terminal_nav",
    "rebalance_count", "days_weight_limits_drifted", "max_weight_limit_drift_pp",
)
# CSV field -> independently reconstructed field, scaling into CSV units, and
# absolute tolerance. Percent/TE tolerances correspond to 1e-10 in fractions.
SCENARIO_RECONCILIATION = {
    "terminal_nav": ("terminal_nav", 1, 1e-4),
    "total_cost_dollars": ("total_cost_dollars", 1, 1e-4),
    "gross_te_pct": ("gross_tracking_error", 100, 1e-8),
    "net_te_pct": ("net_tracking_error", 100, 1e-8),
    "net_cagr_pct": ("net_cagr_pct", 1, 1e-8),
    "net_volatility_pct": ("net_volatility_pct", 1, 1e-8),
    "max_drawdown_pct": ("max_drawdown_pct", 1, 1e-8),
    "annual_one_way_turnover_pct": ("annual_one_way_turnover_pct", 1, 1e-8),
    "annual_incurred_cost_bps": ("annual_incurred_cost_bps", 1, 1e-6),
    "days_weight_limits_drifted": ("all_days_weight_limits_drifted", 1, 0),
    "max_weight_limit_drift_pp": ("maximum_interim_bound_drift", 100, 2e-4),
}
# Attribution is expressed in return fractions; stress in percentage points.
RETURN_TOLERANCE = 1e-10
PERCENTAGE_POINT_TOLERANCE = 1e-8
ATTRIBUTION_SCALARS = (
    "portfolio_total_return", "benchmark_total_return",
    "active_total_return_difference", "linked_cost_contribution",
    "active_linking_residual",
)
ATTRIBUTION_MAPS = (
    "linked_asset_pnl", "linked_benchmark_pnl", "linked_active_asset_pnl",
)


class ReleaseEvidenceError(ValueError):
    """The public evidence cannot safely be presented as a passing release."""


def _require(condition, message):
    if not condition:
        raise ReleaseEvidenceError(f"Release evidence rejected: {message}")


def _mapping(value, name):
    _require(isinstance(value, dict), f"{name} must be an object")
    return value


def _sequence(value, name, nonempty=False):
    _require(isinstance(value, list), f"{name} must be an array")
    _require(not nonempty or bool(value), f"{name} must not be empty")
    return value


def _integer(value, name, positive=False):
    _require(type(value) is int and value >= (1 if positive else 0),
             f"{name} must be a {'positive' if positive else 'nonnegative'} integer")
    return value


def _number(value, name):
    _require(type(value) in (int, float), f"{name} must be a finite number")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    _require(finite, f"{name} must be a finite number")
    return value


def _finite_tree(value, name):
    if isinstance(value, dict):
        for key, item in value.items():
            _finite_tree(item, f"{name}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _finite_tree(item, f"{name}[{index}]")
    elif type(value) in (int, float):
        _number(value, name)


def _read_bytes(path):
    try:
        return path.read_bytes()
    except OSError as exc:
        raise ReleaseEvidenceError(f"Release evidence rejected: cannot read {path.name}: {exc.strerror}") from exc


def _json(raw, name):
    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, f"{name} has duplicate JSON key {key!r}")
            result[key] = value
        return result
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ReleaseEvidenceError(f"Release evidence rejected: invalid JSON in {name}") from exc
    _finite_tree(value, name)
    return value


def _digest(value, name):
    _require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
             f"{name} must be a lowercase SHA-256 fingerprint")
    return value


def _path_pair(row, name):
    for key in ("client", "method"):
        _require(isinstance(row.get(key), str) and bool(row[key].strip()), f"{name}.{key} must be nonempty text")
    return row["client"], row["method"]


def _date(value, name):
    _require(isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is not None,
             f"{name} must be an ISO YYYY-MM-DD date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ReleaseEvidenceError(f"Release evidence rejected: invalid date in {name}") from exc


def _unique_ids(items, name):
    ids = []
    for index, item in enumerate(items):
        item = _mapping(item, f"{name}[{index}]")
        identifier = item.get("id")
        _require(isinstance(identifier, str) and bool(identifier.strip()), f"{name}[{index}].id must be nonempty")
        ids.append(identifier)
    _require(len(set(ids)) == len(ids), f"{name} contains duplicate IDs")
    return set(ids)


def _checks(checks, name, status):
    checks = _sequence(checks, name, nonempty=True)
    ids = _unique_ids(checks, name)
    for check in checks:
        label = f"{name}.{check['id']}"
        _require(check.get("status") == status, f"{label} must be {status}")
        _integer(check.get("count"), f"{label}.count")
        error = _number(check.get("max_abs_error"), f"{label}.max_abs_error")
        tolerance = _number(check.get("tolerance"), f"{label}.tolerance")
        _require(error >= 0 and tolerance >= 0, f"{label} error/tolerance must be nonnegative")
        _require((error <= tolerance) if status == "PASS" else (error > tolerance),
                 f"{label} residual contradicts its {status} status")
    return ids


def _scenarios(raw):
    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8"), newline=""), strict=True)
        fields = reader.fieldnames or []
        _require(len(fields) == len(set(fields)), "scenario CSV has duplicate columns")
        _require(set(fields) == {"client", "method", *SCENARIO_NUMBERS}, "scenario CSV columns differ from the declared aggregate schema")
        rows = list(reader)
    except (UnicodeError, csv.Error) as exc:
        raise ReleaseEvidenceError("Release evidence rejected: invalid scenario CSV") from exc
    _require(bool(rows), "scenario CSV must not be empty")
    for index, row in enumerate(rows):
        _require(None not in row and all(value is not None for value in row.values()), f"scenario CSV row {index} has a malformed field count")
        for key in ("client", "method"):
            _require(bool(row[key].strip()), f"scenario CSV row {index}.{key} must not be empty")
        for key in SCENARIO_NUMBERS:
            try:
                value = float(row[key])
            except ValueError as exc:
                raise ReleaseEvidenceError(f"Release evidence rejected: scenario CSV row {index}.{key} must be numeric") from exc
            row[key] = _number(value, f"scenario CSV row {index}.{key}")
        for key in ("days", "rebalance_count", "days_weight_limits_drifted"):
            _require(row[key] >= 0 and row[key].is_integer(), f"scenario CSV row {index}.{key} must be a nonnegative integer")
            row[key] = int(row[key])
    return rows


def _attribution(attribution, asset_count):
    """Check producer linking identities without assuming initial capital."""
    asset_keys = None
    shared_benchmark = None
    shared_benchmark_return = None
    for row in attribution:
        label = f"attribution {_path_pair(row, 'attribution')}"
        # Normalize individually finite JSON integers before arithmetic: summing
        # huge ints then mixing a float can otherwise raise OverflowError.
        values = {key: float(_number(row.get(key), f"{label}.{key}")) for key in ATTRIBUTION_SCALARS}
        maps = {}
        for key in ATTRIBUTION_MAPS:
            mapping = _mapping(row.get(key), f"{label}.{key}")
            _require(len(mapping) == asset_count and all(isinstance(k, str) and k.strip() for k in mapping),
                     f"{label}.{key} asset count/keys disagreement")
            if asset_keys is None:
                asset_keys = set(mapping)
            _require(set(mapping) == asset_keys, f"{label}.{key} asset coverage disagreement")
            maps[key] = {ticker: float(_number(value, f"{label}.{key}.{ticker}")) for ticker, value in mapping.items()}
        portfolio, benchmark, active = (maps[key] for key in ATTRIBUTION_MAPS)
        cost = values["linked_cost_contribution"]
        _require(cost <= RETURN_TOLERANCE, f"{label} linked cost must be nonpositive")
        if shared_benchmark is None:
            shared_benchmark = benchmark
            shared_benchmark_return = values["benchmark_total_return"]
        _require(abs(values["benchmark_total_return"] - shared_benchmark_return) <= RETURN_TOLERANCE
                 and all(abs(benchmark[t] - shared_benchmark[t]) <= RETURN_TOLERANCE for t in asset_keys),
                 f"{label} shared benchmark disagreement")
        identities = {
            "portfolio linking": sum(portfolio.values()) + cost - values["portfolio_total_return"],
            "benchmark linking": sum(benchmark.values()) - values["benchmark_total_return"],
            "active return difference": values["portfolio_total_return"] - values["benchmark_total_return"] - values["active_total_return_difference"],
        }
        for name, residual in identities.items():
            _require(abs(residual) <= RETURN_TOLERANCE, f"{label} {name} disagreement")
        _require(all(abs(active[t] - (portfolio[t] - benchmark[t])) <= RETURN_TOLERANCE for t in asset_keys),
                 f"{label} per-asset active linking disagreement")
        residual = sum(active.values()) + cost - values["active_total_return_difference"]
        reported = values["active_linking_residual"]
        _require(abs(residual) <= RETURN_TOLERANCE and abs(reported) <= RETURN_TOLERANCE
                 and abs(residual - reported) <= RETURN_TOLERANCE,
                 f"{label} active linking residual disagreement")


def validate_release_bundle(root: Path) -> dict:
    """Return validated ``baseline, incidents, receipt, stress, scenarios``.

    ``scenarios`` is a list of CSV dictionaries with parsed numeric values. Raises
    :class:`ReleaseEvidenceError` on missing, stale, malformed, contradictory, or
    nonfinite evidence. Only five public files are read, including the receipt.
    The receipt's four ``public_artifact_sha256`` keys use repository-relative
    POSIX paths from :data:`PUBLIC_ARTIFACTS` and exact-byte SHA-256 digests.
    """
    root = Path(root)
    receipt = _mapping(_json(_read_bytes(root / "outputs/oversight/run_receipt.json"), "receipt"), "receipt")
    _require(receipt.get("status") == "PASS", "receipt.status must be PASS")
    hashes = _mapping(receipt.get("public_artifact_sha256"), "receipt.public_artifact_sha256")
    loaded = {}
    for name, relative in PUBLIC_ARTIFACTS.items():
        expected = _digest(hashes.get(relative), f"receipt.public_artifact_sha256[{relative}]")
        raw = _read_bytes(root / relative)
        _require(hashlib.sha256(raw).hexdigest() == expected, f"public artifact fingerprint mismatch: {relative}")
        loaded[name] = _scenarios(raw) if name == "scenarios" else _json(raw, name)
    baseline = _mapping(loaded["baseline"], "baseline")
    incidents = _mapping(loaded["incidents"], "incidents")
    _require(baseline.get("status") == receipt.get("baseline_status") == "PASS", "baseline/receipt status disagreement")
    _require(_sequence(baseline.get("blockers"), "baseline.blockers") == [], "baseline contains blockers despite PASS")
    check_ids = _checks(baseline.get("checks"), "baseline.checks", "PASS")
    for name, value in (("receipt", receipt), ("incidents", incidents)):
        _require(value.get("original_inputs_unchanged") is True, f"{name}.original_inputs_unchanged must be true")
        _require(value.get("corrected_retest_status") == "PASS", f"{name}.corrected_retest_status must be PASS")
    cases = _sequence(incidents.get("cases"), "incidents.cases", nonempty=True)
    _unique_ids(cases, "incidents.cases")
    for name, source, key in (
        ("receipt", receipt, "injected_cases"), ("receipt", receipt, "detected_cases"),
        ("incidents", incidents, "injected_case_count"), ("incidents", incidents, "detected_case_count"),
    ):
        _require(_integer(source.get(key), f"{name}.{key}", positive=True) == len(cases), f"{name}.{key} count disagreement")
    for case in cases:
        label = f"incident {case['id']}"
        for key in ("expected_status", "observed_status", "severity"):
            _require(case.get(key) == "BLOCK", f"{label}.{key} must be BLOCK")
        for key in ("detected", "expected_domain_failure_observed"):
            _require(case.get(key) is True, f"{label}.{key} must be true")
        _require(case.get("corrected_retest") == "PASS", f"{label}.corrected_retest must be PASS")
        _require(case.get("closure") == "CLOSED_TEST_CASE", f"{label}.closure must be CLOSED_TEST_CASE")
        failed = _checks(case.get("failed_checks"), f"{label}.failed_checks", "BLOCK")
        _require(failed <= check_ids, f"{label} cites failed controls absent from the baseline catalog")
        expected = _sequence(case.get("expected_domain_checks_any"), f"{label}.expected_domain_checks_any", nonempty=True)
        _require(all(isinstance(item, str) for item in expected), f"{label} expected domain controls must be strings")
        _require(set(expected) <= check_ids and bool(set(expected) & failed), f"{label} lacks an actual expected domain failure")
        blockers = _sequence(case.get("blockers"), f"{label}.blockers", nonempty=True)
        _require(all(isinstance(item, str) for item in blockers), f"{label} blockers must be strings")
        _require(len(blockers) == len(set(blockers)) and set(blockers) == failed, f"{label} blockers disagree with failed controls")
    provenance = _mapping(baseline.get("provenance"), "baseline.provenance")
    _require(provenance.get("engine_imported") is False, "baseline must not import the production engine")
    _require(provenance.get("override_sha256") == {}, "baseline must not use overridden inputs")
    sources = _mapping(provenance.get("source_sha256"), "baseline.provenance.source_sha256")
    inputs = _mapping(receipt.get("input_sha256"), "receipt.input_sha256")
    for alias, relative in SOURCE_PATHS.items():
        source = _digest(sources.get(alias), f"baseline source {alias}")
        _require(source == _digest(inputs.get(relative), f"receipt input {relative}"), f"source fingerprint disagreement: {alias}")
    aggregate = _mapping(baseline.get("aggregate"), "baseline.aggregate")
    counts = {key: _integer(aggregate.get(key), f"baseline.aggregate.{key}", positive=True) for key in (
        "paths", "evaluation_dates", "execution_dates", "source_dates", "assets", "returns_rows",
        "calendar_rows", "daily_rows", "decisions_rows", "trades_rows", "benchmark_rows",
    )}
    for key, expected in {
        "returns_rows": counts["source_dates"] * counts["assets"],
        "calendar_rows": counts["source_dates"],
        "daily_rows": counts["paths"] * counts["evaluation_dates"],
        "decisions_rows": counts["paths"] * counts["execution_dates"],
        "trades_rows": counts["decisions_rows"] * counts["assets"],
        "benchmark_rows": counts["evaluation_dates"],
    }.items():
        _require(counts[key] == expected, f"baseline.aggregate.{key} count disagreement")
    scenarios = loaded["scenarios"]
    paths = {_path_pair(row, "scenario") for row in scenarios}
    _require(len(paths) == len(scenarios) == counts["paths"], "scenario path count disagreement or duplicate path")
    for row in scenarios:
        _require(row["days"] == counts["evaluation_dates"] and row["rebalance_count"] == counts["execution_dates"], "scenario evaluation/rebalance count disagreement")
    metrics = _sequence(aggregate.get("path_metrics"), "baseline.aggregate.path_metrics", nonempty=True)
    _require(all(isinstance(row, dict) for row in metrics), "reconstructed metric rows must be objects")
    metrics_by_path = {_path_pair(row, "reconstructed metric"): row for row in metrics}
    _require(len(metrics) == len(metrics_by_path) == len(paths) and set(metrics_by_path) == paths,
             "reconstructed metric path count/coverage disagreement")
    for row in scenarios:
        pair = _path_pair(row, "scenario")
        metric = metrics_by_path[pair]
        for published, (reconstructed, scale, tolerance) in SCENARIO_RECONCILIATION.items():
            expected = _number(metric.get(reconstructed), f"reconstructed {pair}.{reconstructed}") * scale
            _require(abs(row[published] - expected) <= tolerance,
                     f"scenario/reconstructed metric disagreement: {pair}.{published}")
    attribution = _sequence(aggregate.get("attribution_totals"), "baseline.aggregate.attribution_totals", nonempty=True)
    _require(all(isinstance(row, dict) for row in attribution), "attribution rows must be objects")
    _require(len(attribution) == len(paths) and {_path_pair(row, "attribution") for row in attribution} == paths, "attribution path count/coverage disagreement")
    _attribution(attribution, counts["assets"])
    stress = _sequence(loaded["stress"], "stress", nonempty=True)
    episodes = {}
    episode_windows = {}
    episode_benchmarks = {}
    for index, row in enumerate(stress):
        row = _mapping(row, f"stress[{index}]")
        episode = row.get("episode")
        _require(isinstance(episode, str) and bool(episode.strip()), f"stress[{index}].episode must be nonempty")
        pair = _path_pair(row, f"stress[{index}]")
        _require(pair in paths, f"stress[{index}] has an unknown portfolio path")
        sessions = _integer(row.get("sessions"), f"stress[{index}].sessions", positive=True)
        start = _date(row.get("start_close_exclusive"), f"stress[{index}].start_close_exclusive")
        end = _date(row.get("end_close_inclusive"), f"stress[{index}].end_close_inclusive")
        _require(start < end and sessions <= counts["evaluation_dates"], f"stress[{index}] has inconsistent window bounds/count")
        window = (start, end, sessions)
        _require(episode_windows.setdefault(episode, window) == window, f"stress episode {episode} window/count disagreement")
        values = {key: float(_number(row.get(key), f"stress[{index}].{key}")) for key in (
            "net_return_pct", "benchmark_return_pct", "active_cumulative_return_pp", "window_max_drawdown_pct")}
        net, benchmark = values["net_return_pct"], values["benchmark_return_pct"]
        drawdown = values["window_max_drawdown_pct"]
        tolerance = PERCENTAGE_POINT_TOLERANCE
        _require(net >= -100 - tolerance and benchmark >= -100 - tolerance,
                 f"stress[{index}] return below -100 percent")
        _require(-100 - tolerance <= drawdown <= tolerance and drawdown <= min(0, net) + tolerance,
                 f"stress[{index}] drawdown range/terminal return disagreement")
        _require(abs(values["active_cumulative_return_pp"] - (net - benchmark)) <= tolerance,
                 f"stress[{index}] active gap disagreement")
        _require(abs(episode_benchmarks.setdefault(episode, benchmark) - benchmark) <= tolerance,
                 f"stress episode {episode} shared benchmark disagreement")
        seen = episodes.setdefault(episode, set())
        _require(pair not in seen, f"stress episode {episode} contains a duplicate path")
        seen.add(pair)
    _require(all(seen == paths for seen in episodes.values()), "stress episode path coverage disagreement")
    return {**loaded, "receipt": receipt}
