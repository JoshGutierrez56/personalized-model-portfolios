"""No-login portfolio-control walkthrough using inspectable artificial inputs.

Run ``python run_public_demo.py`` or add ``--no-write`` for a read-only CI/demo
run. This does not fetch market data, execute an optimizer, or replay the WRDS
study. It writes only outputs/public_demo/public_demo_receipt.json and a short
Markdown walkthrough. Source teaching inputs are never edited.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile

import pandas as pd

from oversight_core import run_validation


ROOT = Path(__file__).resolve().parent
BANNER = "ARTIFICIAL TEACHING DEMO - NOT MARKET DATA OR INVESTMENT EVIDENCE"


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_inputs(common_contract, scenario):
    """Expand the hand-worked ledger; never call the production simulator.

    Closing NAVs, trade amounts, gains and fees are literal worked inputs in the
    JSON, not outputs calculated by the challenger. Only ratios, copied labels
    and the validator's tabular schema are assembled here.
    """
    contract = copy.deepcopy(common_contract)
    days = pd.to_datetime(scenario["dates"], format="ISO8601")
    evaluation = days[2:]
    contract.update({"source_start": scenario["dates"][0], "source_end": scenario["dates"][-1]})
    contract["config"] = {"start": str(evaluation[0].date()), "end": str(evaluation[-1].date()),
        "lookback": 2, "cost_bps": scenario["cost_bps"], "allowance_bps": 25,
        "initial_value": 100.0, "covariance": "sample"}
    tickers = contract["tickers"]
    client, method = contract["clients"][0]["name"], contract["methods"][0]
    nav, benchmark_nav = scenario["evaluation_nav"], scenario["benchmark_nav"]
    prior, benchmark_prior = [100.0]+nav[:-1], [100.0]+benchmark_nav[:-1]
    daily, benchmark, decisions, trades = [], [], [], []
    for i, date in enumerate(evaluation):
        gross = scenario["gross_return_numerators"][i]/prior[i]
        net, b_return = nav[i]/prior[i]-1, benchmark_nav[i]/benchmark_prior[i]-1
        daily.append({"date": date, "client": client, "method": method, "nav": nav[i],
            "gross_return": gross, "net_return": net, "benchmark_return": b_return,
            "gross_active_return": gross-b_return, "net_active_return": net-b_return,
            "cost_dollars": scenario["cost_dollars"][i],
            "rebalance": i in scenario["execution_offsets"], "max_weight_limit_drift": 0.0})
        benchmark.append({"date": date, "benchmark_nav": benchmark_nav[i], "benchmark_return": b_return})
    for j, i in enumerate(scenario["execution_offsets"]):
        date, position = evaluation[i], i+2
        decisions.append({"client": client, "method": method, "signal_date": days[position-1],
            "execution_date": date, "history_start": days[position-2], "history_count": 2,
            "shrinkage": 0.0, "estimated_te": 0.0, "minimum_feasible_te": 0.0, "te_budget": 0.0025,
            **{"weight_"+ticker: 0.5 for ticker in tickers}})
        for k, ticker in enumerate(tickers):
            trades.append({"date": date, "signal_date": days[position-1], "client": client,
                "method": method, "ticker": ticker,
                **{field: scenario[field][j][k] for field in
                   ["pretrade_dollars", "posttrade_dollars", "trade_dollars", "trade_cost_dollars"]}})
            trades[-1]["cost_dollars"] = trades[-1].pop("trade_cost_dollars")
    returns = pd.DataFrame([{"date": date, "ticker": ticker, "total_return": value}
        for date, values in zip(days, scenario["returns_by_date"])
        for ticker, value in zip(tickers, values)])
    return {"contract": contract, "calendar": pd.DataFrame({"date": days}), "returns": returns,
            "daily": pd.DataFrame(daily), "benchmark": pd.DataFrame(benchmark),
            "decisions": pd.DataFrame(decisions), "trades": pd.DataFrame(trades)}


def _fingerprints(cases):
    return {name: {table: hashlib.sha256((frame.to_csv(index=False) if isinstance(frame, pd.DataFrame)
                         else json.dumps(frame, sort_keys=True, allow_nan=False)).encode("utf-8")).hexdigest()
                   for table, frame in inputs.items()} for name, inputs in cases.items()}


def _baseline_summary(scenario, validation):
    aggregate = validation.get("aggregate", {})
    metrics = aggregate.get("path_metrics", [{}])[0]
    totals = aggregate.get("attribution_totals", [{}])[0]
    observations = {name: metrics.get(name, totals.get(name)) for name in scenario["expected"]}
    matching = validation["status"] == "PASS"
    for name, expected in scenario["expected"].items():
        if isinstance(expected, dict):
            actual = observations[name]
            matching = matching and isinstance(actual, dict) and set(actual) == set(expected)
            pairs = [(actual.get(key), value) for key, value in expected.items()] if isinstance(actual, dict) else [(None, None)]
        else:
            pairs = [(observations[name], expected)]
        matching = matching and all(isinstance(a, (int, float)) and isinstance(b, (int, float))
                                    and math.isclose(a, b, rel_tol=0, abs_tol=1e-10) for a, b in pairs)
    return {"id": scenario["id"], "title": scenario["title"], "status": validation["status"],
            "hand_values_match": matching, "expected": scenario["expected"], "observed": observations,
            "derivation": scenario["derivation"], "validation": validation}


def _injections(cases):
    specs = [
        ("DEMO-001", "Source-return inconsistency", "zero_cost_wealth", {"daily_nav_reconstruction", "daily_gross_reconciliation"},
         "Change the first evaluation return for AA from 10% to 11% while leaving the saved ledger unchanged.",
         "Restore the declared source return and rerun the original ledger."),
        ("DEMO-002", "Duplicate trade key", "zero_cost_wealth", {"unique_keys_trades"},
         "Duplicate one (date, client, method, ticker) record before any aggregation.",
         "Reject the duplicate snapshot; reload the original unique-key source."),
        ("DEMO-003", "Same-day decision clock", "zero_cost_wealth", {"decision_chronology", "decision_risk_window"},
         "Set the first signal date equal to its execution date.",
         "Restore the previous-close signal and declared trailing history window."),
        ("DEMO-004", "Out-of-bounds allocation", "zero_cost_wealth", {"decision_constraint_bounds"},
         "Change the first proposal to 110% AA / -10% BB: it sums to 100%, but violates long-only bounds.",
         "Restore the feasible 50/50 proposal; full investment alone is insufficient."),
        ("DEMO-005", "Recorded fee mismatch", "funded_fee", {"trade_cost_formula", "sql_fee_error"},
         "Add $0.10 to one recorded trade fee without changing its notional or holdings.",
         "Restore the hand-calculated fee and reconcile both cost and cash funding."),
    ]
    for key, title, scenario, expected, description, repair in specs:
        mutated = copy.deepcopy(cases[scenario])
        if key == "DEMO-001": mutated["returns"].loc[4, "total_return"] = 0.11
        elif key == "DEMO-002": mutated["trades"] = pd.concat([mutated["trades"], mutated["trades"].iloc[[0]]], ignore_index=True)
        elif key == "DEMO-003": mutated["decisions"].loc[0, "signal_date"] = mutated["decisions"].loc[0, "execution_date"]
        elif key == "DEMO-004": mutated["decisions"].loc[0, ["weight_AA", "weight_BB"]] = [1.1, -0.1]
        else: mutated["trades"].loc[0, "cost_dollars"] += 0.1
        yield {"id": key, "title": title, "scenario": scenario, "expected_domain_checks_all": sorted(expected),
               "injection": description, "corrective_action": repair}, mutated


def _markdown(receipt):
    lines = ["# Public Portfolio-Control Teaching Walkthrough", "", "**"+BANNER+"**", "",
             "Overall result: **"+receipt["status"]+"**. No login, licensed data, optimizer, or market-data network call.", "",
             "## Hand-worked baselines", ""]
    for baseline in receipt["baselines"]:
        lines += ["### "+baseline["title"], "", baseline["derivation"], "",
                  f"Validation: {baseline['status']}; hand values match: {baseline['hand_values_match']}.", ""]
    lines += ["## Deliberately dirty inputs", ""]
    for incident in receipt["incidents"]:
        lines += ["### "+incident["id"]+": "+incident["title"], "", incident["injection"], "",
                  "Expected controls: "+", ".join("`"+name+"`" for name in incident["expected_domain_checks_all"])+".", "",
                  f"Detected: {incident['detected']}; corrected original-input retest: {incident['corrected_retest']}.", "",
                  incident["corrective_action"], ""]
    lines += ["## What the evidence does and does not show", "",
              f"Both source JSON bytes and expanded input fingerprints unchanged: {receipt['inputs_unchanged']}.", "",
              "The original in-memory inputs are restored by discarding each faulty copy; no automatic data repair is claimed. "
              "A generic exception does not count as successful diagnosis: every named domain control must block. "
              "These are controlled teaching cases, not real production incidents, investment performance, or a replay of the licensed empirical study.", ""]
    return "\n".join(lines)


def _write_artifacts(root, receipt):
    destination = Path(root).resolve()/"outputs/public_demo"
    if destination.resolve() != destination:
        raise ValueError("Public demo output directory must not redirect to another artifact tree")
    destination.mkdir(parents=True, exist_ok=True)
    payloads = {"public_demo_receipt.json": json.dumps(receipt, indent=2, allow_nan=False)+"\n",
                "public_demo_walkthrough.md": _markdown(receipt)}
    for filename, content in payloads.items():
        final, temporary = destination/filename, None
        if final.is_symlink():
            raise ValueError("Public demo output file must not redirect to another artifact")
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="",
                    dir=destination, prefix=".public-demo-", suffix=".tmp", delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(content)
            os.replace(temporary, final)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()


def run_demo(root=ROOT, *, write=True):
    root = Path(root)
    input_path = root/"examples/hand_worked_inputs.json"
    source_before = _sha(input_path)
    source = json.loads(input_path.read_text(encoding="utf-8"))
    cases = {s["id"]: build_inputs(source["common_contract"], s) for s in source["scenarios"]}
    before = _fingerprints(cases)
    baselines, incidents = [], []
    # Never pass the checkout root: a local WRDS manifest/run_summary must not
    # contaminate or be required by this self-contained artificial demonstration.
    with tempfile.TemporaryDirectory(prefix="portfolio-public-demo-") as empty_root:
        validation_root = Path(empty_root)
        for scenario in source["scenarios"]:
            baselines.append(_baseline_summary(scenario, run_validation(validation_root, overrides=cases[scenario["id"]])))
        for incident, dirty in _injections(cases):
            result = run_validation(validation_root, overrides=dirty)
            expected = set(incident["expected_domain_checks_all"])
            incident.update({"observed_status": result["status"], "blockers": result["blockers"],
                "detected": result["status"] == "BLOCK" and expected.issubset(result["blockers"])
                            and "validator_execution" not in result["blockers"]})
            incidents.append(incident)
        retests = {key: run_validation(validation_root, overrides=value)["status"] for key, value in cases.items()}
    after = _fingerprints(cases)
    unchanged = before == after and source_before == _sha(input_path)
    for incident in incidents:
        incident["corrected_retest"] = retests[incident["scenario"]]
    passed = (all(b["status"] == "PASS" and b["hand_values_match"] for b in baselines)
              and all(i["detected"] and i["corrected_retest"] == "PASS" for i in incidents) and unchanged)
    receipt = {"schema_version": "1.0", "classification": BANNER,
        "completed_utc": datetime.now(timezone.utc).isoformat(), "status": "PASS" if passed else "BLOCK",
        "source_input_sha256": source_before, "expanded_input_sha256_before": before,
        "expanded_input_sha256_after": after, "inputs_unchanged": unchanged,
        "baselines": baselines, "incidents": incidents,
        "detected_cases": sum(i["detected"] for i in incidents), "injected_cases": len(incidents),
        "corrected_retests": retests,
        "scope": "Artificial arithmetic/control demonstration only. Not market evidence, production experience, or optimizer certification."}
    if write:
        _write_artifacts(root, receipt)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-write", action="store_true", help="Print results without creating repository output artifacts.")
    args = parser.parse_args(argv)
    print(BANNER, flush=True)
    try:
        receipt = run_demo(write=not args.no_write)
    except Exception as exc:
        print("BLOCK: demo could not complete ("+type(exc).__name__+").", file=sys.stderr)
        return 1
    for baseline in receipt["baselines"]:
        nav = baseline["observed"]["terminal_nav"]
        displayed_nav = format(nav, ".12g") if isinstance(nav, (int, float)) else "unavailable"
        print(f"{baseline['id']}: {baseline['status']}; hand values match={baseline['hand_values_match']}; terminal NAV={displayed_nav}")
    for incident in receipt["incidents"]:
        print(f"{incident['id']} {incident['title']}: detected={incident['detected']}; corrected retest={incident['corrected_retest']}")
    print(f"{receipt['status']}: {receipt['detected_cases']}/{receipt['injected_cases']} named faults detected; inputs unchanged={receipt['inputs_unchanged']}.")
    if not args.no_write:
        print("Artifacts: outputs/public_demo/public_demo_receipt.json and public_demo_walkthrough.md")
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
