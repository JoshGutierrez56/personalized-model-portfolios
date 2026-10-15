"""Independent plan accounting: no optimizer/accounting-helper imports."""
import hashlib
import json
from datetime import date

import numpy as np


class ControlViolation(ValueError):
    pass


def validate_plan(snapshot,plan,expected_cost_bps=5.,expected_cost_aversion=.05):
    checks=[]
    def require(condition,code):
        if not condition:raise ControlViolation(code)
        checks.append(code)
    def digest(value):
        return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    def number(value):
        return not isinstance(value,bool) and isinstance(value,(int,float)) and np.isfinite(value)
    try:
        require(snapshot['evidence_type']==plan['evidence_type']=='hypothetical','explicit_hypothetical_scope')
        require(plan['snapshot_sha256']==digest(snapshot),'source_snapshot_fingerprint')
        unsigned={k:v for k,v in plan.items() if k!='plan_id'}
        require(plan['plan_id']==digest(unsigned),'plan_payload_fingerprint')
        require(snapshot['as_of']==snapshot['price_as_of']==plan['as_of'],'contemporaneous_quotes')
        require(date.fromisoformat(snapshot['risk_as_of'])<date.fromisoformat(snapshot['as_of']),'strictly_prior_risk')
        require(plan['policy']['cost_bps']==expected_cost_bps and plan['policy']['cost_aversion']==expected_cost_aversion,'independent_fee_and_objective_policy')
        require(number(expected_cost_bps) and 0<=expected_cost_bps<=1000,'valid_authorized_fee_rate')
        require(number(expected_cost_aversion) and expected_cost_aversion>=0,'valid_authorized_cost_aversion')
        symbols=snapshot['symbols'];prices=snapshot['prices']
        require(len(set(symbols))==len(symbols) and set(prices)==set(symbols),'unique_price_labels')
        require(all(number(v) and v>0 for v in prices.values()),'positive_finite_quotes')
        cov=np.asarray(snapshot['annual_covariance'],float)
        require(cov.shape==(len(symbols),len(symbols)) and np.isfinite(cov).all(),'risk_dimensions_and_values')
        require(np.allclose(cov,cov.T,atol=1e-12,rtol=0) and np.linalg.eigvalsh(cov).min()>=-1e-12,'risk_symmetric_psd')
        sources={a['account_id']:a for a in snapshot['accounts']};candidates={a['account_id']:a for a in plan['accounts']}
        require(len(sources)==len(snapshot['accounts'])==len(candidates)==len(plan['accounts']) and set(sources)==set(candidates),'one_plan_per_account')
        for key,account in sources.items():
            candidate=candidates[key];prefix=key+':'
            lots={l['lot_id']:l for l in account['lots']}
            require(len(lots)==len(account['lots']),prefix+'unique_source_lots')
            require(set(account['target'])==set(symbols),prefix+'target_labels')
            require(all(number(w) and 0<=w<=1 for w in account['target'].values()) and sum(account['target'].values())<=1+1e-12,prefix+'target_budget')
            require(all(number(account[k]) and account[k]>=0 for k in ('cash','cash_floor','tax_budget')),prefix+'nonnegative_cash_policy')
            require(set(account.get('blocked',[])).issubset(symbols),prefix+'known_restrictions')
            require(all(s in symbols and number(v) and 0<=v<=1 for s,v in account.get('caps',{}).items()),prefix+'valid_caps')
            for lot in lots.values():
                require(lot['symbol'] in symbols and all(number(lot[k]) and lot[k]>=0 for k in ('shares','basis_per_share','tax_rate')) and lot['tax_rate']<=1,prefix+'valid_lot:'+lot['lot_id'])
                require(date.fromisoformat(lot['acquired'])<=date.fromisoformat(snapshot['as_of']),prefix+'acquisition_chronology:'+lot['lot_id'])
            quantities={s:sum(l['shares'] for l in lots.values() if l['symbol']==s) for s in symbols}
            initial_values={s:quantities[s]*prices[s] for s in symbols}
            nav=account['cash']+sum(initial_values.values());require(nav>0,prefix+'positive_nav')
            tolerance=max(.005,nav*1e-9)
            cash=float(account['cash']);notional=0.;tax=0.;seen=set();sold={}
            for trade in candidate['trades']:
                symbol=trade['symbol'];quantity=trade['shares'];side=trade['side']
                require(symbol in symbols and number(quantity) and quantity>0 and side in ('buy','sell'),prefix+'valid_trade')
                identity=(side,symbol,trade['lot_id']);require(identity not in seen,prefix+'no_duplicate_trade');seen.add(identity)
                amount=quantity*prices[symbol];notional+=amount
                if side=='sell':
                    require(trade['lot_id'] in lots,prefix+'sale_lot_exists')
                    lot=lots[trade['lot_id']]
                    require(lot['symbol']==symbol,prefix+'sale_lot_symbol')
                    sold[trade['lot_id']]=sold.get(trade['lot_id'],0)+quantity
                    require(sold[trade['lot_id']]<=lot['shares']+tolerance/prices[symbol],prefix+'no_oversell')
                    require(symbol in account.get('blocked',[]) or initial_values[symbol]/nav>account['target'][symbol]+1e-12,prefix+'authorized_sale_direction')
                    quantities[symbol]-=quantity;cash+=amount
                    tax+=max(0,prices[symbol]-lot['basis_per_share'])*quantity*lot['tax_rate']
                else:
                    require(trade['lot_id'] is None,prefix+'new_purchase_not_existing_lot')
                    require(symbol not in account.get('blocked',[]) and initial_values[symbol]/nav<account['target'][symbol]-1e-12,prefix+'authorized_purchase_direction')
                    quantities[symbol]+=quantity;cash-=amount
            fee=notional*expected_cost_bps/10000;cash-=fee+tax
            ending_values={s:quantities[s]*prices[s] for s in symbols};ending_nav=cash+sum(ending_values.values())
            require(ending_nav>0,prefix+'solvent_ending_nav')
            require(all(v>=-tolerance for v in ending_values.values()),prefix+'no_short_positions')
            require(cash>=account['cash_floor']-tolerance,prefix+'independent_account_cash_floor')
            require(tax<=account['tax_budget']+tolerance,prefix+'positive_gain_tax_budget')
            require(abs(ending_nav-(nav-fee-tax))<=tolerance,prefix+'self_financing_identity')
            for s in account.get('blocked',[]):require(abs(ending_values[s])<=tolerance,prefix+'prohibited_position:'+s)
            for s,cap in account.get('caps',{}).items():require(ending_values[s]<=cap*ending_nav+tolerance,prefix+'post_cost_cap:'+s)
            expected={'initial_nav':nav,'ending_cash':cash,'ending_nav':ending_nav,'modeled_fee':fee,'tax_reserve':tax}
            for field,value in expected.items():require(number(candidate[field]) and abs(candidate[field]-value)<=tolerance,prefix+'reported_'+field)
            require(set(candidate['ending_values'])==set(symbols) and set(candidate['ending_weights'])==set(symbols),prefix+'ending_labels')
            for s in symbols:
                require(number(candidate['ending_values'][s]) and abs(candidate['ending_values'][s]-ending_values[s])<=tolerance,prefix+'ending_value:'+s)
                require(number(candidate['ending_weights'][s]) and abs(candidate['ending_weights'][s]-ending_values[s]/ending_nav)<=1e-8,prefix+'ending_weight:'+s)
            target=np.array([account['target'][s] for s in symbols])
            before=np.array([initial_values[s]/nav for s in symbols])-target
            after=np.array([ending_values[s]/ending_nav for s in symbols])-target
            for label,active in [('before',before),('after',after)]:
                risk=float(np.sqrt(max(0,active@cov@active)))
                require(number(candidate['tracking_risk_'+label]) and abs(candidate['tracking_risk_'+label]-risk)<=1e-8,prefix+'risk_'+label)
            objective_active=np.array([ending_values[s]/nav for s in symbols])-target
            objective=objective_active@cov@objective_active+expected_cost_aversion*(fee+tax)/nav
            require(abs(candidate['objective_value']-objective)<=1e-8,prefix+'reported_objective')
        return {'passed':True,'controls_passed':len(checks),'controls':checks,
                'scope':'Independent accounting and feasibility; not independent certification of solver optimality or tax treatment.'}
    except ControlViolation:
        raise
    except (KeyError,TypeError,ValueError,IndexError,OverflowError) as exc:
        raise ControlViolation(f'malformed_or_nonfinite_input:{type(exc).__name__}') from exc
