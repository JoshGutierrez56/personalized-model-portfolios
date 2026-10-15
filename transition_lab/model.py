"""Bounded convex transition policy; not a comprehensive tax optimizer."""
from __future__ import annotations

import hashlib
import json
from datetime import date

import cvxpy as cp
import numpy as np


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def finite_number(value, name, minimum=0., maximum=None):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not np.isfinite(value):
        raise ValueError(f'{name} must be a finite number')
    if value<minimum or (maximum is not None and value>maximum):
        raise ValueError(f'{name} outside permitted range')


def validate_snapshot(snapshot):
    if snapshot.get('evidence_type')!='hypothetical':
        raise ValueError('This lab accepts explicitly hypothetical snapshots only')
    decision=date.fromisoformat(snapshot['as_of'])
    if date.fromisoformat(snapshot['price_as_of'])!=decision:
        raise ValueError('Price timestamp must equal the decision date')
    if date.fromisoformat(snapshot['risk_as_of'])>=decision:
        raise ValueError('Risk estimate must strictly precede the decision date')
    symbols=snapshot['symbols']
    if not symbols or len(set(symbols))!=len(symbols) or set(snapshot['prices'])!=set(symbols):
        raise ValueError('Price and symbol labels must be unique and match')
    for symbol,price in snapshot['prices'].items():finite_number(price,f'price:{symbol}',1e-12)
    covariance=np.asarray(snapshot['annual_covariance'],float)
    if covariance.shape!=(len(symbols),len(symbols)) or not np.isfinite(covariance).all():
        raise ValueError('Covariance shape or values invalid')
    if not np.allclose(covariance,covariance.T,rtol=0,atol=1e-12) or np.linalg.eigvalsh(covariance).min() < -1e-12:
        raise ValueError('Covariance must be symmetric positive semidefinite')
    accounts=snapshot['accounts']
    if not accounts or len({a['account_id'] for a in accounts})!=len(accounts):
        raise ValueError('Account IDs must be unique')
    for account in accounts:
        for key in ('cash','cash_floor','tax_budget'):
            finite_number(account[key],key)
        if set(account['target'])!=set(symbols):raise ValueError('Target labels differ')
        for symbol,weight in account['target'].items():finite_number(weight,f'target:{symbol}',0,1)
        if sum(account['target'].values())>1+1e-12:raise ValueError('Target asset weights exceed one')
        if not set(account.get('blocked',[])).issubset(symbols):raise ValueError('Unknown blocked asset')
        for symbol,cap in account.get('caps',{}).items():
            if symbol not in symbols:raise ValueError('Unknown capped asset')
            finite_number(cap,f'cap:{symbol}',0,1)
        lots=account['lots']
        if not lots or len({lot['lot_id'] for lot in lots})!=len(lots):raise ValueError('Lot IDs must be unique within each account')
        for lot in lots:
            if lot['symbol'] not in symbols:raise ValueError('Unknown lot asset')
            finite_number(lot['shares'],'lot shares')
            finite_number(lot['basis_per_share'],'lot basis')
            finite_number(lot['tax_rate'],'lot tax rate',0,1)
            if date.fromisoformat(lot['acquired'])>decision:raise ValueError('Future acquisition date')
        nav=account['cash']+sum(l['shares']*snapshot['prices'][l['symbol']] for l in lots)
        if nav<=0:raise ValueError('Positive investable NAV required')


def optimize(snapshot, cost_bps=5., cost_aversion=.05):
    validate_snapshot(snapshot)
    finite_number(cost_bps,'cost_bps',0,1000)
    finite_number(cost_aversion,'cost_aversion')
    symbols=snapshot['symbols'];prices=np.array([snapshot['prices'][s] for s in symbols])
    covariance=np.asarray(snapshot['annual_covariance'],float)
    policy={'cost_bps':float(cost_bps),'cost_aversion':float(cost_aversion),
            'direction':'sell initially overweight or blocked; buy initially underweight',
            'tax':'positive-gain reserve; no loss credit or netting',
            'objective':'initial-NAV tracking variance + cost_aversion * (fee + tax reserve) / initial NAV'}
    plans=[]
    for account in snapshot['accounts']:
        lots=account['lots'];mapping=np.zeros((len(symbols),len(lots)))
        for j,lot in enumerate(lots):mapping[symbols.index(lot['symbol']),j]=1
        lot_prices=np.array([snapshot['prices'][l['symbol']] for l in lots])
        lot_values=np.array([l['shares'] for l in lots])*lot_prices
        current=mapping@lot_values;nav=float(current.sum()+account['cash'])
        target=np.array([account['target'][s] for s in symbols]);initial=current/nav
        sell=cp.Variable(len(lots),nonneg=True);buy=cp.Variable(len(symbols),nonneg=True)
        ending=initial-mapping@sell+buy
        reserve_coeff=np.array([max(0,1-l['basis_per_share']/p)*l['tax_rate'] for l,p in zip(lots,lot_prices)])
        fee=cost_bps/10000*(cp.sum(sell)+cp.sum(buy));reserve=reserve_coeff@sell
        cash=account['cash']/nav+cp.sum(sell)-cp.sum(buy)-fee-reserve
        constraints=[sell<=lot_values/nav,cash>=account['cash_floor']/nav,reserve<=account['tax_budget']/nav,1-fee-reserve>=1e-6]
        for i,symbol in enumerate(symbols):
            blocked=symbol in account.get('blocked',[])
            if blocked:constraints.extend([ending[i]==0,buy[i]==0])
            elif initial[i]>=target[i]-1e-12:constraints.append(buy[i]==0)
            for j,lot in enumerate(lots):
                if lot['symbol']==symbol and not blocked and initial[i]<=target[i]+1e-12:constraints.append(sell[j]==0)
            if symbol in account.get('caps',{}):constraints.append(ending[i]<=account['caps'][symbol]*(1-fee-reserve))
        objective=cp.quad_form(ending-target,cp.psd_wrap(covariance))+cost_aversion*(fee+reserve)
        problem=cp.Problem(cp.Minimize(objective),constraints)
        problem.solve(solver='CLARABEL',tol_gap_abs=1e-11,tol_feas=1e-11,tol_gap_rel=1e-11,max_iter=300)
        if problem.status!=cp.OPTIMAL:raise ValueError(f"Infeasible or unverified transition for {account['account_id']}: {problem.status}")
        sale_values=np.clip(np.asarray(sell.value)*nav,0,lot_values)
        buy_values=np.maximum(np.asarray(buy.value)*nav,0)
        sale_values[sale_values<1e-6]=0;buy_values[buy_values<1e-6]=0
        trades=[]
        for j,amount in enumerate(sale_values):
            if amount:trades.append({'side':'sell','symbol':lots[j]['symbol'],'lot_id':lots[j]['lot_id'],'shares':float(amount/lot_prices[j])})
        for i,amount in enumerate(buy_values):
            if amount:trades.append({'side':'buy','symbol':symbols[i],'lot_id':None,'shares':float(amount/prices[i])})
        ending_values=current-mapping@sale_values+buy_values
        modeled_fee=float((sale_values.sum()+buy_values.sum())*cost_bps/10000)
        tax=float(reserve_coeff@sale_values)
        ending_cash=float(account['cash']+sale_values.sum()-buy_values.sum()-modeled_fee-tax)
        ending_nav=float(ending_values.sum()+ending_cash)
        active_before=current/nav-target;active_after=ending_values/ending_nav-target
        plans.append({'account_id':account['account_id'],'status':problem.status,'trades':trades,
            'initial_nav':nav,'ending_cash':ending_cash,'ending_nav':ending_nav,'modeled_fee':modeled_fee,'tax_reserve':tax,
            'ending_values':dict(zip(symbols,map(float,ending_values))),
            'ending_weights':dict(zip(symbols,map(float,ending_values/ending_nav))),
            'tracking_risk_before':float(np.sqrt(max(0,active_before@covariance@active_before))),
            'tracking_risk_after':float(np.sqrt(max(0,active_after@covariance@active_after))),
            'objective_value':float(problem.value)})
    plan={'schema_version':1,'evidence_type':'hypothetical','snapshot_sha256':fingerprint(snapshot),
          'as_of':snapshot['as_of'],'policy':policy,'accounts':plans}
    plan['plan_id']=fingerprint(plan)
    return plan
