"""Run the independent challenger against saved licensed research, offline.

Only aggregate evidence is released. Injected faults operate on copies in memory;
the original source, production simulation and portfolio files are never changed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import time

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False, default=str) + "\n", encoding="utf-8")


def stress_summary(root: Path) -> list[dict]:
    """Fixed, already-exposed historical episodes; not new holdout evidence."""
    d = pd.read_csv(root / "outputs/wrds_private/daily.csv", parse_dates=["date"])
    b = pd.read_csv(root / "outputs/wrds_private/benchmark.csv", parse_dates=["date"])
    episodes = [("COVID selloff", "2020-02-19", "2020-03-23"),
                ("2022 stock/bond drawdown", "2021-12-31", "2022-12-30")]
    result = []
    for episode, start, end in episodes:
        cut = d[(d.date > start) & (d.date <= end)]
        bc = b[(b.date > start) & (b.date <= end)]
        bm = float(np.prod(1 + bc.benchmark_return) - 1)
        for (client, method), g in cut.groupby(["client", "method"], sort=True):
            curve = np.r_[1., np.cumprod(1 + g.sort_values("date").net_return)]
            result.append({"episode": episode, "start_close_exclusive": start,
                           "end_close_inclusive": end, "client": client, "method": method,
                           "sessions": len(g), "net_return_pct": float((curve[-1] - 1) * 100),
                           "benchmark_return_pct": bm * 100,
                           "active_cumulative_return_pp": float((curve[-1] - 1 - bm) * 100),
                           "window_max_drawdown_pct": float((curve / np.maximum.accumulate(curve) - 1).min() * 100)})
    return result


def run(root: Path = ROOT):
    from oversight_core import run_validation

    public, private = root / "outputs/oversight", root / "outputs/oversight_private"
    public.mkdir(parents=True, exist_ok=True)
    private.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat()
    timer = time.perf_counter()
    paths = [root / p for p in ["data/wrds/daily.csv", "data/wrds/calendar.csv", "data/wrds/identities.csv",
        "data/wrds/manifest.json", "outputs/wrds_private/daily.csv", "outputs/wrds_private/trades.csv",
        "outputs/wrds_private/decisions.csv", "outputs/wrds_private/benchmark.csv", "outputs/wrds/run_summary.json"]]
    before = {str(p.relative_to(root)).replace("\\", "/"): sha256(p) for p in paths}
    print("Running independent baseline reconciliation", flush=True)
    baseline = run_validation(root, output_private=private / "baseline")
    dump(public / "validation_summary.json", baseline)
    if baseline["status"] != "PASS":
        raise RuntimeError("Baseline failed independent validation; public release is blocked. Inspect validation_summary.json.")

    source = pd.read_csv(root / "data/wrds/daily.csv", keep_default_na=False)
    trades = pd.read_csv(root / "outputs/wrds_private/trades.csv")
    decisions = pd.read_csv(root / "outputs/wrds_private/decisions.csv")
    mutations = []
    wrong_return = source.copy(deep=True)
    wrong_return["total_return"] = pd.to_numeric(wrong_return.ex_distribution_return, errors="raise")
    mutations.append(("INC-001", "Distribution-return definition mismatch", {"returns": wrong_return},
        "Replaced total returns with ex-distribution returns in an in-memory copy of the full source panel.",
        "Data field mapping", "Restore CRSP CIZ DlyRet and reconcile distributions without adding DLRET again.",
        "Data engineering + portfolio analytics", "Independent return/NAV reconstruction must disagree with the saved total-return portfolio."))
    duplicate = pd.concat([trades, trades.iloc[[0]]], ignore_index=True)
    mutations.append(("INC-002", "Duplicate trade record", {"trades": duplicate},
        "Duplicated exactly one trade-key row in an in-memory copy.", "Join cardinality / ingestion",
        "Reject duplicate natural keys before aggregation; identify upstream duplication and reload a unique snapshot.",
        "Trade data operations", "One (date, client, method, ticker) key must identify one trade row."))
    lookahead = decisions.copy(deep=True)
    lookahead.loc[0, "signal_date"] = lookahead.loc[0, "execution_date"]
    mutations.append(("INC-003", "Same-day decision timestamp", {"decisions": lookahead},
        "Changed one signal date to equal its execution date.", "Decision clock",
        "Require the decision to reference the previous close and a strictly earlier complete risk window.",
        "Quant research", "Signal date must be earlier than execution and match the declared previous-close clock."))
    breach = decisions.copy(deep=True)
    ix = breach.index[breach.client.eq("No gold")][0]
    breach.loc[ix, "weight_GLD"] += .01
    breach.loc[ix, "weight_SPY"] -= .01
    mutations.append(("INC-004", "Prohibited asset allocation", {"decisions": breach},
        "Moved one percentage point from SPY to prohibited GLD in one No gold proposal; weights still sum to one.",
        "Mandate / trade construction", "Reject the proposal and re-solve under the separately declared client bounds.",
        "Portfolio management", "A normalized portfolio can still violate its mandate; prohibited asset weights must be zero within tolerance."))
    fees = trades.copy(deep=True)
    fees.loc[0, "cost_dollars"] += 100.
    mutations.append(("INC-005", "Trade-fee reconciliation error", {"trades": fees},
        "Added $100 to one recorded trade fee without changing holdings or actual trade notional.",
        "Cost accounting", "Recompute each fee from absolute notional and rate; reconcile fees and funded NAV.",
        "Portfolio accounting", "Independent SQL cost and cash-funding identities must flag the discrepancy."))
    cases = []
    expected_checks = {
        "INC-001": {"daily_nav_reconstruction", "daily_gross_reconciliation", "daily_net_reconciliation"},
        "INC-002": {"unique_keys_trades"},
        "INC-003": {"decision_chronology", "decision_risk_window"},
        "INC-004": {"decision_constraint_bounds"},
        "INC-005": {"trade_cost_formula", "sql_fee_error", "sql_funding_error"},
    }
    for key, title, overrides, injected, cause, action, owner, criterion in mutations:
        print(f"Running {key}: {title}", flush=True)
        r = run_validation(root, overrides=overrides)
        failed = [c for c in r.get("checks", []) if c.get("status") not in {"PASS", "WARN", "INFO", "SKIP"}]
        domain_detected = bool(expected_checks[key] & {c["id"] for c in failed})
        case = {"id": key, "title": title, "classification": "DELIBERATELY INJECTED TEST CASE",
                "severity": "BLOCK", "expected_status": "BLOCK", "observed_status": r["status"],
                "detected": r["status"] == "BLOCK" and domain_detected,
                "expected_domain_checks_any": sorted(expected_checks[key]),
                "expected_domain_failure_observed": domain_detected,
                "injection": injected, "root_cause": cause,
                "corrective_action": action, "suggested_operational_owner": owner,
                "acceptance_criterion": criterion, "failed_checks": failed,
                "aggregate_impact": r.get("aggregate", {}), "blockers": r.get("blockers", [])}
        cases.append(case)
        dump(private / f"{key}_receipt.json", r)
    print("Retesting original unchanged inputs after all injections", flush=True)
    repaired = run_validation(root)
    after = {str(p.relative_to(root)).replace("\\", "/"): sha256(p) for p in paths}
    unchanged = before == after
    for case in cases:
        case["corrected_retest"] = repaired["status"]
        case["closure"] = "CLOSED_TEST_CASE" if case["detected"] and repaired["status"] == "PASS" and unchanged else "OPEN"
    incident_summary = {"cases": cases, "injected_case_count": len(cases),
                        "detected_case_count": sum(c["detected"] for c in cases),
                        "corrected_retest_status": repaired["status"], "original_inputs_unchanged": unchanged,
                        "scope": "Controlled fault-injection experiments, not real production incidents. Original files never modified."}
    dump(public / "incident_summary.json", incident_summary)
    dump(public / "historical_stress.json", stress_summary(root))
    files = [root / "run_oversight.py", root / "oversight_core.py", root / "oversight_contract.json"] + sorted((root / "sql").glob("oversight_*.sql"))
    release = {"run_id": "oversight-" + started[:19].replace(":", "").replace("-", ""),
        "started_utc": started, "completed_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": round(time.perf_counter() - timer, 3), "python": platform.python_version(),
        "baseline_status": baseline["status"], "injected_cases": len(cases),
        "detected_cases": sum(c["detected"] for c in cases), "corrected_retest_status": repaired["status"],
        "original_inputs_unchanged": unchanged, "input_sha256": before,
        "challenger_code_sha256": {str(p.relative_to(root)).replace("\\", "/"): sha256(p) for p in files},
        "status": "PASS" if all(c["closure"] == "CLOSED_TEST_CASE" for c in cases) else "BLOCK",
        "interpretation": "Technical evidence-release decision only. Not investment approval, an actual order gate, or a claim of future alpha.",
        "source": "Existing WRDS/CRSP current-vintage historical research; no fresh market-data retrieval.",
        "privacy": "Only aggregate challenger/incident/stress receipts are public. Security-day source, detailed holdings, contributions and trades remain local."}
    dump(public / "run_receipt.json", release)
    print(json.dumps({k: release[k] for k in ["run_id", "status", "elapsed_seconds", "injected_cases", "detected_cases", "corrected_retest_status", "original_inputs_unchanged"]}, indent=2))
    if release["status"] != "PASS":
        raise RuntimeError("Fault-injection suite failed; no public release.")
    return release


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    run()
