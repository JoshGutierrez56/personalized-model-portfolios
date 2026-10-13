"""Independent, hand-worked economic fixtures; no production engine imports.

The small artificial calendar is explicitly a unit-test fixture, not market evidence.
"""
import copy
import json
import os
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from oversight_core import _production_text_sha, _sha, run_validation


def synthetic_case(cost_bps=0):
    """Two sleeves; hand-derived holdings, cash costs and benchmark.

    Zero-cost case: initial 60/40, first gain 6/0, reset to 53/53;
    then 53/63.6, then 47.7/63.6 reset to 55.65/55.65;
    terminal 55.65/61.215. Benchmark terminates at 115.7625.
    One-percent-cost case: initial 60/40, flat returns, trades -10.1/+9.9,
    costs .101/.099, terminal 49.9/49.9 = 99.8.
    """
    if cost_bps not in (0, 100):
        raise ValueError("Only hand-worked 0 and 100 bp cases are specified")
    days = pd.to_datetime(["2020-12-30", "2020-12-31", "2021-01-04", "2021-01-05", "2021-02-01", "2021-02-02"])
    if cost_bps:
        days = days[:3]
    contract = {
        "tickers": ["AA", "BB"], "target": [.5, .5], "current": [.6, .4],
        "source_start": str(days[0].date()), "source_end": str(days[-1].date()),
        "annualization": 252, "config": {"start": "2021-01-04", "end": str(days[-1].date()),
            "lookback": 2, "cost_bps": cost_bps, "allowance_bps": 25,
            "initial_value": 100., "covariance": "sample"},
        "methods": ["Minimum risk"], "clients": [{"name": "Fixture", "blocked": [], "floors": {}, "caps": {}}],
        "tolerances": {"dollars": 1e-8, "returns": 1e-10, "weights": 2e-6,
                       "risk": 2e-6, "risk_reconciliation": 1e-10},
        "production_sha256": {}, "require_source_provenance": False,
        "limitations": ["Artificial hand-worked test, not market evidence."],
    }
    values = [[0,0],[0,0],[.1,0],[0,.2],[-.1,0],[0,.1]] if not cost_bps else [[0,0],[0,0],[0,0]]
    returns = pd.DataFrame([{"date":d,"ticker":t,"total_return":v,"ex_distribution_return":v}
                           for d, row in zip(days, values) for t,v in zip(["AA","BB"],row)])
    if cost_bps:
        nav = [99.8]; benchmark_nav = [100.]; costs = [.2]
        pre = [[60.,40.]]; post = [[49.9,49.9]]; change = [[-10.1,9.9]]
        execution_ids = [0]; gross = [0.]
    else:
        nav = [106.,116.6,111.3,116.865]; benchmark_nav = [105.,115.5,110.25,115.7625]
        costs = [0.,0.,0.,0.]; pre = [[66.,40.],[47.7,63.6]]
        post = [[53.,53.],[55.65,55.65]]; change = [[-13.,13.],[7.95,-7.95]]
        execution_ids = [0,2]
        gross = [.06,.1,-5.3/116.6,.05]
    evaluation = days[2:]
    previous = [100.]+nav[:-1]
    b_previous = [100.]+benchmark_nav[:-1]
    net = [n/p-1 for n,p in zip(nav,previous)]
    b_return = [n/p-1 for n,p in zip(benchmark_nav,b_previous)]
    daily = pd.DataFrame([{"date":d,"client":"Fixture","method":"Minimum risk","nav":nav[i],
        "gross_return":gross[i],"net_return":net[i],"benchmark_return":b_return[i],
        "gross_active_return":gross[i]-b_return[i],"net_active_return":net[i]-b_return[i],
        "cost_dollars":costs[i],"rebalance":i in execution_ids,"max_weight_limit_drift":0.}
        for i,d in enumerate(evaluation)])
    benchmark = pd.DataFrame({"date":evaluation,"benchmark_nav":benchmark_nav,"benchmark_return":b_return})
    decisions, trades = [], []
    for j, i in enumerate(execution_ids):
        d = evaluation[i]
        loc = days.get_loc(d)
        decisions.append({"client":"Fixture","method":"Minimum risk","signal_date":days[loc-1],
            "execution_date":d,"history_start":days[loc-2],"history_count":2,"shrinkage":0.,
            "estimated_te":0.,"minimum_feasible_te":0.,"te_budget":.0025,"weight_AA":.5,"weight_BB":.5})
        for k,ticker in enumerate(["AA","BB"]):
            trades.append({"date":d,"signal_date":days[loc-1],"client":"Fixture","method":"Minimum risk",
                "ticker":ticker,"pretrade_dollars":pre[j][k],"posttrade_dollars":post[j][k],
                "trade_dollars":change[j][k],"cost_dollars":abs(change[j][k])*cost_bps/10000})
    return {"contract":contract,"returns":returns,"calendar":pd.DataFrame({"date":days}),
            "daily":daily,"benchmark":benchmark,"decisions":pd.DataFrame(decisions),"trades":pd.DataFrame(trades)}


def check_fixture(tmp_path, case):
    return run_validation(tmp_path, overrides=case)


def test_hand_calculated_wealth_linking_not_summed_daily_returns(tmp_path):
    case = synthetic_case()
    result = check_fixture(tmp_path,case)
    assert result["status"] == "PASS", result["blockers"]
    row = result["aggregate"]["attribution_totals"][0]
    assert row["portfolio_total_return"] == pytest.approx(.16865)
    assert row["benchmark_total_return"] == pytest.approx(.157625)
    assert row["linked_asset_pnl"]["AA"] == pytest.approx(.007)
    assert row["linked_asset_pnl"]["BB"] == pytest.approx(.16165)
    assert row["linked_active_asset_pnl"]["AA"] == pytest.approx(.0095)
    assert row["linked_active_asset_pnl"]["BB"] == pytest.approx(.001525)
    assert row["active_total_return_difference"] == pytest.approx(.011025)
    assert abs(row["active_total_return_difference"]-case["daily"].net_active_return.sum()) > .001
    assert abs(row["active_linking_residual"]) < 1e-12


def test_hand_calculated_costs_funded_without_external_cash(tmp_path):
    result = check_fixture(tmp_path,synthetic_case(100))
    assert result["status"] == "PASS", result["blockers"]
    row = result["aggregate"]["attribution_totals"][0]
    assert row["portfolio_total_return"] == pytest.approx(-.002)
    assert row["linked_cost_contribution"] == pytest.approx(-.002)
    assert result["aggregate"]["path_metrics"][0]["terminal_nav"] == pytest.approx(99.8)
    metrics = result["aggregate"]["path_metrics"][0]
    # One observed day: 20 dollars absolute turnover / 100 pretrade NAV;
    # one-way divides by two, and annualization multiplies by 252.
    assert metrics["annual_one_way_turnover_pct"] == pytest.approx(2520.0)
    assert metrics["annual_incurred_cost_bps"] == pytest.approx(5040.0)
    # The initial capital must be included: a first-day loss is a drawdown.
    assert metrics["max_drawdown_pct"] == pytest.approx(-.2)
    assert metrics["net_cagr_pct"] == pytest.approx((.998**252 - 1) * 100)


@pytest.mark.parametrize("table", ["returns","daily","decisions","trades","benchmark","calendar"])
def test_duplicate_keys_block_without_silent_deduplication(tmp_path,table):
    case = synthetic_case()
    case[table] = pd.concat([case[table],case[table].iloc[[0]]],ignore_index=True)
    result = check_fixture(tmp_path,case)
    assert result["status"] == "BLOCK"
    assert "unique_keys_"+table in result["blockers"]


@pytest.mark.parametrize("table", ["returns","daily","decisions","trades","benchmark"])
def test_missing_expected_records_block(tmp_path,table):
    case = synthetic_case()
    case[table] = case[table].iloc[1:].copy()
    result = check_fixture(tmp_path,case)
    assert result["status"] == "BLOCK"
    assert "source_calendar_complete" in result["blockers"] if table=="returns" else "complete_roster_"+table in result["blockers"]


@pytest.mark.parametrize("bad", [np.nan,np.inf,-np.inf,-1.])
def test_invalid_returns_are_not_filled_or_dropped(tmp_path,bad):
    case = synthetic_case()
    case["returns"].loc[4,"total_return"] = bad
    result = check_fixture(tmp_path,case)
    assert result["status"] == "BLOCK"
    assert "finite_returns" in result["blockers"] or "source_return_domain" in result["blockers"]


def test_mutated_return_hits_economic_reconstruction_not_source_hash(tmp_path):
    case = synthetic_case()
    case["returns"].loc[4,"total_return"] = .08
    result = check_fixture(tmp_path,case)
    assert "daily_nav_reconstruction" in result["blockers"]
    assert "daily_gross_reconciliation" in result["blockers"]
    assert not any("hash" in name for name in result["blockers"])


def test_same_day_signal_and_wrong_window_block(tmp_path):
    case = synthetic_case()
    case["decisions"].loc[0,"signal_date"] = case["decisions"].loc[0,"execution_date"]
    result = check_fixture(tmp_path,case)
    assert {"decision_chronology","decision_risk_window","trade_chronology"} <= set(result["blockers"])


def test_declared_posttrade_weights_are_independently_challenged(tmp_path):
    case = synthetic_case()
    case["decisions"].loc[0,["weight_AA","weight_BB"]] = [1.1,-.1]
    result = check_fixture(tmp_path,case)
    assert {"decision_constraint_bounds","posttrade_decision_weights"} <= set(result["blockers"])


def test_fee_corruption_is_detected_by_python_and_sql(tmp_path):
    case = synthetic_case(100)
    case["trades"].loc[0,"cost_dollars"] += .1
    result = check_fixture(tmp_path,case)
    assert {"trade_cost_formula","sql_fee_error","sql_signed_trade_error"} <= set(result["blockers"])


def test_override_inputs_remain_unmodified_and_detail_stays_private(tmp_path):
    case = synthetic_case()
    prior = copy.deepcopy(case)
    private = tmp_path/"outputs/oversight_private/fixture"
    result = run_validation(tmp_path,case,private)
    assert result["status"] == "PASS", result["blockers"]
    assert (private/"reconstructed_ledger.csv").exists()
    assert "details" not in result and "ledger" not in result
    for name in case:
        if name != "contract":
            pd.testing.assert_frame_equal(case[name],prior[name])


def test_missing_column_returns_structured_block_not_exception(tmp_path):
    case = synthetic_case()
    case["trades"] = case["trades"].drop(columns=["trade_dollars"])
    result = check_fixture(tmp_path,case)
    assert "schema_trades" in result["blockers"]


@pytest.mark.parametrize("bad", [np.nan,np.inf,-1.,1e-4])
def test_invalid_risk_tolerances_cannot_disable_controls(tmp_path,bad):
    case = synthetic_case()
    case["contract"]["tolerances"]["risk"] = bad
    result = check_fixture(tmp_path,case)
    assert "contract_valid" in result["blockers"]


def test_detailed_outputs_cannot_be_written_to_public_directory(tmp_path):
    destination = tmp_path/"outputs/oversight"
    result = run_validation(tmp_path,synthetic_case(),destination)
    assert "private_output_boundary" in result["blockers"]
    assert not destination.exists()


@pytest.mark.parametrize("value", [2,np.nan,"possibly"])
def test_invalid_rebalance_flag_is_not_coerced_to_true(tmp_path,value):
    case = synthetic_case()
    case["daily"]["rebalance"] = case["daily"].rebalance.astype(object)
    case["daily"].loc[0,"rebalance"] = value
    result = check_fixture(tmp_path,case)
    assert "rebalance_flag_domain" in result["blockers"]


def test_complex_return_is_not_silently_cast_to_real(tmp_path):
    case = synthetic_case()
    case["returns"]["total_return"] = case["returns"].total_return.astype(complex)
    case["returns"].loc[0,"total_return"] = .1+.2j
    result = check_fixture(tmp_path,case)
    assert "real_numeric_returns" in result["blockers"]


def test_source_newline_portability_does_not_relax_data_fingerprints(tmp_path):
    case = synthetic_case()
    source = tmp_path/"portfolio_engine.py"
    source.write_bytes(b"# Fixture source\npolicy = 0.5\n")
    declared = _production_text_sha(source)
    original_bytes_hash = _sha(source)
    case["contract"]["production_sha256"] = {"portfolio_engine.py": declared}
    case["contract"]["production_hash_convention"] = "sha256-utf8-universal-newlines-lf-v1"
    assert check_fixture(tmp_path, case)["status"] == "PASS"
    source.write_bytes(b"# Fixture source\r\npolicy = 0.5\r\n")
    assert _production_text_sha(source) == declared
    assert _sha(source) != original_bytes_hash
    assert check_fixture(tmp_path, case)["status"] == "PASS"
    source.write_bytes(b"# Fixture source\r\npolicy = 0.6\r\n")
    result = check_fixture(tmp_path, case)
    assert "production_contract_drift_portfolio_engine.py" in result["blockers"]


def test_malformed_dates_fail_without_inference_warning_or_value_leak(tmp_path):
    case = synthetic_case()
    case["returns"]["date"] = case["returns"].date.astype(object)
    case["returns"].loc[0,"date"] = "PRIVATE_MALFORMED_DATE"
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = check_fixture(tmp_path, case)
    assert result["status"] == "BLOCK"
    assert "validator_execution" in result["blockers"]
    assert not caught
    assert "PRIVATE_MALFORMED_DATE" not in str(result)


@pytest.mark.parametrize("bad_contract", [{}, None, [], False, 0])
def test_explicit_empty_contract_does_not_silently_load_disk_contract(tmp_path, bad_contract):
    case = synthetic_case()
    (tmp_path/"oversight_contract.json").write_text(json.dumps(case["contract"]), encoding="utf-8")
    case["contract"] = bad_contract
    result = check_fixture(tmp_path, case)
    assert result["status"] == "BLOCK"
    assert "contract_valid" in result["blockers"]
    assert "validator_execution" not in result["blockers"]


def test_mixed_supported_rebalance_flag_representations_are_normalized(tmp_path):
    case = synthetic_case()
    case["daily"]["rebalance"] = pd.Series([True, "false", "1", 0], dtype=object)
    result = check_fixture(tmp_path, case)
    assert result["status"] == "PASS", result["blockers"]
    assert case["daily"]["rebalance"].tolist() == [True, "false", "1", 0]


@pytest.mark.parametrize("link_kind", ["file", "private_root", "ancestor"])
def test_private_ledger_cannot_follow_symlinks_into_public_tree(tmp_path, link_kind):
    public = tmp_path/"public"
    public.mkdir()
    exposed = public/"reconstructed_ledger.csv"
    exposed.write_text("PUBLIC_SENTINEL", encoding="utf-8")
    private = tmp_path/"outputs/oversight_private"
    try:
        if link_kind == "file":
            private.mkdir(parents=True)
            (private/"reconstructed_ledger.csv").symlink_to(exposed)
        elif link_kind == "private_root":
            private.parent.mkdir()
            private.symlink_to(public, target_is_directory=True)
        else:
            (tmp_path/"outputs").symlink_to(public, target_is_directory=True)
    except OSError as exc:
        pytest.skip("Host does not permit creating symlinks: "+str(exc.errno))
    result = run_validation(tmp_path, synthetic_case(), private)
    assert "private_output_boundary" in result["blockers"]
    assert exposed.read_text(encoding="utf-8") == "PUBLIC_SENTINEL"
    assert "private_ledger_written" not in result["provenance"]


def test_existing_hard_link_is_replaced_without_overwriting_public_file(tmp_path):
    public = tmp_path/"public.csv"
    public.write_text("PUBLIC_SENTINEL", encoding="utf-8")
    private = tmp_path/"outputs/oversight_private"
    private.mkdir(parents=True)
    destination = private/"reconstructed_ledger.csv"
    os.link(public, destination)
    result = run_validation(tmp_path, synthetic_case(), private)
    assert result["status"] == "PASS", result["blockers"]
    assert public.read_text(encoding="utf-8") == "PUBLIC_SENTINEL"
    assert len(pd.read_csv(destination)) == 4
    assert not list(private.glob(".ledger-*.tmp"))


def test_finite_but_overflowing_returns_fail_without_nonfinite_aggregates(tmp_path):
    case = synthetic_case()
    case["returns"].loc[case["returns"].date.eq("2021-01-04"), "total_return"] = 1e308
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = check_fixture(tmp_path, case)
    assert result["status"] == "BLOCK"
    assert "validator_execution" in result["blockers"]
    assert result["provenance"]["error_type"] in {"FloatingPointError", "ValueError"}
    assert not caught
    json.dumps(result, allow_nan=False)
