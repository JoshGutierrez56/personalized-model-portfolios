# Research design: the cost of customization

## Question and experimental design

How much realized deviation from a multi-asset model results from a client
restriction, and how much turnover can be avoided by accepting an explicit risk
allowance? This is not an expected-return forecast or an alpha search.

The model has weights **30/10/15/5/20/5/10/5%** in SPY/IWM/EFA/EEM/IEF/TLT/GLD/SHY.
Each hypothetical account begins at **40/15/10/5/10/5/10/5%**, with $1 million in
total-return sleeves. Ten scenarios impose exclusions, floors and caps. The
accounts and target weights are hypothetical; the underlying returns are CRSP.
SHY is a short-duration Treasury ETF, not risk-free cash. A weight floor is not
a no-sale rule for specific shares or tax lots.

The baseline design was specified before the new WRDS result was inspected:

| Item | Specification |
|---|---|
| Data | Daily CRSP CIZ total returns, 2010–2025 |
| Evaluation | 2014–2025 |
| Risk estimator | Ledoit–Wolf, trailing 756 trading observations, annualized by 252 |
| Signal | Prior month's final trading close |
| Execution | Following month's first trading close |
| Benchmark | Same fixed policy weights, drifting between the same monthly reset dates, frictionless |
| Initial account | Same legacy allocation for each method; the first execution funds its transition |
| Costs | 5 bp per traded dollar, charged to buys and sells |
| Risk allowance | Minimum feasible estimated TE + 25 bp |
| Methods | Bounded proportional; minimum tracking risk; minimum turnover within TE budget |

The base specification is retained across sensitivity runs. We do not select a
winning parameter using the evaluation-period results. Because this is a
retrospective research development, do not describe the design as a registered
prospective experiment or call 2014–2025 a never-inspected market history.

## Decision clock

At signal close s, estimate covariance from the last 756 returns ending at s.
Construct the proposed weights from that covariance and the account's weights at
s. The next trading day's return is then earned by the **old** positions. Execute
the previously computed allocation at that next close, funding all modeled costs
from the account. New positions earn subsequent returns.

Thus a return on execution day cannot influence that day's proposal. A price move
during the signal-to-execution interval can make realized trading differ from
the optimized amount. The model assumes fractional closing-price allocations,
not guaranteed fills in exact quantities fixed one day in advance.

Between rebalances, each sleeve changes by its own CRSP total return. Weights
drift; they are not silently reset every day. Caps and floors apply at execution
closes. Any drift beyond them on other dates is measured and reported. Prohibited
positions exit at the first transition close and remain zero after that.

## Optimization

For policy weights b, proposed weights w, and lagged annual covariance S, minimize
`(w-b)' S (w-b)`, subject to full investment and the client bounds. The proportional
baseline uses `clip(k*b, lower, upper)` with k chosen for full investment, under
the same bounds.

The lower-turnover portfolio minimizes `sum(abs(w-current))` subject to the same
bounds and `sqrt((w-b)'S(w-b)) <= minimum_feasible_TE + allowance`. The covariance
uses demeaned returns and no expected-return estimate. A convex solver's status,
bounds, funding and risk budget are checked rather than trusting raw output.
Fixed positions are eliminated from the numerical variables to avoid opposing
active inequalities. CLARABEL first uses 1e-8 solver tolerances and may retry at
1e-7; only an `optimal` status is accepted, followed by independent weight and TE
checks. `optimal_inaccurate` is not accepted. The main-run receipt records retries.

## Funding transaction costs

Let h be pre-trade sleeve values, V their sum, c the cost per dollar traded and w
the proposed weights. Solve for post-cost wealth A:

`A + c * sum(abs(A*w - h)) = V`.

Then the new sleeve values are A*w and the trade values are A*w-h. Sells fund
both buys and costs. There is no external cash injection and no separate
performance subtraction that leaves holdings overfunded. Tests check
`post-trade wealth + costs = pre-trade wealth` and `sells - buys = costs`.

CRSP distributions are reinvested within each total-return sleeve. Fractional
holdings and frictionless distribution reinvestment are assumed; fund expenses
already embedded in returns are not charged again. There are no tax lots, taxes,
share rounding, commission schedules or market-impact models. The cost rate is
an assumption, not observed execution expense. Trade size versus lagged 20-day
CRSP dollar volume is a capacity diagnostic, not a fill guarantee or a hard cap.

## Evaluation

- Gross tracking error isolates exposure differences before each day's trading
  costs; net tracking error also reflects those cost debits. Both annualize the
  sample daily standard deviation by sqrt(252).
- Net CAGR, volatility, drawdown and terminal wealth are simulated account
  outcomes, not evidence that customization generates alpha.
- One-way turnover is half gross traded dollars divided by pre-trade NAV.
- Annualized incurred cost is the sum of actual modeled cost/NAV fractions
  divided by evaluation years. It is not asserted to equal the exact CAGR drag.
- The benchmark is deliberately frictionless to make implementation drag visible.
  Even the unrestricted account pays costs while the benchmark does not.
- First-day returns reflect the initial legacy allocation until the transition
  close. This common implementation effect is retained, not discarded to improve
  the unrestricted comparison.

Report all ten scenarios, all three methods, calendar-year results, and these
pre-specified sensitivities on three illustrative constraints (No gold, Retain
40% US large cap, Domestic and liquid): 252/504-day histories, sample covariance,
0/50-bp TE allowances, and 1/10/25-bp trading costs. Costs trigger complete reruns
because funding affects future holdings and turnover.

Paired circular block bootstrap intervals for the lower-turnover minus minimum-
risk gross-TE difference use 1,000 resamples, 21-trading-day blocks and a fixed
seed. Shared blocks preserve method pairing and short-run serial dependence.
They do not cover model-selection uncertainty, regime shifts or different
universes, and are not used to make multiple-comparison alpha claims.

## Scope

This is a research-grade historical simulation, not a production OMS, approved
investment strategy or actual client record. The fixed ETF universe, fixed
policy weights and hypothetical restrictions are purposeful experimental inputs.
Extending to stock-level direct indexing would require a point-in-time investable
universe, corporate-action and delisting policies, tax-lot rules and an execution
model. Rebranding this ETF experiment as direct indexing would be misleading.

Development used AI coding assistance. The audit trail supports review; it does
not represent independent human authorship or investment-manager validation.
