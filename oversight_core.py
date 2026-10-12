"""Independent portfolio arithmetic challenger; never imports production modules.

run_validation returns public aggregate checks only. Optional detailed reconstructions
are written solely to the explicitly supplied private output directory. Overrides are
in-memory copies of source tables, used for labeled fault-injection demonstrations.
They never change the original files. This is a retrospective research control, not
an independent market-data feed or a production trading approval system.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from itertools import product
from typing import Any

import duckdb
import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf


INPUT_FILES = {
    "returns": "data/wrds/daily.csv", "calendar": "data/wrds/calendar.csv",
    "daily": "outputs/wrds_private/daily.csv",
    "decisions": "outputs/wrds_private/decisions.csv",
    "trades": "outputs/wrds_private/trades.csv",
    "benchmark": "outputs/wrds_private/benchmark.csv",
}
SCHEMA = {
    "returns": ["date", "ticker", "total_return"],
    "calendar": ["date"],
    "daily": ["date", "client", "method", "nav", "gross_return", "net_return",
              "benchmark_return", "gross_active_return", "net_active_return",
              "cost_dollars", "rebalance", "max_weight_limit_drift"],
    "decisions": ["client", "method", "signal_date", "execution_date", "history_start",
                  "history_count", "shrinkage", "estimated_te", "minimum_feasible_te", "te_budget"],
    "trades": ["date", "signal_date", "client", "method", "ticker", "pretrade_dollars",
               "posttrade_dollars", "trade_dollars", "cost_dollars"],
    "benchmark": ["date", "benchmark_return", "benchmark_nav"],
}
DATE_FIELDS = {k: [v for v in cols if v in {"date", "signal_date", "execution_date", "history_start"}]
               for k, cols in SCHEMA.items()}
KEYS = {"returns": ["date", "ticker"], "calendar": ["date"],
        "daily": ["date", "client", "method"],
        "decisions": ["execution_date", "client", "method"],
        "trades": ["date", "client", "method", "ticker"], "benchmark": ["date"]}
NUMERIC = {
    "returns": ["total_return"], "calendar": [],
    "daily": ["nav", "gross_return", "net_return", "benchmark_return", "gross_active_return",
              "net_active_return", "cost_dollars", "max_weight_limit_drift"],
    "decisions": ["history_count", "shrinkage", "estimated_te", "minimum_feasible_te", "te_budget"],
    "trades": ["pretrade_dollars", "posttrade_dollars", "trade_dollars", "cost_dollars"],
    "benchmark": ["benchmark_return", "benchmark_nav"],
}


class _Checks:
    def __init__(self):
        self.records: dict[str, dict] = {}

    def condition(self, key, valid, count=1, detail=""):
        self.error(key, 0.0 if valid else 1.0, 0.0, count, detail)

    def error(self, key, error, tolerance, count=1, detail=""):
        value = float(np.max(np.abs(error))) if np.size(error) else 0.0
        finite = bool(np.isfinite(value))
        record = self.records.setdefault(key, {
            "id": key, "status": "PASS", "count": 0, "max_abs_error": 0.0,
            "tolerance": float(tolerance), "detail": detail,
        })
        record["count"] += int(count)
        if finite and record["max_abs_error"] is not None:
            record["max_abs_error"] = max(record["max_abs_error"], value)
        else:
            record["max_abs_error"] = None
        if not finite or value > tolerance:
            record["status"] = "BLOCK"

    @property
    def blocked(self):
        return any(r["status"] == "BLOCK" for r in self.records.values())


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _production_text_sha(path):
    """Fingerprint Python source independent of Git's Windows/Linux line endings.

    Only production-source drift uses this convention. Market data, saved research
    artifacts and all other byte-level provenance remain exact, unnormalized hashes.
    """
    text = Path(path).read_bytes().decode("utf-8")
    canonical = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _frame_hash(frame):
    # Fingerprints override bytes without exposing any rows in public results.
    return hashlib.sha256(frame.to_csv(index=False).encode("utf-8")).hexdigest()


def _bounds(client, tickers):
    lo, hi = np.zeros(len(tickers)), np.ones(len(tickers))
    for i, ticker in enumerate(tickers):
        lo[i] = client.get("floors", {}).get(ticker, 0.0)
        hi[i] = client.get("caps", {}).get(ticker, 1.0)
        if ticker in client.get("blocked", []):
            hi[i] = 0.0
    return lo, hi


def _contract_valid(contract):
    tickers, cfg = contract["tickers"], contract["config"]
    target, current = np.asarray(contract["target"], float), np.asarray(contract["current"], float)
    vals = np.array([cfg["initial_value"], cfg["cost_bps"], cfg["allowance_bps"], contract["annualization"]])
    valid = (len(tickers) >= 2 and len(set(tickers)) == len(tickers)
             and len(target) == len(tickers) and len(current) == len(tickers)
             and np.isfinite(target).all() and np.isfinite(current).all()
             and (target >= 0).all() and (current >= 0).all()
             and abs(target.sum()-1) < 1e-12 and abs(current.sum()-1) < 1e-12
             and np.isfinite(vals).all() and cfg["initial_value"] > 0
             and 0 <= cfg["cost_bps"] < 10000 and cfg["allowance_bps"] >= 0
             and contract["annualization"] > 0
             and isinstance(cfg["lookback"], int) and cfg["lookback"] >= 2
             and cfg["covariance"] in {"ledoit_wolf", "sample"}
             and len(set(contract["methods"])) == len(contract["methods"])
             and "Minimum risk" in contract["methods"]
             and len({c["name"] for c in contract["clients"]}) == len(contract["clients"])
             and len(contract["clients"]) > 0
             and pd.Timestamp(contract["source_start"]) <= pd.Timestamp(cfg["start"])
             <= pd.Timestamp(cfg["end"]) <= pd.Timestamp(contract["source_end"]))
    for client in contract["clients"]:
        declared = set(client.get("blocked", [])) | set(client.get("floors", {})) | set(client.get("caps", {}))
        lo, hi = _bounds(client, tickers)
        valid = valid and not (declared-set(tickers)) and np.isfinite(lo).all() and np.isfinite(hi).all()
        valid = valid and (lo >= 0).all() and (hi <= 1).all() and (lo <= hi).all() and lo.sum() <= 1 and hi.sum() >= 1
    # A NaN/inf threshold must never turn comparisons into an accidental PASS.
    ceilings = {"dollars": 0.0001, "returns": 1e-10, "weights": 2e-6,
                "risk": 2e-6, "risk_reconciliation": 1e-10}
    for name, ceiling in ceilings.items():
        value = contract["tolerances"].get(name)
        valid = valid and isinstance(value, (int, float)) and not isinstance(value, bool)
        valid = valid and np.isfinite(value) and 0 <= value <= ceiling
    if contract.get("require_source_provenance", True):
        valid = valid and set(contract.get("production_sha256", {})) == {"portfolio_engine.py", "walkforward.py", "wrds_data.py"}
        valid = valid and contract.get("production_hash_convention") == "sha256-utf8-universal-newlines-lf-v1"
    return bool(valid)


def _prepare(tables, contract, checks):
    """Fail closed before pivoting/joining: no filling, deduplication or dropped rows."""
    tickers = contract["tickers"]
    for name, table in tables.items():
        needed = SCHEMA[name] + (["weight_"+t for t in tickers] if name == "decisions" else [])
        checks.condition("schema_"+name, not (set(needed)-set(table.columns)), detail="Required columns present.")
        if set(needed)-set(table.columns):
            continue
        checks.condition("nonnull_keys_"+name, not table[KEYS[name]].isna().any().any(), len(table))
        checks.condition("unique_keys_"+name, not table.duplicated(KEYS[name]).any(), len(table))
        for field in DATE_FIELDS[name]:
            table[field] = pd.to_datetime(table[field], format="ISO8601", errors="raise")
            checks.condition("valid_dates_"+name, table[field].notna().all()
                             and table[field].eq(table[field].dt.normalize()).all()
                             and table[field].dt.tz is None, len(table))
        numeric = NUMERIC[name] + (["weight_"+t for t in tickers] if name == "decisions" else [])
        if numeric:
            values = table[numeric].apply(pd.to_numeric, errors="raise")
            checks.condition("real_numeric_"+name, not np.iscomplexobj(values.to_numpy()), values.size)
            if np.iscomplexobj(values.to_numpy()):
                continue
            checks.condition("finite_"+name, np.isfinite(values.to_numpy(dtype=float)).all(), values.size)
            table[numeric] = values
    if checks.blocked:
        return None
    returns, calendar = tables["returns"], pd.DatetimeIndex(tables["calendar"]["date"].sort_values())
    checks.condition("calendar_boundary", len(calendar) > 0 and calendar[0] == pd.Timestamp(contract["source_start"])
                     and calendar[-1] == pd.Timestamp(contract["source_end"]), len(calendar))
    checks.condition("source_ticker_roster", set(returns.ticker) == set(tickers), len(returns))
    expected = pd.MultiIndex.from_product([calendar, tickers], names=["date", "ticker"])
    actual = pd.MultiIndex.from_frame(returns[["date", "ticker"]])
    checks.condition("source_calendar_complete", len(actual) == len(expected) and not len(expected.difference(actual))
                     and not len(actual.difference(expected)), len(expected))
    checks.condition("source_return_domain", returns.total_return.gt(-1).all(), len(returns),
                     "Total losses require a separately declared liquidation policy; never filled or dropped.")
    if "permno" in returns:
        checks.condition("source_identity_stable", returns.permno.notna().all()
                         and returns.groupby("ticker").permno.nunique().eq(1).all()
                         and returns.groupby("permno").ticker.nunique().eq(1).all(), len(returns))
    for name, allowed in {"dlyretmissflg": {"NA"}, "dlyretdurflg": {"D1", "D2", "D3", "D4", "DU"},
                          "dlydelflg": {"N"}, "tradingstatusflg": {"A"}}.items():
        if name in returns:
            checks.condition("source_flag_"+name, returns[name].isin(allowed).all(), len(returns))
    cfg = contract["config"]
    evaluation = calendar[(calendar >= pd.Timestamp(cfg["start"])) & (calendar <= pd.Timestamp(cfg["end"]))]
    checks.condition("nonempty_evaluation", len(evaluation) > 0)
    if not len(evaluation):
        return None
    execution = pd.DatetimeIndex(pd.Series(evaluation).groupby(evaluation.to_period("M")).first().values)
    clients, methods = [c["name"] for c in contract["clients"]], contract["methods"]
    for name, dates, columns, levels in [
        ("daily", evaluation, ["date", "client", "method"], [evaluation, clients, methods]),
        ("decisions", execution, ["execution_date", "client", "method"], [execution, clients, methods]),
        ("trades", execution, ["date", "client", "method", "ticker"], [execution, clients, methods, tickers]),
        ("benchmark", evaluation, ["date"], [evaluation]),
    ]:
        want = pd.MultiIndex.from_product(levels, names=columns)
        have = pd.MultiIndex.from_frame(tables[name][columns])
        checks.condition("complete_roster_"+name, len(have) == len(want)
                         and not len(want.difference(have)) and not len(have.difference(want)), len(want))
    checks.condition("positive_saved_nav", tables["daily"].nav.gt(0).all()
                     and tables["benchmark"].benchmark_nav.gt(0).all(), len(tables["daily"]))
    checks.condition("nonnegative_saved_fees", tables["trades"].cost_dollars.ge(0).all()
                     and tables["daily"].cost_dollars.ge(0).all(), len(tables["trades"]))
    checks.condition("rebalance_flag_domain", tables["daily"].rebalance.isin(
        [True, False, 0, 1, "True", "False", "true", "false", "1", "0"]).all(), len(tables["daily"]))
    if checks.blocked:
        return None
    panel = returns.pivot(index="date", columns="ticker", values="total_return").reindex(index=calendar, columns=tickers)
    return panel, evaluation, execution


def _risk_controls(tables, panel, executions, contract, checks):
    cfg, target = contract["config"], np.array(contract["target"])
    tol, bounds = contract["tolerances"], {c["name"]: _bounds(c, contract["tickers"]) for c in contract["clients"]}
    decisions = tables["decisions"]
    cols = ["weight_"+t for t in contract["tickers"]]
    for date in executions:
        loc = panel.index.get_loc(date)
        checks.condition("risk_history_sufficient", loc >= cfg["lookback"])
        if loc < cfg["lookback"]:
            continue
        history = panel.iloc[loc-cfg["lookback"]:loc]
        if cfg["covariance"] == "ledoit_wolf":
            fit = LedoitWolf().fit(history.to_numpy())
            covariance, shrinkage = fit.covariance_, fit.shrinkage_
        else:
            covariance, shrinkage = np.cov(history.to_numpy(), rowvar=False, ddof=1), 0.0
        covariance = covariance * contract["annualization"]
        checks.condition("risk_covariance_psd", np.isfinite(covariance).all()
                         and np.linalg.eigvalsh(covariance).min() >= -1e-12)
        group = decisions.loc[decisions.execution_date.eq(date)]
        checks.condition("decision_chronology", group.signal_date.lt(group.execution_date).all(), len(group))
        checks.condition("decision_risk_window", group.signal_date.eq(history.index[-1]).all()
                         and group.history_start.eq(history.index[0]).all()
                         and group.history_count.eq(cfg["lookback"]).all(), len(group),
                         "Exactly the declared trailing observations, ending strictly before execution.")
        checks.error("risk_shrinkage_reconciliation", group.shrinkage.to_numpy()-shrinkage, tol["risk_reconciliation"], len(group))
        calculated = {}
        for row in group.itertuples(index=False):
            weights = np.array([getattr(row, c) for c in cols])
            lo, hi = bounds[row.client]
            checks.error("decision_full_investment", weights.sum()-1, tol["weights"])
            checks.error("decision_constraint_bounds", max(0, float((lo-weights).max()), float((weights-hi).max())), tol["weights"])
            variance = float((weights-target) @ covariance @ (weights-target))
            te = np.sqrt(max(variance, 0))
            calculated[(row.client, row.method)] = te
            checks.error("risk_te_reconciliation", te-row.estimated_te, tol["risk_reconciliation"])
            if row.method == "Lower turnover":
                checks.error("risk_te_budget", max(0, te-row.te_budget), tol["risk"])
        for row in group.itertuples(index=False):
            reference = calculated[(row.client, "Minimum risk")]
            checks.error("risk_minimum_reference", row.minimum_feasible_te-reference, tol["risk_reconciliation"],
                         detail="Reconciles the saved Minimum risk solution; does not independently certify optimizer optimality.")
            checks.error("risk_budget_definition", row.te_budget-reference-cfg["allowance_bps"]/10000,
                         tol["risk_reconciliation"])
    trade_times = tables["trades"].merge(decisions[["execution_date", "client", "method", "signal_date"]],
        left_on=["date", "client", "method"], right_on=["execution_date", "client", "method"],
        validate="many_to_one", suffixes=("_trade", "_decision"))
    checks.condition("trade_chronology", trade_times.signal_date_trade.lt(trade_times.date).all()
                     and trade_times.signal_date_trade.eq(trade_times.signal_date_decision).all(), len(trade_times))


def _sql_controls(root, tables, contract, checks):
    with duckdb.connect(":memory:") as connection:
        connection.execute("SET threads=1")
        for name in ["trades", "daily", "decisions", "benchmark"]:
            connection.register(name, tables[name])
        for filename, parameter, unit in [
            ("oversight_trade_controls.sql", contract["config"]["cost_bps"]/10000, "dollars"),
            ("oversight_daily_controls.sql", contract["config"]["initial_value"], "returns"),
        ]:
            # SQL is versioned challenger source, not a query generated from engine code.
            path = root / "sql" / filename
            if not path.exists():
                path = Path(__file__).parent / "sql" / filename
            result = connection.execute(path.read_text(encoding="utf-8"), [parameter]).df().iloc[0]
            for column in result.index:
                if column == "row_count":
                    continue
                tolerance = 0 if column.endswith("count") else contract["tolerances"][unit]
                checks.error("sql_"+column, result[column], tolerance, int(result.row_count))


def _reconstruct(tables, panel, evaluation, executions, contract, checks, retain_detail):
    tickers, cfg = contract["tickers"], contract["config"]
    target, current = np.array(contract["target"]), np.array(contract["current"])
    capital, rate, tol = cfg["initial_value"], cfg["cost_bps"]/10000, contract["tolerances"]
    returns = panel.loc[evaluation].to_numpy()
    scheduled = set(executions)
    benchmark = tables["benchmark"].set_index("date").loc[evaluation]
    b_holdings, b_previous = target*capital, capital
    b_contributions, b_dollars, b_nav, b_returns = [], [], [], []
    for date, observed in zip(evaluation, returns):
        gain = b_holdings*observed
        b_contributions.append(gain/b_previous)
        b_dollars.append(gain)
        b_holdings = b_holdings+gain
        nav = float(b_holdings.sum())
        b_nav.append(nav)
        b_returns.append(gain.sum()/b_previous)
        if date in scheduled:
            b_holdings = target*nav
        b_previous = nav
    b_contributions, b_dollars = np.asarray(b_contributions), np.asarray(b_dollars)
    b_nav, b_returns = np.array(b_nav), np.array(b_returns)
    checks.error("benchmark_nav_reconstruction", b_nav-benchmark.benchmark_nav.to_numpy(), tol["dollars"], len(evaluation))
    checks.error("benchmark_return_reconstruction", b_returns-benchmark.benchmark_return.to_numpy(), tol["returns"], len(evaluation))
    details, totals, path_metrics = [], [], []
    for client, method in product(contract["clients"], contract["methods"]):
        name = client["name"]
        daily = tables["daily"].loc[tables["daily"].client.eq(name) & tables["daily"].method.eq(method)].set_index("date").loc[evaluation]
        trades = tables["trades"].loc[tables["trades"].client.eq(name) & tables["trades"].method.eq(method)]
        trade_map = {date: group.set_index("ticker").loc[tickers] for date, group in trades.groupby("date")}
        decisions = tables["decisions"].loc[tables["decisions"].client.eq(name) & tables["decisions"].method.eq(method)].set_index("execution_date")
        lo, hi = _bounds(client, tickers)
        held, previous = current*capital, capital
        asset_pnl, cost_total = np.zeros(len(tickers)), 0.0
        nav_series, net_series, gross_series, drift_series = [], [], [], []
        flags = daily.rebalance
        if flags.dtype == object:
            valid_flags = flags.isin(["True", "False", "true", "false", "1", "0"])
            checks.condition("rebalance_flag_domain", valid_flags.all(), len(flags))
            flags = flags.astype(str).str.lower().isin(["true", "1"])
        checks.condition("rebalance_schedule", np.array_equal(flags.to_numpy(dtype=bool), evaluation.isin(executions)), len(evaluation))
        for idx, (date, observed) in enumerate(zip(evaluation, returns)):
            prior = held.copy()
            gain = prior*observed
            before = prior+gain
            asset_contribution = gain/previous
            fee = 0.0
            traded_fraction = 0.0
            if date in scheduled:
                trade = trade_map[date]
                change = trade.trade_dollars.to_numpy()
                costs = np.abs(change)*rate
                fee = float(costs.sum())
                held = before+change
                checks.error("trade_preholdings_reconstruction", before-trade.pretrade_dollars.to_numpy(), tol["dollars"], len(tickers))
                checks.error("trade_postholdings_reconstruction", held-trade.posttrade_dollars.to_numpy(), tol["dollars"], len(tickers))
                checks.error("trade_cost_formula", costs-trade.cost_dollars.to_numpy(), tol["dollars"], len(tickers))
                checks.error("trade_self_financing", change.sum()+fee, tol["dollars"])
                proposed = decisions.loc[date, ["weight_"+t for t in tickers]].to_numpy(dtype=float)
                executed = held/held.sum()
                checks.error("posttrade_decision_weights", executed-proposed, tol["weights"], len(tickers))
                checks.error("posttrade_constraints", max(0, float((lo-executed).max()), float((executed-hi).max())), tol["weights"])
                traded_fraction = np.abs(change).sum()/before.sum()
            else:
                held = before
            nav = float(held.sum())
            gross = float(gain.sum()/previous)
            net = nav/previous-1
            cost_contribution = -fee/previous
            drift = max(0, float((lo-held/nav).max()), float((held/nav-hi).max()))
            checks.condition("reconstructed_positive_nav", nav > 0 and (held >= -tol["dollars"]).all())
            checks.error("daily_asset_gross_identity", asset_contribution.sum()-gross, tol["returns"])
            checks.error("daily_net_contribution_identity", asset_contribution.sum()+cost_contribution-net, tol["returns"])
            active_contribution = asset_contribution-b_contributions[idx]
            checks.error("daily_active_contribution_identity", active_contribution.sum()+cost_contribution-(net-b_returns[idx]), tol["returns"])
            # Saved reported metrics compared as arrays below; fee and drift independently derived here.
            asset_pnl += gain
            cost_total += fee
            nav_series.append(nav); net_series.append(net); gross_series.append(gross); drift_series.append(drift)
            if retain_detail:
                details.append({"date": str(date.date()), "client": name, "method": method,
                    "prior_nav": previous, "reconstructed_nav": nav, "gross_return": gross,
                    "net_return": net, "benchmark_return": b_returns[idx],
                    "cost_contribution": cost_contribution, "cost_dollars": fee,
                    "rebalance": date in scheduled, "max_weight_limit_drift": drift,
                    **{"prior_holding_"+t: float(v) for t,v in zip(tickers,prior)},
                    **{"post_holding_"+t: float(v) for t,v in zip(tickers,held)},
                    **{"asset_contribution_"+t: float(v) for t,v in zip(tickers,asset_contribution)},
                    **{"active_contribution_"+t: float(v) for t,v in zip(tickers,active_contribution)}})
            checks.error("daily_fee_reconstruction", fee-float(daily.cost_dollars.iloc[idx]), tol["dollars"])
            if "cost_fraction" in daily:
                checks.error("daily_cost_fraction", fee/before.sum()-float(daily.cost_fraction.iloc[idx]), tol["returns"])
            if "gross_traded_fraction" in daily:
                checks.error("daily_traded_fraction", traded_fraction-float(daily.gross_traded_fraction.iloc[idx]), tol["returns"])
            previous = nav
        navs, nets, gross_returns = np.array(nav_series), np.array(net_series), np.array(gross_series)
        checks.error("daily_nav_reconstruction", navs-daily.nav.to_numpy(), tol["dollars"], len(evaluation))
        for label, calculated, column in [
            ("gross", gross_returns, "gross_return"), ("net", nets, "net_return"),
            ("benchmark", b_returns, "benchmark_return"),
            ("gross_active", gross_returns-b_returns, "gross_active_return"),
            ("net_active", nets-b_returns, "net_active_return"),
            ("drift", np.array(drift_series), "max_weight_limit_drift"),
        ]:
            checks.error("daily_"+label+"_reconciliation", calculated-daily[column].to_numpy(),
                         tol["weights"] if label == "drift" else tol["returns"], len(evaluation))
        linked_asset = asset_pnl/capital
        linked_benchmark = b_dollars.sum(axis=0)/capital
        linked_cost = -cost_total/capital
        portfolio_return, benchmark_return = navs[-1]/capital-1, b_nav[-1]/capital-1
        active_return = portfolio_return-benchmark_return
        linked_active = linked_asset-linked_benchmark
        checks.error("multiperiod_portfolio_linking", linked_asset.sum()+linked_cost-portfolio_return, tol["returns"])
        checks.error("multiperiod_benchmark_linking", linked_benchmark.sum()-benchmark_return, tol["returns"])
        residual = linked_active.sum()+linked_cost-active_return
        checks.error("multiperiod_active_linking", residual, tol["returns"])
        totals.append({"client": name, "method": method,
            "portfolio_total_return": float(portfolio_return), "benchmark_total_return": float(benchmark_return),
            "active_total_return_difference": float(active_return),
            "linked_asset_pnl": {t:float(v) for t,v in zip(tickers,linked_asset)},
            "linked_benchmark_pnl": {t:float(v) for t,v in zip(tickers,linked_benchmark)},
            "linked_active_asset_pnl": {t:float(v) for t,v in zip(tickers,linked_active)},
            "linked_cost_contribution": float(linked_cost), "active_linking_residual": float(residual)})
        path_metrics.append({"client": name, "method": method,
            "terminal_nav": float(navs[-1]), "total_cost_dollars": float(cost_total),
            "gross_tracking_error": float(np.std(gross_returns-b_returns,ddof=1)*np.sqrt(contract["annualization"])) if len(navs)>1 else 0.0,
            "net_tracking_error": float(np.std(nets-b_returns,ddof=1)*np.sqrt(contract["annualization"])) if len(navs)>1 else 0.0,
            "interim_drift_days": int(np.sum((np.array(drift_series)>tol["weights"]) & ~evaluation.isin(executions))),
            "maximum_interim_bound_drift": float(max(drift_series))})
    return {"attribution_totals": totals, "path_metrics": path_metrics,
            "linking_method": "Initial-capital-scaled realized dollar P&L; sum asset gains/V0 plus negative costs/V0 equals cumulative portfolio return. Subtract analogous benchmark contributions for exact cumulative wealth-return difference. Not Brinson, factor attribution, or a separate cost-free portfolio."}, details


def run_validation(root: Path, overrides: dict | None = None, output_private: Path | None = None) -> dict:
    """Validate immutable saved artifacts; no acquisition, optimizer or engine calls.

    Overrides keys: returns, calendar, daily, decisions, trades, benchmark (DataFrames)
    and contract (dict). Full declared coverage is mandatory; subset tables BLOCK.
    Detailed ledger is absent from the JSON result. output_private must resolve
    beneath root/outputs/oversight_private; any other destination BLOCKS. It writes
    reconstructed_ledger.csv there, even when an economic reconciliation BLOCKS,
    to support incident diagnosis. Structural failures stop before reconstruction.
    """
    root, overrides = Path(root), dict(overrides or {})
    checks, aggregate, provenance = _Checks(), {}, {"source_sha256": {}, "override_sha256": {}, "engine_imported": False}
    contract: dict[str, Any] = {}

    def result():
        records = list(checks.records.values())
        return {"schema_version": "1.0", "status": "BLOCK" if checks.blocked else "PASS",
                "checks": records, "blockers": [r["id"] for r in records if r["status"] == "BLOCK"],
                "aggregate": aggregate, "provenance": provenance,
                "limitations": contract.get("limitations", [])}

    try:
        checks.condition("override_keys", not (set(overrides)-set(INPUT_FILES)-{"contract"}))
        if checks.blocked:
            return result()
        contract = overrides.get("contract") or json.loads((root/"oversight_contract.json").read_text(encoding="utf-8"))
        provenance["contract_sha256"] = hashlib.sha256(json.dumps(contract,sort_keys=True).encode()).hexdigest()
        checks.condition("contract_valid", _contract_valid(contract))
        if checks.blocked:
            return result()
        if output_private is not None:
            approved_private = (root/"outputs/oversight_private").resolve()
            proposed_private = Path(output_private).resolve()
            checks.condition("private_output_boundary", proposed_private == approved_private
                             or approved_private in proposed_private.parents,
                             detail="Detailed reconstructed holdings and returns may only be written under outputs/oversight_private.")
            if checks.blocked:
                return result()
        for name, digest in contract.get("production_sha256", {}).items():
            checks.condition("production_contract_drift_"+name,
                             (root/name).exists() and _production_text_sha(root/name)==digest,
                             detail="UTF-8 source fingerprint with CRLF/CR normalized to LF; substantive source changes still block.")
        summary_path = root/"outputs/wrds/run_summary.json"
        require_provenance = contract.get("require_source_provenance", True)
        if require_provenance:
            checks.condition("required_run_provenance", summary_path.exists())
        if summary_path.exists():
            summary = json.loads(summary_path.read_text())
            checks.condition("executed_configuration_drift", summary["config"] == contract["config"]
                             and summary["methods"] == contract["methods"])
        manifest = root/"data/wrds/manifest.json"
        if require_provenance:
            checks.condition("required_source_provenance", manifest.exists())
        if manifest.exists():
            source = json.loads(manifest.read_text())
            if require_provenance:
                checks.condition("source_manifest_schema", set(source.get("files", {})) == {"daily.csv", "identities.csv", "calendar.csv"}
                                 and source.get("return_field") == "dlyret"
                                 and source.get("returns_table") == "crsp.dsf_v2"
                                 and source.get("requested_start") == contract["source_start"]
                                 and source.get("requested_end") == contract["source_end"])
            for name, digest in source.get("files", {}).items():
                file = root/"data/wrds"/name
                checks.condition("cached_source_hash_"+name, file.exists() and _sha(file)==digest)
        if checks.blocked:
            return result()
        tables = {}
        for name, relative in INPUT_FILES.items():
            path = root/relative
            if path.exists():
                provenance["source_sha256"][name] = _sha(path)
            if name in overrides:
                tables[name] = overrides[name].copy(deep=True)
                provenance["override_sha256"][name] = _frame_hash(tables[name])
            else:
                # CRSP literal NA flag is not a pandas missing-value marker here.
                tables[name] = pd.read_csv(path, keep_default_na=False)
        prepared = _prepare(tables, contract, checks)
        aggregate.update({name+"_rows":len(frame) for name,frame in tables.items()})
        if prepared is None or checks.blocked:
            return result()
        panel, evaluation, execution = prepared
        aggregate.update({"paths":len(contract["clients"])*len(contract["methods"]),
                          "evaluation_dates":len(evaluation), "execution_dates":len(execution),
                          "source_dates":len(panel), "assets":len(contract["tickers"])})
        _risk_controls(tables, panel, execution, contract, checks)
        _sql_controls(root, tables, contract, checks)
        calculated, detail = _reconstruct(tables, panel, evaluation, execution, contract, checks, output_private is not None)
        aggregate.update(calculated)
        if output_private is not None:
            destination = Path(output_private)
            destination.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(detail).to_csv(destination/"reconstructed_ledger.csv", index=False)
            provenance["private_ledger_written"] = True
            provenance["private_ledger_rows"] = len(detail)
    except Exception as exc:
        # Fail closed without including raw input values or filesystem secrets in public diagnostics.
        checks.condition("validator_execution", False, detail="Validation stopped: "+type(exc).__name__+". No release; inspect the local source/contract.")
        provenance["error_type"] = type(exc).__name__
    return result()
