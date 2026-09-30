"""Small, inspectable portfolio-construction functions used by the notebook."""

from dataclasses import dataclass, field
from pathlib import Path
import hashlib
import json
from datetime import datetime, timezone

import cvxpy as cp
import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf


TICKERS = ["SPY", "IWM", "EFA", "EEM", "IEF", "TLT", "GLD", "SHY"]
TARGET = pd.Series([.30, .10, .15, .05, .20, .05, .10, .05], index=TICKERS)
# A hypothetical starting account, expressed as fractions of account value.
CURRENT = pd.Series([.40, .15, .10, .05, .10, .05, .10, .05], index=TICKERS)
ANNUALIZATION = 252


@dataclass
class ClientRules:
    name: str
    blocked: tuple = ()
    floors: dict = field(default_factory=dict)
    caps: dict = field(default_factory=dict)
    description: str = ""


def example_clients():
    """These are invented accounts, not client or employer data."""
    return [
        ClientRules("Unrestricted"),
        ClientRules("No gold", blocked=("GLD",)),
        ClientRules("No emerging markets", blocked=("EEM",)),
        ClientRules("No long Treasuries", blocked=("TLT",)),
        ClientRules("10% short Treasuries", floors={"SHY": .10}),
        ClientRules("20% short Treasuries", floors={"SHY": .20}),
        ClientRules("Retain 40% US large cap", floors={"SPY": .40}),
        ClientRules("20% US small-cap floor", floors={"IWM": .20}),
        ClientRules("20% position cap", caps={t: .20 for t in TICKERS}),
        ClientRules("Domestic and liquid", blocked=("EFA", "EEM"), floors={"SHY": .15}),
    ]


def bounds(rules, tickers):
    labels = pd.Index(tickers)
    unknown = (set(rules.blocked) | set(rules.floors) | set(rules.caps)) - set(labels)
    if unknown:
        raise ValueError(f"Unknown assets: {sorted(unknown)}")
    lo = pd.Series(0., index=labels)
    hi = pd.Series(1., index=labels)
    for t, v in rules.floors.items():
        lo[t] = v
    for t, v in rules.caps.items():
        hi[t] = v
    for t in rules.blocked:
        hi[t] = 0.
    if not np.isfinite(lo).all() or not np.isfinite(hi).all():
        raise ValueError("Bounds must be finite")
    if (lo < 0).any() or (hi > 1).any() or (lo > hi).any():
        raise ValueError("Infeasible bounds: require 0 <= floor <= cap <= 1")
    if lo.sum() > 1 + 1e-10 or hi.sum() < 1 - 1e-10:
        raise ValueError("Infeasible bounds: full investment is impossible")
    return lo, hi


def validate_weights(weights, rules, tol=2e-6):
    lo, hi = bounds(rules, weights.index)
    if not np.isfinite(weights).all():
        raise ValueError("Non-finite portfolio weights")
    if abs(weights.sum() - 1) > tol:
        raise ValueError("Weights do not sum to one")
    if (weights < lo - tol).any() or (weights > hi + tol).any():
        raise ValueError("Portfolio violates a client constraint")


def proportional_portfolio(target, rules):
    """Bounded proportional allocation: clip(k * target, floor, cap).

    This baseline uses the same restrictions as the optimizer but no covariance.
    All target weights must be positive so every available asset can receive weight.
    """
    if (target <= 0).any() or not np.isclose(target.sum(), 1):
        raise ValueError("The proportional rule requires a positive normalized target")
    lo, hi = bounds(rules, target.index)
    left, right = 0., max(1., float((hi / target).max()))
    for _ in range(100):
        scale = (left + right) / 2
        weights = (scale * target).clip(lo, hi)
        if weights.sum() < 1:
            left = scale
        else:
            right = scale
    validate_weights(weights, rules)
    return weights


def estimate_covariance(returns):
    if len(returns) < 60 or returns.isna().any().any():
        raise ValueError("Need at least 60 complete observations")
    if not np.isfinite(returns.to_numpy()).all():
        raise ValueError("Returns must be finite")
    covariance = LedoitWolf().fit(returns.to_numpy()).covariance_ * ANNUALIZATION
    return pd.DataFrame(covariance, index=returns.columns, columns=returns.columns)


def tracking_error(weights, target, covariance):
    active = (weights - target).to_numpy()
    matrix = covariance.loc[target.index, target.index].to_numpy()
    variance = float(active @ matrix @ active)
    if variance < -1e-10:
        raise ValueError("Covariance implies negative variance")
    return float(np.sqrt(max(variance, 0.)))


def optimize_portfolio(target, covariance, rules, current=None, te_budget=None):
    """Minimize tracking variance, or minimize trades subject to a TE budget.

    te_budget is annualized tracking error as a decimal, not basis points.
    Transaction costs are reported separately rather than mixed with variance.
    """
    lo, hi = bounds(rules, target.index)
    matrix = covariance.loc[target.index, target.index].to_numpy()
    if not np.isfinite(matrix).all() or not np.allclose(matrix, matrix.T):
        raise ValueError("Covariance must be finite and symmetric")
    if np.linalg.eigvalsh(matrix).min() < -1e-10:
        raise ValueError("Covariance must be positive semidefinite")
    w = cp.Variable(len(target))
    active = w - target.to_numpy()
    variance = cp.quad_form(active, cp.psd_wrap(matrix))
    constraints = [cp.sum(w) == 1, w >= lo.to_numpy(), w <= hi.to_numpy()]
    if te_budget is None:
        objective = cp.Minimize(variance * 1e4)
    else:
        if current is None or te_budget < 0:
            raise ValueError("A nonnegative TE budget and current weights are required")
        current = current.reindex(target.index)
        if current.isna().any() or (current < 0).any() or not np.isclose(current.sum(), 1):
            raise ValueError("Current weights must be long-only and sum to one")
        # An explicit second-order cone avoids squaring a small risk budget.
        values, vectors = np.linalg.eigh(matrix)
        risk_root = np.diag(np.sqrt(np.maximum(values, 0))) @ vectors.T
        constraints.append(cp.norm((100 * risk_root) @ active, 2) <= te_budget * 100)
        objective = cp.Minimize(cp.norm1(w - current.to_numpy()))
    problem = cp.Problem(objective, constraints)
    problem.solve(solver="CLARABEL", tol_gap_abs=1e-8, tol_feas=1e-8, tol_gap_rel=1e-8)
    if problem.status != cp.OPTIMAL or w.value is None:
        raise ValueError(f"No validated optimum: {problem.status}")
    weights = pd.Series(w.value, index=target.index)
    validate_weights(weights, rules)
    if te_budget is not None and tracking_error(weights, target, covariance) > te_budget + 2e-6:
        raise ValueError("Solved portfolio exceeds the tracking-error budget")
    return weights


def portfolio_metrics(weights, target, current, covariance, holdout, cost_bps=5.):
    if not np.isfinite(cost_bps) or cost_bps < 0:
        raise ValueError("Cost assumption must be nonnegative and finite")
    trades = weights - current
    gross_traded = float(trades.abs().sum())
    active_returns = holdout.loc[:, target.index] @ (weights - target)
    return {
        "estimated_te_pct": tracking_error(weights, target, covariance) * 100,
        "holdout_te_pct": float(active_returns.std(ddof=1) * np.sqrt(ANNUALIZATION) * 100),
        "one_way_turnover_pct": gross_traded / 2 * 100,
        "gross_traded_pct": gross_traded * 100,
        "estimated_cost_bps": gross_traded * cost_bps,
        "max_weight_pct": float(weights.max() * 100),
    }


def run_study(training, holdout, clients=None, allowance_bps=25., cost_bps=5.):
    if training.index.max() >= holdout.index.min():
        raise ValueError("Training must strictly precede the holdout")
    if allowance_bps < 0 or not np.isfinite(allowance_bps):
        raise ValueError("Risk allowance must be nonnegative and finite")
    training = training.loc[:, TICKERS]
    holdout = holdout.loc[:, TICKERS]
    if len(holdout) < 2 or holdout.isna().any().any() or not np.isfinite(holdout).all().all():
        raise ValueError("Need a finite, complete holdout with at least two rows")
    covariance = estimate_covariance(training)
    rows, portfolios = [], {}
    for client in clients or example_clients():
        risk_only = optimize_portfolio(TARGET, covariance, client)
        budget = tracking_error(risk_only, TARGET, covariance) + allowance_bps / 10000
        methods = {
            "Proportional": proportional_portfolio(TARGET, client),
            "Minimum risk": risk_only,
            "Lower turnover": optimize_portfolio(TARGET, covariance, client, CURRENT, budget),
        }
        for method, weights in methods.items():
            rows.append({"client": client.name, "method": method,
                         **portfolio_metrics(weights, TARGET, CURRENT, covariance, holdout, cost_bps)})
            portfolios[(client.name, method)] = weights
    results = pd.DataFrame(rows)
    weights = pd.DataFrame(portfolios).T
    weights.index.names = ["client", "method"]
    return results, weights, covariance


def load_market_prices(cache_dir="data", refresh=False):
    """Download adjusted daily closes. Fail explicitly; never substitute synthetic data."""
    import yfinance as yf
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / "adjusted_close_2014_2025.csv"
    metadata_path = cache_dir / "market_metadata.json"
    if path.exists() and metadata_path.exists() and not refresh:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if hashlib.sha256(path.read_bytes()).hexdigest() != metadata["sha256"]:
            raise ValueError("Cached market data hash changed; refresh explicitly")
        prices = pd.read_csv(path, index_col=0, parse_dates=True)
    else:
        raw = yf.download(TICKERS, start="2014-01-01", end="2026-01-01",
                          auto_adjust=True, progress=False, threads=False)
        if raw.empty:
            raise RuntimeError("Market download failed. Retry or explicitly select synthetic mode.")
        prices = raw["Close"].reindex(columns=TICKERS)
        prices.index = pd.to_datetime(prices.index).tz_localize(None)
        prices.to_csv(path)
        metadata = {"source": "Yahoo Finance via yfinance", "auto_adjust": True,
                    "requested_start": "2014-01-01", "requested_end_exclusive": "2026-01-01",
                    "downloaded_utc": datetime.now(timezone.utc).isoformat(),
                    "yfinance_version": yf.__version__, "tickers": TICKERS,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    prices = prices.reindex(columns=TICKERS)
    if prices.index.duplicated().any() or not prices.index.is_monotonic_increasing:
        raise ValueError("Price dates must be unique and sorted")
    if prices.isna().any().any() or not np.isfinite(prices).all().all() or (prices <= 0).any().any():
        raise ValueError("Missing or invalid prices; inspect the source instead of filling gaps")
    if len(prices) < 2500 or prices.index.max() < pd.Timestamp("2025-12-30"):
        raise ValueError("Incomplete download for the specified study period")
    return prices, metadata


def synthetic_prices(seed=42):
    """Deterministic plumbing fixture, not evidence of market performance."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2014-01-02", "2025-12-31")
    factors = rng.normal(size=(len(dates), 3)) * np.array([.009, .004, .007])
    loadings = np.array([[1, -.1, 0], [1.15, -.1, 0], [.9, 0, 0], [1.05, 0, .1],
                         [0, 1, 0], [0, 1.8, 0], [.05, .1, 1], [0, .1, 0]])
    noise = rng.normal(size=(len(dates), 8)) * .002
    log_returns = .0001 + factors @ loadings.T + noise
    prices = pd.DataFrame(100 * np.exp(log_returns.cumsum(axis=0)), index=dates, columns=TICKERS)
    return prices, {"source": "SYNTHETIC - not historical market returns", "seed": seed}
