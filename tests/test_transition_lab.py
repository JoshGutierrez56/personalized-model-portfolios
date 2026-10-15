import copy
import json
from pathlib import Path

import numpy as np
import pytest

from transition_lab.challenger import ControlViolation, validate_plan
from transition_lab.journal import PaperJournal
from transition_lab.model import fingerprint, optimize, validate_snapshot

FIXTURE=Path(__file__).resolve().parents[1]/'examples'/'transition_accounts.json'


def source():return json.loads(FIXTURE.read_text())


def resign(plan):
    plan['plan_id']=fingerprint({k:v for k,v in plan.items() if k!='plan_id'})
    return plan


def test_transition_prefers_high_basis_and_reconciles_both_accounts():
    s=source();p=optimize(s);report=validate_plan(s,p)
    assert report['passed']
    first,second=p['accounts']
    sales=[t for t in first['trades'] if t['side']=='sell']
    assert {t['lot_id'] for t in sales}=={'us-high-basis'}
    assert first['tax_reserve']==pytest.approx(sum(t['shares']*2 for t in sales))
    assert second['tax_reserve']==0
    assert all(t['side']=='buy' for t in second['trades'])
    for a in p['accounts']:
        assert a['ending_nav']==pytest.approx(a['initial_nav']-a['modeled_fee']-a['tax_reserve'])
        assert a['tracking_risk_after']<a['tracking_risk_before']


def test_tax_budget_frontier_is_not_funded_by_another_account():
    s=source();objectives=[]
    for budget in (0,100,250,500,1000):
        s['accounts'][0]['tax_budget']=budget
        p=optimize(s);validate_plan(s,p)
        a=p['accounts'][0]
        assert a['tax_reserve']<=budget+.005
        assert a['ending_cash']>=s['accounts'][0]['cash_floor']-.005
        objectives.append(a['objective_value'])
    assert np.max(np.diff(objectives))<1e-8
    s['accounts'][0]['cash_floor']=1e8
    with pytest.raises(ValueError,match='Infeasible'):optimize(s)


def test_no_fee_no_tax_single_account_reaches_known_target():
    s=source();s['accounts']=s['accounts'][:1]
    for lot in s['accounts'][0]['lots']:lot['tax_rate']=0
    p=optimize(s,cost_bps=0,cost_aversion=0)
    validate_plan(s,p,expected_cost_bps=0,expected_cost_aversion=0)
    assert list(p['accounts'][0]['ending_weights'].values())==pytest.approx([.4,.25,.3],abs=2e-6)
    assert p['accounts'][0]['ending_cash']==pytest.approx(4250,abs=.05)


def test_prohibited_loss_position_is_exited_without_claiming_a_tax_credit():
    s=source();s['accounts'][0]['blocked']=['INTL']
    p=optimize(s);validate_plan(s,p)
    a=p['accounts'][0]
    assert a['ending_values']['INTL']==pytest.approx(0,abs=.005)
    sells=[t for t in a['trades'] if t['side']=='sell']
    lots={l['lot_id']:l for l in s['accounts'][0]['lots']}
    positive_tax=sum(max(0,s['prices'][t['symbol']]-lots[t['lot_id']]['basis_per_share'])*t['shares']*lots[t['lot_id']]['tax_rate'] for t in sells)
    assert a['tax_reserve']==pytest.approx(positive_tax)
    assert any(t['symbol']=='INTL' for t in sells)


def test_forced_gain_liquidation_with_zero_tax_budget_fails_instead_of_relaxing_policy():
    s=source();s['accounts'][0]['blocked']=['US'];s['accounts'][0]['tax_budget']=0
    with pytest.raises(ValueError,match='Infeasible'):optimize(s)


def test_challenger_accepts_an_independently_hand_derived_tax_fee_cash_plan():
    s=source();s['symbols']=['A','B'];s['prices']={'A':10.,'B':20.};s['annual_covariance']=[[.04,0],[0,.09]]
    s['accounts']=[{'account_id':'hand','cash':100.,'cash_floor':40.,'tax_budget':2.,'target':{'A':.25,'B':.5},'blocked':[],'caps':{},
        'lots':[{'lot_id':'a','symbol':'A','shares':10.,'basis_per_share':8.,'tax_rate':.2,'acquired':'2020-01-02'},
                {'lot_id':'b','symbol':'B','shares':0.,'basis_per_share':20.,'tax_rate':.2,'acquired':'2020-01-02'}]}]
    nav=197.85;after=np.array([50/nav-.25,100/nav-.5])
    p={'evidence_type':'hypothetical','as_of':s['as_of'],'snapshot_sha256':fingerprint(s),'policy':{'cost_bps':10.,'cost_aversion':.05},
       'accounts':[{'account_id':'hand','trades':[{'side':'sell','symbol':'A','lot_id':'a','shares':5.},{'side':'buy','symbol':'B','lot_id':None,'shares':5.}],
          'initial_nav':200.,'ending_cash':47.85,'ending_nav':197.85,'modeled_fee':.15,'tax_reserve':2.,
          'ending_values':{'A':50.,'B':100.},'ending_weights':{'A':50/nav,'B':100/nav},
          'tracking_risk_before':np.sqrt(.025),'tracking_risk_after':float(np.sqrt(after@np.diag([.04,.09])@after)),
          'objective_value':.05*2.15/200}]}
    assert validate_plan(s,resign(p),expected_cost_bps=10.)['passed']


@pytest.mark.parametrize('fault',['future_risk','stale_quote','duplicate_lot','nan_price','negative_tax','bad_covariance'])
def test_invalid_inputs_fail_before_solving(fault):
    s=source()
    if fault=='future_risk':s['risk_as_of']=s['as_of']
    if fault=='stale_quote':s['price_as_of']='2026-10-13'
    if fault=='duplicate_lot':s['accounts'][0]['lots'].append(copy.deepcopy(s['accounts'][0]['lots'][0]))
    if fault=='nan_price':s['prices']['US']=float('nan')
    if fault=='negative_tax':s['accounts'][0]['tax_budget']=-1
    if fault=='bad_covariance':s['annual_covariance'][0][0]=-1
    with pytest.raises(ValueError):validate_snapshot(s)


@pytest.mark.parametrize('fault,control',[
    ('duplicate','no_duplicate_trade'),('oversell','no_oversell'),('fee','reported_modeled_fee'),
    ('cash','reported_ending_cash'),('policy','independent_fee_and_objective_policy'),('tax','reported_tax_reserve'),
    ('account','one_plan_per_account'),('risk','risk_after')])
def test_economic_challenger_catches_resigned_faults(fault,control):
    s=source();p=optimize(s);a=p['accounts'][0]
    if fault=='duplicate':a['trades'].append(copy.deepcopy(a['trades'][0]))
    if fault=='oversell':a['trades'][0]['shares']=1000
    if fault=='fee':a['modeled_fee']+=1
    if fault=='cash':a['ending_cash']+=1
    if fault=='policy':p['policy']['cost_bps']=0
    if fault=='tax':a['tax_reserve']=0
    if fault=='account':p['accounts'].append(copy.deepcopy(a))
    if fault=='risk':a['tracking_risk_after']=0
    with pytest.raises(ControlViolation,match=control):validate_plan(s,resign(p))


def cash_event():
    return {'event_id':'deposit-1','type':'cash_flow','settled_on':'2026-10-14','account_id':'cash-first','amount':1500.,'source':'hypothetical fixture'}


def test_duplicate_event_is_idempotent_and_conflicting_payload_fails(tmp_path):
    j=PaperJournal(tmp_path/'ledger.db',source());event=cash_event()
    first=j.apply(event,0);second=j.apply(event,0)
    assert first['nav_after']-first['nav_before']==1500
    assert first['investment_pnl']==0
    assert second['duplicate'] and j.read()['revision']==1
    event['amount']=2000
    with pytest.raises(ControlViolation,match='conflicting_idempotency_key'):j.apply(event,1)


def test_interrupted_write_rolls_back_and_reopen_replays_once(tmp_path):
    path=tmp_path/'ledger.db';j=PaperJournal(path,source());before=j.read()
    with pytest.raises(RuntimeError,match='injected_interruption'):j.apply(cash_event(),0,interrupt_before_commit=True)
    assert j.read()==before
    reopened=PaperJournal(path)
    assert reopened.apply(cash_event(),0)['revision']==1
    assert reopened.apply(cash_event(),1)['duplicate']
    assert PaperJournal(path).read()['revision']==1


def test_database_handles_close_after_initialization_read_and_commit(tmp_path):
    path=tmp_path/'ledger.db';j=PaperJournal(path,source())
    assert j.read()['revision']==0
    j.apply(cash_event(),0)
    # Windows refuses this rename if a connection still retains a file handle.
    renamed=path.with_suffix('.closed')
    path.rename(renamed)
    assert PaperJournal(renamed).read()['revision']==1


def test_split_preserves_nav_and_cost_basis_and_invalidates_old_plan(tmp_path):
    s=source();plan=optimize(s);j=PaperJournal(tmp_path/'ledger.db',s)
    split={'event_id':'split-1','type':'split','settled_on':'2026-10-14','symbol':'US','ratio':2.,'source':'hypothetical split fixture'}
    result=j.apply(split,0);state=j.read()['snapshot']
    assert result['nav_before']==pytest.approx(result['nav_after'])
    assert state['prices']['US']==50
    before=s['accounts'][0]['lots'][0];after=state['accounts'][0]['lots'][0]
    assert after['shares']==600 and after['basis_per_share']==10
    assert before['shares']*before['basis_per_share']==after['shares']*after['basis_per_share']
    with pytest.raises(ControlViolation,match='source_snapshot_fingerprint'):validate_plan(state,plan)


def test_future_cash_is_unavailable_and_stale_version_cannot_commit(tmp_path):
    j=PaperJournal(tmp_path/'ledger.db',source());event=cash_event();event['settled_on']='2026-10-15'
    with pytest.raises(ControlViolation,match='event_settlement'):j.apply(event,0)
    assert j.read()['revision']==0
    j.apply(cash_event(),0)
    event=cash_event();event['event_id']='deposit-2'
    with pytest.raises(ControlViolation,match='stale_state_version'):j.apply(event,0)


def test_plan_commit_reconciles_new_lots_and_is_not_reexecuted(tmp_path):
    s=source();p=optimize(s);j=PaperJournal(tmp_path/'ledger.db',s)
    event={'event_id':'transition-1','type':'transition','settled_on':s['as_of'],'source':'hypothetical plan','plan':p}
    result=j.apply(event,0);after=j.read()['snapshot']
    assert result['nav_after']==pytest.approx(sum(a['ending_nav'] for a in p['accounts']))
    for a,candidate in zip(after['accounts'],p['accounts']):
        assert a['cash']==candidate['ending_cash']
        assert a['tax_budget']==pytest.approx(500-candidate['tax_reserve'])
        for symbol in s['symbols']:
            value=sum(l['shares']*s['prices'][symbol] for l in a['lots'] if l['symbol']==symbol)
            assert value==pytest.approx(candidate['ending_values'][symbol])
    assert j.apply(event,0)['duplicate']
    assert j.read()['snapshot']==after


def test_public_view_rechecks_financial_results_not_just_saved_pass_labels():
    from build_transition_dashboard import validate_evidence
    evidence=json.loads((FIXTURE.parents[1]/'outputs/transition_lab/evidence.json').read_text())
    validate_evidence(evidence)
    evidence['frontier'][0]['plan']['accounts'][0]['ending_cash']+=25
    resign(evidence['frontier'][0]['plan'])
    with pytest.raises(ControlViolation,match='reported_ending_cash'):validate_evidence(evidence)


def test_public_view_rejects_stale_source_fingerprints():
    from build_transition_dashboard import validate_evidence
    evidence=json.loads((FIXTURE.parents[1]/'outputs/transition_lab/evidence.json').read_text())
    evidence['source_sha256']['transition_lab/model.py']='0'*64
    with pytest.raises(ValueError,match='Stale source receipt'):validate_evidence(evidence)
