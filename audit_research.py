"""Independent arithmetic checks of saved detailed research artifacts."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

from portfolio_engine import TICKERS, example_clients, validate_weights
from run_research import code_hashes
from wrds_data import load_wrds

root=Path(__file__).resolve().parent
out=root/'outputs/wrds'
private=root/'outputs/wrds_private'
receipt=json.loads((out/'run_summary.json').read_text())
_,_,source=load_wrds()
quality=json.loads((out/'data_quality.json').read_text())
assert receipt['code_sha256']==code_hashes(), 'Source code differs from executed run'
assert quality['local_source_file_sha256']==source['files']
daily=pd.read_csv(private/'daily.csv',parse_dates=['date'])
decisions=pd.read_csv(private/'decisions.csv',parse_dates=['signal_date','execution_date'])
trades=pd.read_csv(private/'trades.csv',parse_dates=['date','signal_date'])
assert len(decisions)==4320 and decisions.execution_date.nunique()==144
assert (decisions.signal_date<decisions.execution_date).all()
assert decisions.history_count.eq(receipt['config']['lookback']).all()
rules={c.name:c for c in example_clients()}
for row in decisions.itertuples():
    weights=pd.Series({ticker:getattr(row,f'weight_{ticker}') for ticker in TICKERS})
    validate_weights(weights,rules[row.client])
    if row.method=='Lower turnover':
        assert row.estimated_te<=row.te_budget+2e-6
max_funding_error=0.
max_path_error=0.
for (client,method),group in daily.groupby(['client','method']):
    group=group.sort_values('date')
    prev=np.r_[receipt['config']['initial_value'],group.nav.to_numpy()[:-1]]
    np.testing.assert_allclose(group.net_return,group.nav/prev-1,atol=2e-12)
    np.testing.assert_allclose(group.gross_return-group.net_return,group.cost_dollars/prev,atol=2e-12)
    path=receipt['config']['initial_value']*np.cumprod(1+group.net_return)
    max_path_error=max(max_path_error,float(abs(path-group.nav).max()))
    np.testing.assert_allclose(path,group.nav,rtol=1e-10)
assert (daily.loc[~daily.rebalance,'cost_dollars']==0).all()
daily_lookup=daily.set_index(['date','client','method'],verify_integrity=True)
for (date,client,method),group in trades.groupby(['date','client','method']):
    error=abs(group.pretrade_dollars.sum()-group.posttrade_dollars.sum()-group.cost_dollars.sum())
    max_funding_error=max(max_funding_error,float(error))
    assert error<1e-6
    assert abs(group.trade_dollars.sum()+group.cost_dollars.sum())<1e-6
    np.testing.assert_allclose(group.cost_dollars,abs(group.trade_dollars)*receipt['config']['cost_bps']/10000,atol=1e-9)
    match=daily_lookup.loc[(date,client,method)]
    assert abs(float(match.cost_dollars)-group.cost_dollars.sum())<1e-7
sens=pd.read_csv(out/'sensitivity_summary.csv')
assert len(receipt['sensitivity_specifications'])==8
assert sens.specification.nunique()==9 and len(sens)==81
assert np.isfinite(sens[['gross_te_pct','annual_one_way_turnover_pct','annual_incurred_cost_bps']]).all().all()
check={'status':'PASS','checked_allocation_decisions':len(decisions),
       'checked_portfolio_paths':daily.groupby(['client','method']).ngroups,
       'checked_rebalances':trades.groupby(['date','client','method']).ngroups,
       'sensitivity_summary_rows':len(sens),
       'max_self_financing_error_dollars':max_funding_error,
       'max_compounded_path_error_dollars':max_path_error,
       'checks':['WRDS source hashes','executed code hashes','strict chronology',
                 'post-trade constraint feasibility','ex-ante TE budgets',
                 'NAV and return reconciliation','self-financing buys/sells/costs',
                 'no non-rebalance trading costs','all sensitivity specifications complete']}
(out/'AUDIT.json').write_text(json.dumps(check,indent=2),encoding='utf-8')
print(json.dumps(check,indent=2))
