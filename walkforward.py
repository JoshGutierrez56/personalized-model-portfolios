"""Lagged monthly decisions, drifting total-return sleeves and self-financed costs."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf

from portfolio_engine import (ANNUALIZATION, CURRENT, TARGET, TICKERS, ClientRules,
    bounds, example_clients, optimize_portfolio, proportional_portfolio, tracking_error,
    validate_weights)

METHODS = ("Proportional", "Minimum risk", "Lower turnover")


@dataclass(frozen=True)
class StudyConfig:
    start: str = "2014-01-01"
    end: str = "2025-12-31"
    lookback: int = 756
    allowance_bps: float = 25.
    cost_bps: float = 5.
    initial_value: float = 1_000_000.
    covariance: str = "ledoit_wolf"

    def validate(self):
        if self.lookback < 60 or self.covariance not in {"ledoit_wolf", "sample"}:
            raise ValueError("Invalid covariance specification.")
        vals = [self.allowance_bps, self.cost_bps, self.initial_value]
        if not np.isfinite(vals).all() or min(vals) < 0 or self.initial_value <= 0 or self.cost_bps >= 10000:
            raise ValueError("Invalid risk allowance, cost rate or initial wealth.")
        if pd.Timestamp(self.start) > pd.Timestamp(self.end):
            raise ValueError("Study start must precede its end.")


def funded_rebalance(holdings, target, cost_bps):
    """Solve A + c*sum(abs(A*w - h)) = sum(h), charging both buys and sells.

    No external cash injection. Weights are fractions of *post-cost* wealth.
    Holdings are total-return sleeve dollars, not a tax-lot/share ledger.
    """
    h, w = np.asarray(holdings, float), np.asarray(target, float)
    if h.shape != w.shape or h.ndim != 1 or not np.isfinite(h).all() or not np.isfinite(w).all():
        raise ValueError("Invalid holdings/weight vectors.")
    if (h < 0).any() or (w < -2e-6).any() or not np.isclose(w.sum(), 1, atol=2e-6):
        raise ValueError("Require long-only normalized weights and nonnegative holdings.")
    if not np.isfinite(cost_bps) or not 0 <= cost_bps < 10000 or h.sum() <= 0:
        raise ValueError("Invalid cost rate or portfolio value.")
    w = np.maximum(w, 0)
    w /= w.sum()
    nav, rate = h.sum(), cost_bps / 10000
    left, right = 0., nav
    for _ in range(70):
        mid = (left + right) / 2
        if mid + rate * np.abs(mid * w - h).sum() > nav:
            right = mid
        else:
            left = mid
    after = ((left + right) / 2) * w
    trades = after - h
    fee = float(rate * np.abs(trades).sum())
    if abs(after.sum() + fee - nav) > max(1e-7, nav * 1e-11):
        raise ArithmeticError("Self-financing accounting identity failed.")
    return after, trades, fee


def _validate_returns(returns):
    if list(returns.columns) != TICKERS:
        raise ValueError("Returns must contain the exact, ordered model universe.")
    if not isinstance(returns.index, pd.DatetimeIndex) or returns.index.has_duplicates or not returns.index.is_monotonic_increasing:
        raise ValueError("Returns require a unique ordered DatetimeIndex.")
    if not np.isfinite(returns.to_numpy()).all() or (returns <= -1).any().any():
        raise ValueError("Missing, non-finite or total-loss returns require explicit handling.")


def decision_schedule(returns, config):
    """Trade at the first available close each month; signal is the prior close."""
    _validate_returns(returns)
    config.validate()
    out = returns.loc[config.start:config.end]
    if out.empty:
        raise ValueError("No evaluation observations.")
    first = out.groupby(out.index.to_period("M")).head(1).index
    rows = []
    for execution in first:
        pos = returns.index.get_loc(execution)
        if pos < config.lookback:
            raise ValueError("Not enough history for the first lagged risk estimate.")
        history = returns.iloc[pos-config.lookback:pos]
        values = history.to_numpy()
        if config.covariance == "ledoit_wolf":
            estimator = LedoitWolf().fit(values)
            cov, shrinkage = estimator.covariance_, float(estimator.shrinkage_)
        else:
            cov, shrinkage = np.cov(values, rowvar=False, ddof=1), 0.
        cov = pd.DataFrame(cov * ANNUALIZATION, index=TICKERS, columns=TICKERS)
        rows.append({"execution_date": execution, "signal_date": history.index[-1],
                     "history_start": history.index[0], "history_count": len(history),
                     "shrinkage": shrinkage, "covariance": cov})
    return rows


def run_walkforward(returns, config=None, clients=None, dollar_volume=None):
    config = config or StudyConfig()
    clients = example_clients() if clients is None else clients
    if not clients or len({c.name for c in clients}) != len(clients):
        raise ValueError("Need distinct client scenarios.")
    schedule = decision_schedule(returns, config)
    lookup = {row["execution_date"]: row for row in schedule}
    out = returns.loc[config.start:config.end]
    keys = [(client.name, method) for client in clients for method in METHODS]
    rules = {c.name: c for c in clients}
    limits = {c.name: tuple(v.to_numpy() for v in bounds(c, TICKERS)) for c in clients}
    holdings = {key: CURRENT.to_numpy() * config.initial_value for key in keys}
    wealth_prev = {key: config.initial_value for key in keys}
    benchmark = TARGET.to_numpy() * config.initial_value
    benchmark_prev = config.initial_value
    daily, decisions, trades, benchmark_rows = [], [], [], []
    for date, market in out.iterrows():
        scheduled = lookup.get(date)
        proposals = {}
        if scheduled:
            cov = scheduled["covariance"]
            # These holdings end at signal_date; today's returns have NOT been applied.
            for client in clients:
                minimum = optimize_portfolio(TARGET, cov, client)
                min_te = tracking_error(minimum, TARGET, cov)
                for method in METHODS:
                    key = (client.name, method)
                    current = pd.Series(holdings[key] / holdings[key].sum(), index=TICKERS)
                    if method == "Proportional":
                        proposed = proportional_portfolio(TARGET, client)
                    elif method == "Minimum risk":
                        proposed = minimum
                    elif config.allowance_bps == 0 and np.linalg.eigvalsh(cov).min() > 1e-12:
                        # Positive-definite risk has a unique minimum: a zero
                        # allowance leaves no alternative turnover solution.
                        proposed = minimum.copy()
                    else:
                        proposed = optimize_portfolio(TARGET, cov, client, current,
                            min_te + config.allowance_bps / 10000)
                    validate_weights(proposed, client)
                    proposals[key] = proposed
                    decisions.append({"client": client.name, "method": method,
                        "signal_date": scheduled["signal_date"], "execution_date": date,
                        "history_start": scheduled["history_start"],
                        "history_count": scheduled["history_count"], "shrinkage": scheduled["shrinkage"],
                        "estimated_te": tracking_error(proposed, TARGET, cov),
                        "minimum_feasible_te": min_te,
                        "te_budget": min_te + config.allowance_bps / 10000,
                        "solver_status": proposed.attrs.get("solver_status", "not_required"),
                        "solver_tolerance": proposed.attrs.get("solver_tolerance", 0.),
                        "solver_retry_count": proposed.attrs.get("solver_retry_count", 0),
                        **{f"weight_{t}": float(proposed[t]) for t in TICKERS}})
        # Hold the previous allocation for the entire close-to-close return interval.
        benchmark *= 1 + market.to_numpy()
        benchmark_nav = float(benchmark.sum())
        benchmark_return = benchmark_nav / benchmark_prev - 1
        if scheduled:
            benchmark = benchmark_nav * TARGET.to_numpy()  # frictionless policy benchmark
        benchmark_rows.append({"date": date, "benchmark_return": benchmark_return,
                               "benchmark_nav": benchmark_nav})
        benchmark_prev = benchmark_nav
        for key in keys:
            before = holdings[key] * (1 + market.to_numpy())
            nav_pre = float(before.sum())
            gross_return = nav_pre / wealth_prev[key] - 1
            fee, gross_traded = 0., 0.
            if scheduled:
                after, change, fee = funded_rebalance(before, proposals[key].to_numpy(), config.cost_bps)
                validate_weights(pd.Series(after / after.sum(), index=TICKERS), rules[key[0]])
                gross_traded = float(np.abs(change).sum())
                adv = (dollar_volume.loc[:scheduled["signal_date"]].tail(20).mean()
                       if dollar_volume is not None else None)
                for j, ticker in enumerate(TICKERS):
                    denominator = float(adv[ticker]) if adv is not None else np.nan
                    trades.append({"date": date, "signal_date": scheduled["signal_date"],
                        "client": key[0], "method": key[1], "ticker": ticker,
                        "pretrade_dollars": float(before[j]), "posttrade_dollars": float(after[j]),
                        "trade_dollars": float(change[j]), "cost_dollars": abs(float(change[j])) * config.cost_bps / 10000,
                        "lagged_adv20_dollars": denominator,
                        "participation": abs(float(change[j])) / denominator if denominator > 0 else np.nan})
            else:
                after = before
            nav_post = float(after.sum())
            net_return = nav_post / wealth_prev[key] - 1
            drifted = after / nav_post
            # Limits are enforced at rebalance, not continuously between closes.
            lo, hi = limits[key[0]]
            violation = max(float((lo-drifted).max()), float((drifted-hi).max()), 0.)
            daily.append({"date": date, "client": key[0], "method": key[1],
                "nav": nav_post, "gross_return": gross_return, "net_return": net_return,
                "benchmark_return": benchmark_return,
                "gross_active_return": gross_return - benchmark_return,
                "net_active_return": net_return - benchmark_return,
                "cost_dollars": fee, "cost_fraction": fee / nav_pre,
                "gross_traded_fraction": gross_traded / nav_pre,
                "rebalance": bool(scheduled), "max_weight_limit_drift": violation})
            holdings[key], wealth_prev[key] = after, nav_post
    return {"daily": pd.DataFrame(daily), "decisions": pd.DataFrame(decisions),
            "trades": pd.DataFrame(trades), "benchmark": pd.DataFrame(benchmark_rows)}


def summarize_run(run, config):
    records = []
    for (client, method), frame in run["daily"].groupby(["client", "method"], sort=False):
        years = len(frame) / ANNUALIZATION
        nav = np.r_[config.initial_value, frame.nav.to_numpy()]
        records.append({"client": client, "method": method, "days": len(frame),
            "net_cagr_pct": ((nav[-1]/nav[0])**(1/years)-1)*100,
            "net_volatility_pct": frame.net_return.std(ddof=1)*np.sqrt(ANNUALIZATION)*100,
            "max_drawdown_pct": (nav/np.maximum.accumulate(nav)-1).min()*100,
            "gross_te_pct": frame.gross_active_return.std(ddof=1)*np.sqrt(ANNUALIZATION)*100,
            "net_te_pct": frame.net_active_return.std(ddof=1)*np.sqrt(ANNUALIZATION)*100,
            "annual_one_way_turnover_pct": frame.gross_traded_fraction.sum()/2/years*100,
            "annual_incurred_cost_bps": frame.cost_fraction.sum()/years*10000,
            "total_cost_dollars": frame.cost_dollars.sum(), "terminal_nav": nav[-1],
            "rebalance_count": int(frame.rebalance.sum()),
            "days_weight_limits_drifted": int((frame.max_weight_limit_drift > 2e-6).sum()),
            "max_weight_limit_drift_pp": frame.max_weight_limit_drift.max()*100})
    return pd.DataFrame(records)


def period_summary(run):
    daily = run["daily"].copy()
    daily["year"] = daily.date.dt.year
    records = []
    for (client, method, year), frame in daily.groupby(["client", "method", "year"]):
        records.append({"client": client, "method": method, "year": int(year),
            "net_return_pct": (np.prod(1+frame.net_return)-1)*100,
            "gross_te_pct": frame.gross_active_return.std(ddof=1)*np.sqrt(ANNUALIZATION)*100,
            "net_te_pct": frame.net_active_return.std(ddof=1)*np.sqrt(ANNUALIZATION)*100,
            "one_way_turnover_pct": frame.gross_traded_fraction.sum()/2*100,
            "incurred_cost_bps": frame.cost_fraction.sum()*10000})
    return pd.DataFrame(records)


def paired_block_bootstrap(run, repetitions=1000, block=21, seed=20260930):
    """Descriptive paired circular-block intervals; no optimal-strategy selection.

    Shared date blocks preserve contemporaneous pairing; they approximate serial
    dependence, not uncertainty over alternate economic histories or model choice.
    """
    rng = np.random.default_rng(seed)
    daily = run["daily"]
    results = []
    n = daily.date.nunique()
    if n < block * 2:
        raise ValueError("Too few dates for block resampling.")
    starts = rng.integers(0, n, size=(repetitions, int(np.ceil(n/block))))
    indices = ((starts[:, :, None] + np.arange(block)) % n).reshape(repetitions, -1)[:, :n]
    for client, group in daily.groupby("client"):
        table = group.pivot(index="date", columns="method", values="gross_active_return")
        low, minimum = table["Lower turnover"].to_numpy(), table["Minimum risk"].to_numpy()
        differences = (low[indices].std(axis=1, ddof=1)-minimum[indices].std(axis=1, ddof=1))*np.sqrt(ANNUALIZATION)*100
        results.append({"client": client,
            "gross_te_difference_pp": (low.std(ddof=1)-minimum.std(ddof=1))*np.sqrt(ANNUALIZATION)*100,
            "lower_95_pp": float(np.quantile(differences, .025)),
            "upper_95_pp": float(np.quantile(differences, .975)),
            "block_days": block, "repetitions": repetitions})
    return pd.DataFrame(results)
