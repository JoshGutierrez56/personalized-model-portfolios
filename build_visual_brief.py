"""Render a results brief from the completed WRDS study; no new backtest."""
from pathlib import Path
import hashlib
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter, MultipleLocator
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
SRC = ROOT / 'outputs/wrds'
OUT = SRC / 'visual_brief'
OUT.mkdir(parents=True, exist_ok=True)
BG, INK, MUTED, GRID = '#F6F4EF', '#172E43', '#627282', '#DDE1E2'
NAVY, TEAL, GRAY, GOLD = '#214B72', '#008578', '#8A98A6', '#B07924'
COLORS = {'Minimum risk': NAVY, 'Lower turnover': TEAL, 'Proportional': GRAY}
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 12, 'text.parse_math': False,
    'text.color': INK, 'axes.labelcolor': MUTED, 'xtick.color': MUTED,
    'ytick.color': INK, 'axes.edgecolor': GRID, 'figure.facecolor': BG,
    'axes.facecolor': BG, 'axes.spines.top': False, 'axes.spines.right': False,
    'axes.spines.left': False, 'axes.spines.bottom': False,
    'savefig.facecolor': BG, 'pdf.fonttype': 42})
summary = pd.read_csv(SRC / 'scenario_summary.csv')
sens = pd.read_csv(SRC / 'sensitivity_summary.csv')
intervals = pd.read_csv(SRC / 'tracking_risk_intervals.csv').set_index('client')
daily = pd.read_csv(ROOT / 'outputs/wrds_private/daily.csv', parse_dates=['date'])
bench = pd.read_csv(ROOT / 'outputs/wrds_private/benchmark.csv', parse_dates=['date'])
ng = summary.query("client == 'No gold'").set_index('method')
focal = daily.query("client == 'No gold'")
figures = []


def frame(number, title, subtitle):
    fig = plt.figure(figsize=(12.5, 10.5))
    fig.text(.055, .958, f'PERSONALIZED MODEL PORTFOLIOS   /   FINDING {number:02d}',
             fontsize=11, weight='bold', color=TEAL)
    fig.text(.055, .906, title, fontsize=26, weight='bold', va='top')
    fig.text(.055, .847, subtitle, fontsize=12.5, color=MUTED, va='top', linespacing=1.5)
    return fig


def footer(fig, note):
    fig.text(.055, .069, note, fontsize=10.3, color=MUTED, va='top', linespacing=1.45)
    fig.text(.055, .021, 'SOURCE  WRDS / CRSP CIZ | 2014–2025 evaluation | Hypothetical ETF accounts',
             fontsize=9.5, color=MUTED)


def clean(ax, grid='x'):
    ax.set_axisbelow(True)
    ax.grid(axis=grid, color=GRID, linewidth=.8)
    ax.tick_params(length=0, pad=9)


def save(fig, name):
    fig.savefig(OUT / f'{name}.png', dpi=180)
    vector = OUT / f'{name}.svg'
    fig.savefig(vector)
    vector.write_text('\n'.join(line.rstrip() for line in vector.read_text(encoding='utf-8').splitlines())+'\n', encoding='utf-8')
    figures.append((fig, name))


# 1. All constrained cases, not a selected subset.
table = summary.pivot(index='client', columns='method', values='gross_te_pct').drop('Unrestricted')
table = table.sort_values('Proportional', ascending=False)
reduction = 100 * (1 - table['Minimum risk'] / table['Proportional'])
fig = frame(1, 'Closer to the model in all 9 constrained cases',
    'Risk-aware allocation reduced realized tracking error by 20–69% versus proportional allocation.\n'
    'Tracking error measures variability of returns relative to the policy model; lower means closer tracking.')
ax = fig.add_axes([.30, .16, .57, .58])
ys = np.arange(len(table))
for y, (name, row) in zip(ys, table.iterrows()):
    a, b = row['Minimum risk'], row['Proportional']
    ax.plot([a, b], [y, y], color='#BCC8D0', lw=5, solid_capstyle='round')
    ax.scatter([b], [y], s=85, color=GRAY, zorder=3)
    ax.scatter([a], [y], s=105, color=NAVY, zorder=4)
    ax.annotate(f'{a:.2f}%', (a, y), xytext=(0, -18), textcoords='offset points',
                ha='center', color=NAVY, fontsize=10.5, weight='bold')
    ax.annotate(f'{b:.2f}%', (b, y), xytext=(0, 12), textcoords='offset points',
                ha='center', color=MUTED, fontsize=10.5)
    ax.text(3.01, y, f'−{reduction[name]:.0f}%', va='center', ha='left',
            weight='bold', fontsize=14, color=TEAL, clip_on=False)
labels = {'10% short Treasuries': '10% short-Treasury floor',
          '20% short Treasuries': '20% short-Treasury floor',
          'Retain 40% US large cap': '40% US large-cap floor',
          '20% US small-cap floor': '20% US small-cap floor'}
ax.set_yticks(ys, [labels.get(n, n) for n in table.index], fontsize=11)
ax.set_xlim(0, 2.9)
ax.set_ylim(len(table)-.4, -.7)
ax.xaxis.set_major_locator(MultipleLocator(.5))
ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{x:.1f}%'))
ax.set_xlabel('Annualized gross tracking error', labelpad=13)
clean(ax)
handles = [Line2D([], [], marker='o', linestyle='', color=c, label=l, markersize=9)
           for l, c in [('Minimum tracking risk', NAVY), ('Proportional allocation', GRAY)]]
fig.legend(handles=handles, loc='center', bbox_to_anchor=(.60, .775),
           frameon=False, ncol=2, fontsize=12)
fig.text(.895, .756, 'Reduction', fontsize=10, color=TEAL, weight='bold')
footer(fig, 'Same restrictions and monthly execution timing for both methods. Full constrained-scenario set shown.\n'
    '“Domestic and liquid” excludes EFA/EEM and sets a 15% SHY floor. Tracking risk is not expected return.')
save(fig, '01_risk_aware_allocation')


# 2. Economic cost versus tracking-risk trade-off, with separate units.
turn_saved = 100 * (1 - ng.loc['Lower turnover', 'annual_one_way_turnover_pct'] /
                   ng.loc['Minimum risk', 'annual_one_way_turnover_pct'])
extra_te = 100 * (ng.loc['Lower turnover', 'gross_te_pct'] - ng.loc['Minimum risk', 'gross_te_pct'])
cost_saved = ng.loc['Minimum risk', 'annual_incurred_cost_bps'] - ng.loc['Lower turnover', 'annual_incurred_cost_bps']
fig = frame(2, '60% less turnover. About $110/year saved.',
    'No-gold account, per $1 million: lower-turnover allocation versus minimum tracking risk.\n'
    'The cost benefit is small at the assumed 5 bp per traded dollar; tracking risk rises by 27 bp.')
metrics = [
    ('annual_one_way_turnover_pct', 'Annualized one-way turnover', 23, '%', f'−{turn_saved:.0f}%', 'less turnover'),
    ('gross_te_pct', 'Annualized gross tracking error', 2.1, '%', f'+{extra_te:.0f} bp', 'more tracking risk'),
    ('annual_incurred_cost_bps', 'Annualized modeled trading cost', 2.3, ' bp', f'−{cost_saved:.2f} bp', 'of account value / year'),
]
for bottom, (metric, title, xmax, unit, callout, sub) in zip([.595, .36, .125], metrics):
    ax = fig.add_axes([.235, bottom, .50, .125])
    for y, method in enumerate(['Minimum risk', 'Lower turnover']):
        v = ng.loc[method, metric]
        ax.barh(y, v, height=.43, color=COLORS[method])
        ax.text(v+.025*xmax, y, f'{v:.2f}{unit}', va='center', weight='bold', fontsize=13,
                color=COLORS[method])
    ax.set_yticks([0, 1], ['Minimum risk', 'Lower turnover'], fontsize=12)
    ax.set_ylim(1.7, -.7)
    ax.set_xlim(0, xmax)
    ax.set_xticks([])
    ax.set_title(title, loc='left', fontsize=13, weight='bold', pad=12)
    fig.text(.79, bottom+.06, callout, fontsize=24, weight='bold', color=GOLD if metric=='gross_te_pct' else TEAL)
    fig.text(.79, bottom+.025, sub, fontsize=10.5, color=MUTED)
ci = intervals.loc['No gold']
footer(fig, f'Added TE: {extra_te:.1f} bp; paired 95% block-bootstrap interval {100*ci.lower_95_pp:.1f}–{100*ci.upper_95_pp:.1f} bp (1,000 resamples).\n'
    '$110/year is the annualized cost-rate difference scaled to a constant $1m NAV, not a return forecast.')
save(fig, '02_turnover_tradeoff')


# 3. Portfolio history, including a benchmark and actual ending wealth.
fig = frame(3, 'Closest tracking did not mean highest return',
    'No-gold accounts, starting at $1 million. The policy benchmark includes a 10% gold allocation.\n'
    'Differences reflect exposure choices—not evidence of alpha or a forecast of future performance.')
benchmark_cagr = 100*((bench.benchmark_nav.iloc[-1]/1e6)**(252/len(bench))-1)
series = [('Policy benchmark', INK, bench.benchmark_nav.iloc[-1], benchmark_cagr)] + [
    (m, COLORS[m], ng.loc[m, 'terminal_nav'], ng.loc[m, 'net_cagr_pct'])
    for m in ['Lower turnover', 'Proportional', 'Minimum risk']]
for x, (label, color, nav, cagr) in zip([.065, .303, .542, .78], series):
    fig.text(x, .758, label, color=color, weight='bold', fontsize=11.5)
    fig.text(x, .719, f'${nav/1e6:.2f}m', color=color, weight='bold', fontsize=23)
    fig.text(x, .693, f'{cagr:.2f}% annualized return', color=MUTED, fontsize=10.5)
ax = fig.add_axes([.09, .37, .855, .275])
ax.plot(bench.date, bench.benchmark_nav/1e6, color=INK, lw=2.0, ls='--', label='Policy benchmark')
for method in ['Proportional', 'Lower turnover', 'Minimum risk']:
    g = focal.query('method == @method').sort_values('date')
    ax.plot(g.date, g.nav/1e6, color=COLORS[method], lw=1.7)
ax.set_ylabel('Account value ($m)')
ax.set_ylim(.80, 2.75)
clean(ax, 'y')
ax2 = fig.add_axes([.09, .14, .855, .155])
for method in ['Proportional', 'Lower turnover', 'Minimum risk']:
    g = focal.query('method == @method').sort_values('date')
    te = g.gross_active_return.rolling(252).std()*np.sqrt(252)*100
    ax2.plot(g.date, te, color=COLORS[method], lw=1.6)
ax2.set_title('How much tracking risk changed through time', loc='left', fontsize=12, weight='bold', pad=10)
ax2.set_ylabel('Trailing 1-year TE (%)', fontsize=10.5)
ax2.set_ylim(0, None)
for axis in [ax, ax2]:
    axis.set_xlim(pd.Timestamp('2014-01-01'), pd.Timestamp('2025-12-31'))
clean(ax2, 'y')
footer(fig, 'Portfolio wealth and returns are net of modeled trading costs; the policy benchmark is frictionless.\n'
    'Trailing TE uses 252 daily observations, before trading costs. Initial positions transition at the first close.')
save(fig, '03_wealth_and_risk')


# 4. Every completed sensitivity, measured against its own minimum-risk path.
f = sens.query("client == 'No gold'")
order = f.specification.drop_duplicates().tolist()
p = f.pivot(index='specification', columns='method',
            values=['gross_te_pct', 'annual_incurred_cost_bps', 'annual_one_way_turnover_pct']).loc[order]
d = pd.DataFrame(index=order)
d['extra_te_bps'] = 100*(p.gross_te_pct['Lower turnover']-p.gross_te_pct['Minimum risk'])
d['annual_dollars_saved_per_million'] = 100*(p.annual_incurred_cost_bps['Minimum risk']-p.annual_incurred_cost_bps['Lower turnover'])
d['turnover_reduction_pct'] = 100*(1-p.annual_one_way_turnover_pct['Lower turnover']/p.annual_one_way_turnover_pct['Minimum risk'])
fig = frame(4, 'Doubling the risk budget barely saves more',
    'No-gold account: base specification plus all eight sensitivity runs. Each row is a full simulation.\n'
    'A 50 bp allowance doubles added realized tracking risk, but saves only ~$5/year more per $1m.')
axs = [fig.add_axes([.285, .18, .265, .57]), fig.add_axes([.65, .18, .265, .57])]
names = ['Base: 25 bp risk / 5 bp cost', '1-year risk history', '2-year risk history',
         'Sample covariance', '0 bp risk allowance', '50 bp risk allowance',
         '1 bp trading cost', '10 bp trading cost', '25 bp trading cost']
for j, (ax, metric, title, xmax) in enumerate(zip(axs,
        ['extra_te_bps', 'annual_dollars_saved_per_million'],
        ['Added tracking risk (bp)', 'Annual cost savings / $1m'], [65, 650])):
    for y, row in enumerate(d.itertuples()):
        if y in [0, 5]:
            ax.axhspan(y-.42, y+.42, color='#E6EDE8' if y==0 else '#F1E5CB', zorder=0)
        val = getattr(row, metric)
        color = GOLD if y==5 else TEAL if j==1 else NAVY
        ax.plot([0, val], [y, y], color=color, lw=2.5)
        ax.scatter([val], [y], s=75, color=color, zorder=3)
        label = f'{val:.1f}' if j==0 else f'${val:,.0f}'
        ax.text(val+xmax*.035, y, label, va='center', fontsize=11, color=color, weight='bold')
    ax.set_xlim(-xmax*.02, xmax)
    ax.set_ylim(len(d)-.4, -.8)
    ax.set_yticks(range(len(d)), names if j==0 else ['']*len(d), fontsize=11)
    ax.set_title(title, fontsize=12, loc='left', weight='bold', pad=14)
    ax.xaxis.set_major_locator(MultipleLocator(20 if j==0 else 200))
    if j==1:
        ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f'${x:,.0f}'))
    clean(ax)
footer(fig, 'Base: 756-day Ledoit–Wolf risk estimate; estimated TE allowance of 25 bp; 5 bp per traded dollar.\n'
    'Rows change one assumption. Savings scale annual cost-rate differences to $1m, not actual fixed dollar bills.')
save(fig, '04_sensitivity_economics')


# Verify displayed path-based statistics against the saved research summary.
for method, g in focal.groupby('method'):
    expected_te = g.gross_active_return.std()*np.sqrt(252)*100
    assert abs(expected_te-ng.loc[method, 'gross_te_pct']) < 1e-9
    assert abs(g.sort_values('date').nav.iloc[-1]-ng.loc[method, 'terminal_nav']) < 1e-6
assert (table['Minimum risk'] < table['Proportional']).all()
assert len(d) == 9
with PdfPages(OUT / 'WRDS_results_visual_brief.pdf') as pdf:
    for fig, _ in figures:
        pdf.savefig(fig)
        plt.close(fig)
d.to_csv(OUT / 'no_gold_sensitivity_comparison.csv', index_label='specification')
inputs = [SRC/'scenario_summary.csv', SRC/'sensitivity_summary.csv', SRC/'tracking_risk_intervals.csv',
          ROOT/'outputs/wrds_private/daily.csv', ROOT/'outputs/wrds_private/benchmark.csv']
receipt = {'scope': 'Presentation of saved study; no parameter changes or new simulations',
    'input_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
    'charts': [name+'.png' for _, name in figures],
    'data_checks': 'TE and ending wealth reconciled to daily paths; all 9 constrained cases and all 8 sensitivities included',
    'benchmark_cagr_pct': benchmark_cagr, 'benchmark_terminal_nav': float(bench.benchmark_nav.iloc[-1]),
    'no_gold_turnover_reduction_pct': turn_saved, 'no_gold_added_te_bps': extra_te,
    'no_gold_cost_savings_bps': cost_saved, 'median_constrained_te_reduction_pct': float(reduction.median())}
(OUT/'visual_brief_receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
print(json.dumps(receipt, indent=2))
