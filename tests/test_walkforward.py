"""Economic accounting and time-order invariants, not a second implementation."""
from dataclasses import replace
import unittest
import numpy as np
import pandas as pd

from portfolio_engine import TICKERS, TARGET, ClientRules, synthetic_prices
from walkforward import StudyConfig, funded_rebalance, run_walkforward, decision_schedule


class WalkForwardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        prices, _ = synthetic_prices()
        cls.returns = prices.pct_change(fill_method=None).iloc[1:]
        cls.config = StudyConfig(start="2016-01-01", end="2016-04-29", lookback=252)
        cls.clients = [ClientRules("No gold", blocked=("GLD",))]

    def test_self_financing_costs_and_both_sides(self):
        after, trades, fee = funded_rebalance([60.,40.], [.5,.5], 100.)
        self.assertAlmostEqual(fee, .2)
        self.assertAlmostEqual(after.sum()+fee, 100)
        self.assertAlmostEqual(-trades.sum(), fee)
        np.testing.assert_allclose(after/after.sum(), [.5,.5])

    def test_costs_are_not_external_cash(self):
        after, trades, fee = funded_rebalance([100.,0.], [0.,1.], 100.)
        self.assertAlmostEqual(after.sum(), 100*.99/1.01)
        self.assertAlmostEqual(fee, .01*abs(trades).sum())
        self.assertAlmostEqual(after.sum()+fee, 100)

    def test_no_trade_has_no_cost(self):
        after, trades, fee = funded_rebalance([60.,40.], [.6,.4], 20.)
        np.testing.assert_allclose(after,[60.,40.],atol=1e-10)
        self.assertLess(fee,1e-10)

    def test_execution_return_cannot_change_same_day_decision(self):
        altered=self.returns.copy()
        first=decision_schedule(self.returns,self.config)[0]['execution_date']
        altered.loc[first,'SPY']=.25
        one=run_walkforward(self.returns,self.config,self.clients)
        two=run_walkforward(altered,self.config,self.clients)
        cols=[f'weight_{t}' for t in TICKERS]
        np.testing.assert_allclose(one['decisions'].iloc[:3][cols],two['decisions'].iloc[:3][cols],atol=1e-9)
        self.assertTrue((one['decisions'].signal_date<one['decisions'].execution_date).all())

    def test_future_returns_cannot_change_past_allocations(self):
        altered=self.returns.copy()
        altered.loc['2016-03-01':] *= 3
        one=run_walkforward(self.returns,self.config,self.clients)['decisions']
        two=run_walkforward(altered,self.config,self.clients)['decisions']
        cols=[f'weight_{t}' for t in TICKERS]
        select=one.execution_date<'2016-03-01'
        np.testing.assert_allclose(one.loc[select,cols],two.loc[select,cols],atol=1e-9)

    def test_same_unrestricted_weights_match_frictionless_benchmark_after_initial_transition(self):
        result=run_walkforward(self.returns,replace(self.config,cost_bps=0),[ClientRules('Free')])
        daily=result['daily'].query("method == 'Minimum risk'").iloc[1:]
        np.testing.assert_allclose(daily.gross_active_return,0,atol=1e-8)

    def test_non_rebalance_days_have_drift_without_fictitious_trading(self):
        run=run_walkforward(self.returns,self.config,self.clients)
        daily=run['daily']
        self.assertTrue((daily.loc[~daily.rebalance,'cost_dollars']==0).all())
        self.assertTrue((daily.loc[~daily.rebalance,'gross_traded_fraction']==0).all())
        trades=run['trades']
        for (_,_,_), group in trades.groupby(['client','method','date']):
            self.assertAlmostEqual(group.pretrade_dollars.sum(),group.posttrade_dollars.sum()+group.cost_dollars.sum(),places=6)
        self.assertTrue((trades.query("ticker == 'GLD'").posttrade_dollars.abs()<1e-3).all())

    def test_bad_data_and_insufficient_history_fail_closed(self):
        bad=self.returns.copy(); bad.iloc[4,0]=np.nan
        with self.assertRaises(ValueError): run_walkforward(bad,self.config,self.clients)
        with self.assertRaises(ValueError): decision_schedule(self.returns,replace(self.config,lookback=2000))
        with self.assertRaises(ValueError): funded_rebalance([1.,0.],[1.2,-.2],5)

    def test_zero_allowance_has_no_turnover_discretion(self):
        result=run_walkforward(self.returns,replace(self.config,allowance_bps=0),self.clients)
        rows=result['decisions']
        cols=[f'weight_{t}' for t in TICKERS]
        np.testing.assert_allclose(rows.query("method == 'Minimum risk'")[cols],
                                   rows.query("method == 'Lower turnover'")[cols],atol=1e-10)


if __name__=='__main__': unittest.main()
