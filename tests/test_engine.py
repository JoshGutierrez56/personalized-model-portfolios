"""Checks for economically meaningful failure modes, using no network."""
import unittest
import numpy as np
import pandas as pd

from portfolio_engine import (ClientRules, CURRENT, TARGET, TICKERS, bounds,
    estimate_covariance, example_clients, optimize_portfolio, portfolio_metrics,
    proportional_portfolio, run_study, synthetic_prices, tracking_error, validate_weights)


class PortfolioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        prices, _ = synthetic_prices()
        returns = prices.pct_change(fill_method=None).dropna()
        cls.train = returns.loc[:"2021-12-31"]
        cls.test = returns.loc["2022-01-01":]
        cls.cov = estimate_covariance(cls.train)

    def test_unrestricted_recovers_target(self):
        w = optimize_portfolio(TARGET, self.cov, ClientRules("free"))
        np.testing.assert_allclose(w, TARGET, atol=1e-5)

    def test_all_methods_respect_same_constraints(self):
        result, weights, _ = run_study(self.train, self.test)
        self.assertEqual(len(result), 30)
        for client in example_clients():
            for _, w in weights.loc[client.name].iterrows():
                validate_weights(w, client)

    def test_optimizer_cannot_lose_in_sample_to_feasible_baseline(self):
        for client in example_clients():
            baseline = proportional_portfolio(TARGET, client)
            optimal = optimize_portfolio(TARGET, self.cov, client)
            self.assertLessEqual(tracking_error(optimal, TARGET, self.cov),
                                 tracking_error(baseline, TARGET, self.cov) + 2e-6)

    def test_trade_minimization_respects_explicit_risk_allowance(self):
        for client in example_clients():
            risk = optimize_portfolio(TARGET, self.cov, client)
            budget = tracking_error(risk, TARGET, self.cov) + .0025
            low = optimize_portfolio(TARGET, self.cov, client, CURRENT, budget)
            self.assertLessEqual(tracking_error(low, TARGET, self.cov), budget + 2e-6)
            self.assertLessEqual(abs(low-CURRENT).sum(), abs(risk-CURRENT).sum() + 2e-6)

    def test_infeasible_and_unknown_constraints_fail(self):
        for rule in [ClientRules("bad", floors={"SPY": .8, "IEF": .8}),
                     ClientRules("bad", caps={t: .10 for t in TICKERS}),
                     ClientRules("bad", blocked=("SPY",), floors={"SPY": .1}),
                     ClientRules("bad", blocked=("UNKNOWN",))]:
            with self.assertRaises(ValueError):
                bounds(rule, TICKERS)

    def test_costs_charge_buys_and_sells(self):
        current = TARGET.copy()
        current["SPY"] -= .1
        current["IEF"] += .1
        metrics = portfolio_metrics(TARGET, TARGET, current, self.cov, self.test, 5)
        self.assertAlmostEqual(metrics["gross_traded_pct"], 20)
        self.assertAlmostEqual(metrics["one_way_turnover_pct"], 10)
        self.assertAlmostEqual(metrics["estimated_cost_bps"], 1)

    def test_holdout_cannot_change_fitted_portfolios(self):
        _, first, _ = run_study(self.train, self.test, [example_clients()[1]])
        _, second, _ = run_study(self.train, self.test * 10, [example_clients()[1]])
        np.testing.assert_allclose(first, second, atol=1e-10)

    def test_overlap_and_invalid_covariance_fail(self):
        with self.assertRaises(ValueError):
            run_study(self.train, self.train.tail(20))
        bad = pd.DataFrame(-np.eye(8), index=TICKERS, columns=TICKERS)
        with self.assertRaises(ValueError):
            optimize_portfolio(TARGET, bad, ClientRules("bad"))


if __name__ == "__main__":
    unittest.main()
