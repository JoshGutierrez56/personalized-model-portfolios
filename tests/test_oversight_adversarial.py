"""Hand-calculated challenger cases; no engine/optimizer or licensed inputs.

Two assets, one funded rebalance and two drifting closes make denominator and
multi-period-linking mistakes visible without trusting production-generated data.
"""
import numpy as np
import pandas as pd
import pytest

from oversight_core import run_validation


def hand_case(cost_bps=100.0):
    dates = pd.to_datetime(["2023-12-28", "2023-12-29", "2024-01-02", "2024-01-03", "2024-01-04"])
    market = np.array([[.01, -.01], [-.01, .01], [.10, 0.], [.10, 0.], [-.20, .05]])
    contract = {
        "source_start": str(dates[0].date()), "source_end": str(dates[-1].date()),
        "tickers": ["A", "B"], "target": [.5, .5], "current": [1., 0.],
        "annualization": 252, "methods": ["Minimum risk"],
        "clients": [{"name": "Cap A", "caps": {"A": .5}, "floors": {}, "blocked": []}],
        "config": {"start": "2024-01-02", "end": "2024-01-04", "lookback": 2,
                   "allowance_bps": 25., "cost_bps": cost_bps, "initial_value": 100., "covariance": "sample"},
        "tolerances": {"dollars": 1e-8, "returns": 1e-10, "weights": 2e-6,
                       "risk": 2e-6, "risk_reconciliation": 1e-10},
        "production_sha256": {}, "require_source_provenance": False,
        "limitations": ["Hand-calculated synthetic validation fixture only."],
    }
    # Selling A and buying B has gross notional exactly 110 regardless of fee:
    # |55(1-c)-110| + |55(1-c)| = 110, so funded NAV = 110(1-c).
    fee = 110 * cost_bps / 10000
    first = (110 - fee) / 2
    account = np.array([[100., 0.], [first, first], [first*1.1, first], [first*.88, first*1.05]])
    benchmark = np.array([[50., 50.], [52.5, 52.5], [57.75, 52.5], [46.2, 55.125]])
    rows, bm = [], []
    for j, date in enumerate(dates[2:]):
        previous, nav = account[j].sum(), account[j+1].sum()
        gross = float(account[j] @ market[j+2] / previous)
        net = nav/previous - 1
        b_return = benchmark[j+1].sum()/benchmark[j].sum() - 1
        f = fee if j == 0 else 0.
        rows.append({"date": date, "client": "Cap A", "method": "Minimum risk", "nav": nav,
                     "gross_return": gross, "net_return": net, "benchmark_return": b_return,
                     "gross_active_return": gross-b_return, "net_active_return": net-b_return,
                     "cost_dollars": f, "cost_fraction": f/(previous*(1+gross)),
                     "gross_traded_fraction": 1. if j == 0 else 0., "rebalance": j == 0,
                     "max_weight_limit_drift": max(account[j+1,0]/nav-.5, 0.)})
        bm.append({"date": date, "benchmark_return": b_return, "benchmark_nav": benchmark[j+1].sum()})
    trades = pd.DataFrame([
        {"date": dates[2], "signal_date": dates[1], "client": "Cap A", "method": "Minimum risk",
         "ticker": ticker, "pretrade_dollars": pre, "posttrade_dollars": first,
         "trade_dollars": first-pre, "cost_dollars": abs(first-pre)*cost_bps/10000}
        for ticker, pre in [("A", 110.), ("B", 0.)]])
    decisions = pd.DataFrame([{"client": "Cap A", "method": "Minimum risk", "signal_date": dates[1],
        "execution_date": dates[2], "history_start": dates[0], "history_count": 2, "shrinkage": 0.,
        "estimated_te": 0., "minimum_feasible_te": 0., "te_budget": .0025, "weight_A": .5, "weight_B": .5}])
    returns = pd.DataFrame([{"date": date, "ticker": ticker, "total_return": market[i,j]}
                           for i,date in enumerate(dates) for j,ticker in enumerate(["A", "B"])])
    return {"contract": contract, "calendar": pd.DataFrame({"date": dates}), "returns": returns,
            "decisions": decisions, "trades": trades, "daily": pd.DataFrame(rows), "benchmark": pd.DataFrame(bm)}


def test_high_return_fee_denominator_and_exact_multiperiod_linking(tmp_path):
    case = hand_case()
    private = tmp_path/"outputs/oversight_private/test"
    result = run_validation(tmp_path, overrides=case, output_private=private)
    assert result["status"] == "PASS", result["blockers"]
    # Gross return 10%, fee 1.1 on prior NAV 100 => net 8.9%, not 9%.
    ledger = pd.read_csv(private/"reconstructed_ledger.csv")
    assert ledger.loc[0, "net_return"] == pytest.approx(.089)
    assert ledger.loc[0, "cost_contribution"] == pytest.approx(-.011)
    totals = result["aggregate"]["attribution_totals"][0]
    assert totals["portfolio_total_return"] == pytest.approx(.050885)
    assert totals["benchmark_total_return"] == pytest.approx(.01325)
    assert totals["active_total_return_difference"] == pytest.approx(.037635)
    assert totals["linked_cost_contribution"] == pytest.approx(-.011)
    assert totals["active_linking_residual"] == pytest.approx(0, abs=1e-12)
    assert case["daily"].net_active_return.sum() == pytest.approx(.039)
    assert totals["active_total_return_difference"] != pytest.approx(case["daily"].net_active_return.sum())
    # A cap can drift between rebalances without falsely blocking a valid run.
    assert result["aggregate"]["path_metrics"][0]["interim_drift_days"] == 1


def test_all_input_row_orders_are_irrelevant(tmp_path):
    case = hand_case()
    for key, value in list(case.items()):
        if isinstance(value, pd.DataFrame):
            case[key] = value.sample(frac=1, random_state=7).reset_index(drop=True)
    result = run_validation(tmp_path, overrides=case)
    assert result["status"] == "PASS", result["blockers"]


@pytest.mark.parametrize("fault,expected", [
    ("missing_column", "schema_daily"), ("duplicate_calendar", "unique_keys_calendar"),
    ("nan_return", "finite_returns"), ("malformed_date", "validator_execution"),
    ("future_signal", "decision_chronology"), ("missing_asset", "source_calendar_complete"),
    ("unknown_constraint", "contract_valid"),
])
def test_structural_faults_fail_closed_without_raw_diagnostics(tmp_path, fault, expected):
    case = hand_case()
    if fault == "missing_column": case["daily"] = case["daily"].drop(columns="net_return")
    elif fault == "duplicate_calendar": case["calendar"] = pd.concat([case["calendar"], case["calendar"].iloc[[0]]])
    elif fault == "nan_return": case["returns"].loc[0, "total_return"] = np.nan
    elif fault == "malformed_date": case["returns"]["date"] = "INVALID_PRIVATE_VALUE"
    elif fault == "future_signal": case["decisions"].loc[0,"signal_date"] = pd.Timestamp("2024-01-02")
    elif fault == "missing_asset": case["returns"] = case["returns"].iloc[1:]
    elif fault == "unknown_constraint": case["contract"]["clients"][0]["blocked"] = ["UNKNOWN"]
    result = run_validation(tmp_path, overrides=case)
    assert result["status"] == "BLOCK"
    assert expected in result["blockers"]
    assert "INVALID_PRIVATE_VALUE" not in str(result)


@pytest.mark.parametrize("bad_tolerance", [float("nan"), float("inf"), -1.])
def test_tampered_tolerance_cannot_disable_validation(tmp_path, bad_tolerance):
    case = hand_case()
    case["contract"]["tolerances"]["returns"] = bad_tolerance
    result = run_validation(tmp_path, overrides=case)
    assert result["status"] == "BLOCK"
    assert "contract_valid" in result["blockers"]


def test_internally_consistent_forged_benchmark_is_reconstructed_from_assets(tmp_path):
    case = hand_case()
    # Forge both benchmark and every copied daily benchmark/active field. All
    # daily-vs-benchmark SQL identities still reconcile, but source-ledger truth does not.
    case["benchmark"]["benchmark_return"] += .01
    case["benchmark"]["benchmark_nav"] = 100*np.cumprod(1+case["benchmark"].benchmark_return)
    case["daily"]["benchmark_return"] += .01
    case["daily"]["gross_active_return"] -= .01
    case["daily"]["net_active_return"] -= .01
    result = run_validation(tmp_path, overrides=case)
    checks = {x["id"]: x["status"] for x in result["checks"]}
    assert checks["sql_benchmark_error"] == "PASS"
    assert checks["sql_gross_active_error"] == "PASS"
    assert checks["sql_net_active_error"] == "PASS"
    assert checks["benchmark_nav_reconstruction"] == "BLOCK"
    assert checks["benchmark_return_reconstruction"] == "BLOCK"


def test_source_mismatch_reaches_economic_controls_not_generic_failure(tmp_path):
    case = hand_case()
    case["returns"].loc[(case["returns"].date == "2024-01-03") & case["returns"].ticker.eq("A"), "total_return"] = .20
    result = run_validation(tmp_path, overrides=case)
    assert result["status"] == "BLOCK"
    assert "validator_execution" not in result["blockers"]
    assert {"daily_nav_reconstruction", "daily_gross_reconciliation", "daily_net_reconciliation"}.issubset(result["blockers"])


def test_wrong_fee_denominator_can_look_plausible_but_is_blocked(tmp_path):
    case = hand_case()
    case["daily"].loc[0,"net_return"] = .09
    case["daily"].loc[0,"net_active_return"] = .04
    result = run_validation(tmp_path, overrides=case)
    assert result["status"] == "BLOCK"
    assert "sql_cost_return_error" in result["blockers"]
    assert "daily_net_reconciliation" in result["blockers"]
