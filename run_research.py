"""Execute the pre-specified WRDS study and write aggregate, auditable outputs."""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from portfolio_engine import TICKERS, example_clients
from walkforward import (StudyConfig, METHODS, run_walkforward, summarize_run,
                         period_summary, paired_block_bootstrap)
from wrds_data import load_wrds

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs/wrds"
PRIVATE = ROOT / "outputs/wrds_private"
COLORS = {"Proportional":"#8b98a8", "Minimum risk":"#153b59", "Lower turnover":"#168c86"}


def code_hashes():
    return {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
            ["portfolio_engine.py", "wrds_data.py", "walkforward.py", "run_research.py"]}


def charts(summary, yearly, run, sensitivity):
    plt.rcParams.update({"figure.dpi":120,"font.size":10,"axes.spines.top":False,
                         "axes.spines.right":False,"axes.titleweight":"bold"})
    order = [c.name for c in example_clients()]
    fig, axes=plt.subplots(1,2,figsize=(14,6),sharey=True)
    y=np.arange(len(order))
    for ax,metric,title in zip(axes,["gross_te_pct","annual_one_way_turnover_pct"],
            ["Realized tracking risk (before trading costs)","Annualized one-way turnover"]):
        table=summary.pivot(index="client",columns="method",values=metric).loc[order]
        for shift,method in zip([-.23,0,.23],METHODS):
            ax.barh(y+shift,table[method],height=.21,color=COLORS[method],label=method)
        ax.set_title(title,fontsize=11); ax.set_xlabel("Percent"); ax.grid(axis="x",alpha=.15)
    axes[0].set_yticks(y,order); axes[0].invert_yaxis()
    axes[1].legend(frameon=False,loc="upper left",bbox_to_anchor=(1,1))
    fig.suptitle("CRSP / WRDS: the cost of customization, 2014–2025",fontsize=15)
    fig.tight_layout(); fig.savefig(OUT/"tracking_and_turnover.png",dpi=160,bbox_inches="tight"); plt.close(fig)

    fig,axes=plt.subplots(2,1,figsize=(11,7),sharex=True)
    focal="No gold"
    for method in METHODS:
        group=run['daily'].query("client == @focal and method == @method").set_index('date')
        relative=(1+group.net_return).cumprod()/(1+group.benchmark_return).cumprod()-1
        axes[0].plot(group.index,relative*100,color=COLORS[method],label=method)
        rolling=group.gross_active_return.rolling(252).std()*np.sqrt(252)*100
        axes[1].plot(group.index,rolling,color=COLORS[method])
    axes[0].set_title("No-gold account: path and risk relative to the policy benchmark")
    axes[0].set_ylabel("Net relative wealth (%)"); axes[0].legend(frameon=False)
    axes[1].set_ylabel("Trailing 252-day gross TE (%)")
    axes[0].axhline(0,color='#777',linewidth=.7)
    for ax in axes: ax.grid(alpha=.15)
    fig.tight_layout(); fig.savefig(OUT/'no_gold_history.png',dpi=160); plt.close(fig)

    fig,ax=plt.subplots(figsize=(11,5))
    focus=yearly.query("client == 'No gold'")
    for method in METHODS:
        part=focus.query('method == @method')
        ax.plot(part.year,part.gross_te_pct,'o-',label=method,color=COLORS[method])
    ax.set(title="No-gold account: risk varies materially by year",xlabel="Calendar year",ylabel="Realized gross tracking error (%)")
    ax.legend(frameon=False); ax.grid(alpha=.15)
    fig.tight_layout();fig.savefig(OUT/'annual_risk.png',dpi=160);plt.close(fig)

    if not sensitivity.empty:
        focus=sensitivity.query("client == 'No gold'").copy()
        labels=focus.specification.drop_duplicates().tolist()
        fig,axes=plt.subplots(1,2,figsize=(14,6),sharey=True)
        y=np.arange(len(labels))
        for ax,metric,title in zip(axes,["gross_te_pct","annual_one_way_turnover_pct"],
                ["Realized gross tracking error (%)","Annualized one-way turnover (%)"]):
            table=focus.pivot(index="specification",columns="method",values=metric).loc[labels]
            for shift,method in zip([-.23,0,.23],METHODS):
                ax.barh(y+shift,table[method],height=.21,color=COLORS[method],label=method)
            ax.set_title(title,fontsize=11);ax.grid(axis="x",alpha=.15)
        axes[0].set_yticks(y,labels);axes[0].invert_yaxis()
        axes[1].legend(frameon=False,loc="upper left",bbox_to_anchor=(1,1))
        fig.suptitle("No-gold sensitivity: each row is a complete simulation",fontsize=14)
        fig.tight_layout();fig.savefig(OUT/'sensitivity.png',dpi=160,bbox_inches='tight');plt.close(fig)


def execute(include_sensitivity=True):
    OUT.mkdir(parents=True,exist_ok=True);PRIVATE.mkdir(parents=True,exist_ok=True)
    returns, raw, provenance=load_wrds()
    raw['dollar_volume']=pd.to_numeric(raw.price,errors='coerce').abs()*pd.to_numeric(raw.volume,errors='coerce')
    volume=raw.pivot(index='date',columns='ticker',values='dollar_volume').reindex(columns=TICKERS)
    config=StudyConfig()
    print('Running main study: 10 scenarios x 3 methods; 144 monthly executions expected.',flush=True)
    run=run_walkforward(returns,config,dollar_volume=volume)
    summary=summarize_run(run,config);yearly=period_summary(run)
    # Detailed simulated holdings/returns/trades and source rows remain local.
    for name,frame in run.items(): frame.to_csv(PRIVATE/f'{name}.csv',index=False)
    summary.to_csv(OUT/'scenario_summary.csv',index=False)
    yearly.to_csv(OUT/'annual_summary.csv',index=False)
    print('Main study complete; running paired block intervals.',flush=True)
    intervals=paired_block_bootstrap(run)
    intervals.to_csv(OUT/'tracking_risk_intervals.csv',index=False)
    sensitivity_frames=[]
    selected=[c for c in example_clients() if c.name in ['No gold','Retain 40% US large cap','Domestic and liquid']]
    base_subset=summary[summary.client.isin([c.name for c in selected])].copy()
    base_subset['specification']='Base: 756d / 25bp / 5bp';sensitivity_frames.append(base_subset)
    specifications=[
        ('252-day covariance',replace(config,lookback=252)),
        ('504-day covariance',replace(config,lookback=504)),
        ('Sample covariance',replace(config,covariance='sample')),
        ('0bp risk allowance',replace(config,allowance_bps=0)),
        ('50bp risk allowance',replace(config,allowance_bps=50)),
        ('1bp trading cost',replace(config,cost_bps=1)),
        ('10bp trading cost',replace(config,cost_bps=10)),
        ('25bp trading cost',replace(config,cost_bps=25)),
    ]
    completed=[]
    if include_sensitivity:
        for i,(label,spec) in enumerate(specifications,1):
            print(f'Sensitivity {i}/{len(specifications)}: {label}',flush=True)
            trial=run_walkforward(returns,spec,selected,dollar_volume=volume)
            part=summarize_run(trial,spec);part['specification']=label
            sensitivity_frames.append(part);completed.append({'label':label,'config':asdict(spec)})
    sensitivity=pd.concat(sensitivity_frames,ignore_index=True)
    sensitivity.to_csv(OUT/'sensitivity_summary.csv',index=False)
    charts(summary,yearly,run,sensitivity)
    quality={
        'source':provenance['source'],'retrieved_utc':provenance['retrieved_utc'],
        'tables':{'returns':provenance['returns_table'],'identities':provenance['identity_table'],'calendar':provenance['calendar_table']},
        'return_field':'dlyret','identity_asof':provenance['identity_asof'],
        'requested_start':provenance['requested_start'],'requested_end':provenance['requested_end'],
        'security_day_rows':provenance['rows'],'trading_days':provenance['trading_days'],
        'assets':provenance['assets'],'missing_returns':0,'duplicate_security_dates':0,
        'return_flags':provenance['flags'],'local_source_file_sha256':provenance['files'],
        'license_boundary':'Raw CRSP extracts and detailed daily simulation files are local-only and gitignored.',
    }
    (OUT/'data_quality.json').write_text(json.dumps(quality,indent=2),encoding='utf-8')
    daily,decisions,trades=run['daily'],run['decisions'],run['trades']
    trading=trades.trade_dollars.abs()>1e-5
    liquidity=trades.loc[trading,'participation']
    evidence={
        'completed_utc':datetime.now(timezone.utc).isoformat(),'data_source':provenance['source'],
        'config':asdict(config),'out_of_sample_start':str(daily.date.min().date()),
        'out_of_sample_end':str(daily.date.max().date()),'evaluation_days':int(daily.date.nunique()),
        'client_scenarios':10,'methods':list(METHODS),'portfolio_paths':len(summary),
        'rebalance_dates':int(decisions.execution_date.nunique()),'validated_allocation_decisions':len(decisions),
        'strict_signal_before_execution':bool((decisions.signal_date<decisions.execution_date).all()),
        'solver_retries_main':int(decisions.solver_retry_count.sum()),
        'solver_status_counts':decisions.solver_status.value_counts().to_dict(),
        'sensitivity_specifications':completed,
        'bootstrap':{'repetitions':1000,'block_trading_days':21,'seed':20260930,'interpretation':'Paired descriptive intervals, not a strategy-selection significance claim.'},
        'maximum_trade_to_lagged_adv20_pct':float(liquidity.max()*100),
        'nonzero_trades_missing_adv20':int(liquidity.isna().sum()),
        'python':sys.version.split()[0],
        'packages':{p:importlib.metadata.version(p) for p in ['numpy','pandas','cvxpy','scikit-learn','psycopg2-binary']},
        'code_sha256':code_hashes(),
        'interpretation':'Historical WRDS-backed simulation of hypothetical constrained ETF accounts; not live trading or alpha evidence.'}
    (OUT/'run_summary.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    print(f'COMPLETE: {len(decisions)} monthly allocation decisions; {len(completed)} sensitivity specifications.',flush=True)
    return evidence


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-only',action='store_true',help='Skip sensitivity reruns; receipt labels exactly what ran.')
    args=parser.parse_args()
    execute(not args.base_only)
