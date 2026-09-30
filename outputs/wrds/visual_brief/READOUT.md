# Personalized Model Portfolios: results brief

## Assessment

A substantive portfolio-implementation research project. The strongest result is
that covariance-aware allocation improves benchmark tracking under client
restrictions. The study does not establish an alpha strategy or a tax benefit.

Underlying observations are actual WRDS/CRSP total returns: 32,192 security-days
across eight ETFs, 2010–2025. Evaluation covers 2014–2025, with 30 simulated
portfolio paths, 144 monthly execution dates, and 4,320 allocation decisions.
Policy weights, client restrictions and trading costs are experimental assumptions.

## Findings

1. **Risk-aware allocation reduced realized tracking error in all nine constrained
   scenarios**, versus bounded proportional allocation. Reductions ranged from
   19.75% to 68.86%, with a 35.50% median. This is about tracking-risk control,
   not higher returns. For example, excluding long Treasuries produced 0.31%
   tracking error with minimum-risk allocation versus 0.95% proportionally.
2. **Trading less provided limited direct economic savings in liquid ETFs.**
   In the no-gold account, minimum-risk versus lower-turnover allocation produced
   18.23% versus 7.25% annualized one-way turnover, but gross tracking error rose
   from 1.37% to 1.64%. Costs fell from 1.82 to 0.72 basis points of NAV annually.
   The 1.10 bp annualized cost-rate difference is about $110 per $1 million of
   constant NAV; it is not the actual dollar cost difference of growing accounts.
   Costs assume 5 bp per traded dollar on both buys and sells.
3. **The return winner was not the closest tracker.** In the no-gold example,
   starting with $1 million, ending wealth was $2.26m for minimum risk, $2.42m
   proportional, and $2.46m lower turnover. Their annualized net returns were
   7.03%, 7.66%, and 7.81%. The unrestricted, frictionless policy benchmark,
   which contains 10% gold, reached $2.54m (8.10% annualized). Different exposure
   paths explain this comparison; transaction-cost savings are much too small
   to explain the return spread. This is not alpha attribution.
4. **More risk allowance quickly hit diminishing savings.** Changing the no-gold
   allowance from 25 to 50 bp raised the realized TE increment versus minimum
   risk from 27.0 to 54.0 bp, while annual modeled savings rose from approximately
   $110 to $115 per $1m. All eight sensitivity specifications are displayed.
   At a 25 bp trading-cost assumption, savings were about $549/year per $1m;
   that is a different cost assumption, not an observed execution estimate.

The base no-gold TE increment has a paired 95% block-bootstrap interval of
20.0–35.6 bp (1,000 resamples, 21-day blocks). It is conditional on this sample
and does not capture future regimes or universe-selection uncertainty.

## Portfolio-manager interpretation

Use risk-aware allocation to evaluate the exposure cost of customization. Do not
accept additional tracking risk solely because a turnover percentage looks
dramatically better: price the benefit in account-level dollars. Tax-lot,
illiquidity and operational benefits could change that decision, but none is
measured in this experiment.

## Verification and deliverables

- Original validation receipt: 22 passing tests and 8 executed notebook cells.
- Independent audit rerun September 30: PASS across all 4,320 decisions and
  portfolio accounting reconciliation.
- Chart TE and ending wealth reconciled to saved daily paths.
- Four PNG/SVG charts and the four-page `WRDS_results_visual_brief.pdf`.
- `visual_brief_receipt.json` records source hashes and computed headline values.
- Licensed raw extracts and detailed daily files are not included in this brief.

Presentation-only addition: no research parameters or original calculations were
changed. This is a retrospective fixed-universe ETF simulation, not live client
performance, tax-aware direct indexing, or a production trading system.
