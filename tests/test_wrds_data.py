"""Fail-closed data controls using fixtures, never presented as market evidence."""
import unittest
import numpy as np
import pandas as pd
from portfolio_engine import TICKERS
from wrds_data import validate_identity,validate_panel


class WRDSDataTests(unittest.TestCase):
    def setUp(self):
        self.names=pd.DataFrame({'ticker':TICKERS,'permno':range(8)})
        self.calendar=pd.DataFrame({'date':pd.bdate_range('2020-01-01',periods=252)})
        self.rows=pd.MultiIndex.from_product([self.calendar.date,range(8)],names=['date','permno']).to_frame(index=False)
        self.rows['total_return']=.001
        self.rows['dlyretmissflg']='NA';self.rows['dlyretdurflg']='D1'
        self.rows['dlydelflg']='N';self.rows['tradingstatusflg']='A'

    def test_complete_daily_return_panel_is_not_price_differenced(self):
        _,returns=validate_panel(self.rows,self.names,self.calendar)
        self.assertEqual(returns.shape,(252,8))
        self.assertEqual(returns.iloc[0,0],.001)

    def test_missing_row_and_duplicate_row_fail(self):
        for rows in [self.rows.iloc[1:],pd.concat([self.rows,self.rows.iloc[:1]])]:
            with self.assertRaises(ValueError):validate_panel(rows,self.names,self.calendar)

    def test_ambiguous_identity_fails(self):
        with self.assertRaises(ValueError):validate_identity(pd.concat([self.names,self.names.iloc[:1]]))

    def test_bad_returns_and_ciz_flags_fail(self):
        for col,value in [('total_return',np.nan),('total_return',-1),('dlyretmissflg','MP'),('dlyretdurflg','P1'),('dlydelflg','Y')]:
            rows=self.rows.copy();rows.loc[0,col]=value
            with self.assertRaises(ValueError):validate_panel(rows,self.names,self.calendar)

    def test_long_weekend_is_not_multi_trading_day_return(self):
        rows=self.rows.copy();rows.loc[0,'dlyretdurflg']='DU'
        _,returns=validate_panel(rows,self.names,self.calendar)
        self.assertEqual(len(returns),252)


if __name__=='__main__':unittest.main()
