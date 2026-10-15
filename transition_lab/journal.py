"""Local paper ledger: atomic state, idempotency, stale-version rejection.

No broker connector, tax filing, settlement service, or live execution exists.
"""
import copy
from contextlib import closing
from datetime import date
import hashlib
import json
import math
import sqlite3

from .challenger import ControlViolation, validate_plan


def encode(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)


def digest(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


class PaperJournal:
    def __init__(self,path,snapshot=None,policy=None):
        self.path=str(path)
        authorized=policy or {'cost_bps':5.,'cost_aversion':.05}
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL, snapshot TEXT NOT NULL, sha256 TEXT NOT NULL, policy TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS events (event_id TEXT PRIMARY KEY, payload_sha256 TEXT NOT NULL, revision INTEGER UNIQUE NOT NULL, payload TEXT NOT NULL, result TEXT NOT NULL)')
            existing=db.execute('SELECT snapshot, policy FROM state WHERE id=1').fetchone()
            if existing is None:
                if snapshot is None:raise ValueError('Initial hypothetical snapshot is required')
                if snapshot.get('evidence_type')!='hypothetical':raise ValueError('Paper ledger requires hypothetical state')
                db.execute('INSERT INTO state VALUES (1,0,?,?,?)',(encode(snapshot),digest(snapshot),encode(authorized)))
            elif snapshot is not None and (existing[0]!=encode(snapshot) or existing[1]!=encode(authorized)):
                raise ControlViolation('refuse_to_overwrite_existing_journal')
            db.commit()

    def read(self):
        with closing(sqlite3.connect(self.path)) as db:
            row=db.execute('SELECT revision,snapshot,sha256 FROM state WHERE id=1').fetchone()
        state=json.loads(row[1])
        if digest(state)!=row[2]:raise ControlViolation('journal_state_checksum')
        return {'revision':row[0],'snapshot':state,'snapshot_sha256':row[2]}

    def apply(self,event,expected_revision,interrupt_before_commit=False):
        event_id=event.get('event_id')
        if not isinstance(event_id,str) or not event_id.strip():raise ControlViolation('event_id_required')
        payload_hash=digest(event)
        db=sqlite3.connect(self.path,isolation_level=None)
        try:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT revision,snapshot,sha256,policy FROM state WHERE id=1').fetchone()
            existing=db.execute('SELECT payload_sha256,revision,result FROM events WHERE event_id=?',(event_id,)).fetchone()
            if existing:
                if existing[0]!=payload_hash:raise ControlViolation('conflicting_idempotency_key')
                db.commit()
                return {'duplicate':True,'event_revision':existing[1],'current_revision':row[0],'original_result':json.loads(existing[2])}
            if not isinstance(expected_revision,int) or isinstance(expected_revision,bool) or expected_revision!=row[0]:
                raise ControlViolation('stale_state_version')
            snapshot=json.loads(row[1]);policy=json.loads(row[3])
            if digest(snapshot)!=row[2]:raise ControlViolation('journal_state_checksum')
            if date.fromisoformat(event['settled_on'])!=date.fromisoformat(snapshot['as_of']):
                raise ControlViolation('event_settlement_not_current_decision_date')
            if not isinstance(event.get('source'),str) or not event['source'].strip():raise ControlViolation('event_source_required')
            updated=copy.deepcopy(snapshot)
            nav_before=self._nav(snapshot)
            cash_flow=0.;fees=0.;reserve=0.
            if event['type']=='cash_flow':
                amount=event['amount']
                if isinstance(amount,bool) or not isinstance(amount,(int,float)) or not math.isfinite(amount):raise ControlViolation('cash_flow_amount')
                accounts=[a for a in updated['accounts'] if a['account_id']==event['account_id']]
                if len(accounts)!=1:raise ControlViolation('cash_flow_account')
                accounts[0]['cash']+=amount
                if accounts[0]['cash']<0:raise ControlViolation('cash_flow_overdraft')
                cash_flow=amount
            elif event['type']=='split':
                ratio=event['ratio'];symbol=event['symbol']
                if isinstance(ratio,bool) or not isinstance(ratio,(int,float)) or not math.isfinite(ratio) or ratio<=0 or symbol not in updated['prices']:
                    raise ControlViolation('split_terms')
                basis_before=sum(l['shares']*l['basis_per_share'] for a in updated['accounts'] for l in a['lots'])
                for account in updated['accounts']:
                    for lot in account['lots']:
                        if lot['symbol']==symbol:lot['shares']*=ratio;lot['basis_per_share']/=ratio
                updated['prices'][symbol]/=ratio
                basis_after=sum(l['shares']*l['basis_per_share'] for a in updated['accounts'] for l in a['lots'])
                if not math.isclose(basis_before,basis_after,rel_tol=1e-12,abs_tol=1e-8):raise ControlViolation('split_basis_conservation')
            elif event['type']=='transition':
                plan=event['plan']
                validate_plan(snapshot,plan,expected_cost_bps=policy['cost_bps'],expected_cost_aversion=policy['cost_aversion'])
                for candidate in plan['accounts']:
                    account=next(a for a in updated['accounts'] if a['account_id']==candidate['account_id'])
                    for trade in candidate['trades']:
                        if trade['side']=='sell':
                            lot=next(l for l in account['lots'] if l['lot_id']==trade['lot_id'])
                            lot['shares']=max(0.,lot['shares']-trade['shares'])
                        else:
                            rate=account.get('new_lot_tax_rate')
                            if isinstance(rate,bool) or not isinstance(rate,(int,float)) or not math.isfinite(rate) or not 0<=rate<=1:raise ControlViolation('new_lot_tax_rate_required')
                            account['lots'].append({'lot_id':event_id+':'+account['account_id']+':'+trade['symbol'],
                                'symbol':trade['symbol'],'shares':trade['shares'],'basis_per_share':updated['prices'][trade['symbol']],
                                'tax_rate':rate,'acquired':updated['as_of']})
                    account['cash']=candidate['ending_cash']
                    account['tax_budget']=max(0.,account['tax_budget']-candidate['tax_reserve'])
                    account['tax_reserve_cumulative']=account.get('tax_reserve_cumulative',0.)+candidate['tax_reserve']
                    fees+=candidate['modeled_fee'];reserve+=candidate['tax_reserve']
            else:raise ControlViolation('unknown_event_type')
            nav_after=self._nav(updated)
            if not math.isclose(nav_after,nav_before+cash_flow-fees-reserve,rel_tol=1e-10,abs_tol=.005):
                raise ControlViolation('event_nav_reconciliation')
            version=row[0]+1
            result={'duplicate':False,'revision':version,'event_id':event_id,'type':event['type'],
                    'snapshot_sha256':digest(updated),'nav_before':nav_before,'nav_after':nav_after,
                    'external_cash_flow':cash_flow,'modeled_fee':fees,'tax_reserve':reserve,
                    'investment_pnl':nav_after-nav_before-cash_flow+fees+reserve}
            db.execute('INSERT INTO events VALUES (?,?,?,?,?)',(event_id,payload_hash,version,encode(event),encode(result)))
            db.execute('UPDATE state SET revision=?,snapshot=?,sha256=? WHERE id=1',(version,encode(updated),digest(updated)))
            if interrupt_before_commit:raise RuntimeError('injected_interruption_before_commit')
            db.commit();return result
        except BaseException:
            db.rollback();raise
        finally:db.close()

    @staticmethod
    def _nav(snapshot):
        return sum(a['cash']+sum(l['shares']*snapshot['prices'][l['symbol']] for l in a['lots']) for a in snapshot['accounts'])
