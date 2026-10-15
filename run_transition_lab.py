"""Build synthetic transition/frontier/control evidence without licensed inputs."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import tempfile

from transition_lab.challenger import ControlViolation, validate_plan
from transition_lab.journal import PaperJournal
from transition_lab.model import fingerprint, optimize

ROOT=Path(__file__).resolve().parent


def resign(plan):
    plan['plan_id']=fingerprint({k:v for k,v in plan.items() if k!='plan_id'})
    return plan


def build_evidence():
    source=json.loads((ROOT/'examples/transition_accounts.json').read_text(encoding='utf-8'))
    plan=optimize(source);validation=validate_plan(source,plan)
    frontier=[]
    for budget in (0,100,250,500,1000,2500,10000):
        snapshot=copy.deepcopy(source)
        for account in snapshot['accounts']:account['tax_budget']=budget
        result=optimize(snapshot);checked=validate_plan(snapshot,result)
        frontier.append({'budget_per_account':budget,'plan':result,'validation':checked})
    definitions=[
        ('duplicate_instruction','Same sale appears twice','no_duplicate_trade','Deduplicate by account, side, security and lot; recalculate the plan.'),
        ('oversell','Sale exceeds the selected lot','no_oversell','Rebuild from current available shares; never borrow another account\'s lot.'),
        ('fee_understatement','Modeled fee reduced by $1','reported_modeled_fee','Recalculate costs on purchases and sales, not only net exposure.'),
        ('tax_omission','Positive-gain reserve shown as zero','reported_tax_reserve','Reconstruct gains by sold lot and input rate; do not silently net losses.'),
        ('cash_subsidy','Reported cash increased by $1','reported_ending_cash','Reconcile each account separately; no cross-account subsidy.'),
        ('policy_override','Plan declares zero transaction costs','independent_fee_and_objective_policy','Compare against the independently supplied fee policy.'),
        ('stale_snapshot','Source cash changed after planning','source_snapshot_fingerprint','Rebuild and revalidate against the current snapshot.'),
        ('future_risk','Risk timestamp equals the decision date','strictly_prior_risk','Use an eligible strictly prior risk estimate.')]
    incidents=[]
    for name,title,expected,remedy in definitions:
        snapshot=copy.deepcopy(source);corrupt=copy.deepcopy(plan);account=corrupt['accounts'][0]
        if name=='duplicate_instruction':account['trades'].append(copy.deepcopy(account['trades'][0]))
        if name=='oversell':account['trades'][0]['shares']=1000
        if name=='fee_understatement':account['modeled_fee']-=1
        if name=='tax_omission':account['tax_reserve']=0
        if name=='cash_subsidy':account['ending_cash']+=1
        if name=='policy_override':corrupt['policy']['cost_bps']=0
        if name=='stale_snapshot':snapshot['accounts'][0]['cash']+=100
        if name=='future_risk':
            snapshot['risk_as_of']=snapshot['as_of'];corrupt['snapshot_sha256']=fingerprint(snapshot)
        resign(corrupt)
        try:validate_plan(snapshot,corrupt)
        except ControlViolation as exc:
            if expected not in str(exc):raise AssertionError((name,expected,str(exc))) from exc
            incidents.append({'id':name,'title':title,'status':'BLOCKED','control':str(exc),'correction':remedy,
                              'clean_retest':'PASS' if validate_plan(source,plan)['passed'] else 'FAIL'})
        else:raise AssertionError('Fault escaped: '+name)
    operations=[]
    with tempfile.TemporaryDirectory(prefix='transition-paper-') as temporary:
        path=Path(temporary)/'journal.sqlite';journal=PaperJournal(path,source)
        deposit={'event_id':'deposit-1','type':'cash_flow','settled_on':source['as_of'],
                 'source':'Hypothetical contribution fixture','account_id':'cash-first','amount':1500.}
        operations.append({'step':'Record external contribution, not investment profit',**journal.apply(deposit,0)})
        operations.append({'step':'Replay identical contribution without applying twice',**journal.apply(deposit,0)})
        before=journal.read();fresh=optimize(before['snapshot'])
        event={'event_id':'transition-1','type':'transition','settled_on':source['as_of'],
               'source':'Independently checked hypothetical plan','plan':fresh}
        try:journal.apply(event,1,interrupt_before_commit=True)
        except RuntimeError:
            assert journal.read()==before
            operations.append({'step':'Interrupt between journal write and commit','status':'ROLLED BACK','revision':before['revision']})
        else:raise AssertionError('Expected injected interruption')
        reopened=PaperJournal(path)
        operations.append({'step':'Reopen and commit the checked plan once',**reopened.apply(event,1)})
        operations.append({'step':'Retry the committed plan without executing again',**reopened.apply(event,1)})
        split={'event_id':'split-1','type':'split','settled_on':source['as_of'],'source':'Hypothetical two-for-one split',
               'symbol':'US','ratio':2.}
        operations.append({'step':'Apply split with share/basis/value conservation',**reopened.apply(split,2)})
        assert PaperJournal(path).read()['revision']==3
    files=[*sorted((ROOT/'transition_lab').glob('*.py')),ROOT/'run_transition_lab.py',ROOT/'examples/transition_accounts.json']
    return {'evidence_type':'hypothetical','decision_date':source['as_of'],'snapshot':source,'baseline_plan':plan,
        'baseline_validation':validation,'frontier':frontier,'incidents':incidents,'operations':operations,
        'source_sha256':{str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        'limits':['Illustrative covariance and prices; not an empirical performance backtest.',
                  'Positive-gain tax reserves, not comprehensive tax calculations or paid taxes.',
                  'Direction-restricted fractional-share optimization; not unrestricted global tax-optimality.',
                  'Local single-decision-date paper journal; no broker connection or live operating history.',
                  'Calculation-path independence within one development process; no independent human certification.']}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--no-write',action='store_true')
    parser.add_argument('--output',type=Path,default=ROOT/'outputs/transition_lab/evidence.json');args=parser.parse_args()
    evidence=build_evidence()
    if not args.no_write:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(evidence,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'accounts':len(evidence['baseline_plan']['accounts']),'frontier_scenarios':len(evidence['frontier']),
                      'faults_blocked':len(evidence['incidents']),'paper_operating_steps':len(evidence['operations']),
                      'baseline_control_assertions':evidence['baseline_validation']['controls_passed'],'wrote_evidence':not args.no_write}))


if __name__=='__main__':main()
