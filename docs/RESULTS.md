# Current WRDS results: investment interpretation

Source: the September 30, 2026 authenticated CRSP CIZ extract. See the
[data-quality receipt](../outputs/wrds/data_quality.json),
[run receipt](../outputs/wrds/run_summary.json), and
[independent audit](../outputs/wrds/AUDIT.json).

## Main comparison

Across the nine constrained scenarios, minimum-risk optimization has lower
realized gross tracking error than bounded proportional allocation in **9/9**
cases in the 2014?2025 simulation. That is a historical implementation result,
not an alpha claim or a guarantee for another model/universe.

## No-gold account

| Metric | Minimum risk | Lower turnover |
|---|---:|---:|
| Annualized gross tracking error | 1.37% | 1.64% |
| Annualized one-way turnover | 18.23% | 7.25% |
| Annualized incurred trading costs | 1.82 bp | 0.72 bp |

Lower-turnover implementation adds **27.0 bp**
of realized annualized tracking risk while saving about
**1.10 bp of account value per
year** in modeled trading costs, under the 5-bp per-dollar-traded assumption.
That annualized cost difference is roughly $110 per $1 million of NAV; actual
simulated dollar expenses change as portfolio value changes. It is not a claim
about guaranteed execution savings or an exact CAGR difference.

The paired 21-day block interval for that TE difference is
**20.0?35.6 bp** (1,000 resamples). This is a
descriptive interval conditional on this historical sample, not protection
against a different future regime.

## PM judgment

The turnover reduction is large in percentage terms, but its direct trading-cost
benefit is small for this liquid ETF universe. That weakens the case for accepting
extra tracking risk *solely* to save commissions/spread costs. A lower-turnover
rule might still matter for tax lots, illiquid instruments or operational limits,
but those benefits are **not measured here** and should not be asserted.

The natural discussion with a portfolio manager is therefore: which constraints
are economically justified, which risks require explicit client acceptance, and
when is proportional redistribution inadequate? A portfolio optimizer provides a
measurable trade-off; it does not decide the client's utility function.

## What remains outside the experiment

No tax-lot accounting, calibrated price impact, point-in-time stock-selection
universe, live client records, or production order management. Real CRSP returns
strengthen the data foundation; they do not remove the need for those separate
models. All policy weights and client restrictions remain explicit hypotheses.
