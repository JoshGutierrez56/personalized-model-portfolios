# Decision memo: spend the tax budget only when the risk reduction justifies it

**Evidence:** hypothetical prices, tax lots, input rates and annual covariance; decision date 14 October 2026. No actual accounts, realized performance or live trades. [Interactive evidence](https://joshgutierrez56.github.io/personalized-model-portfolios/transition-lab.html) · [Complete calculations](../outputs/transition_lab/evidence.json)

## Recommendation within the modeled policy

For the **$85,000 legacy-gains account**, a $500 positive-gain reserve budget permits a substantial reduction in tracking risk. The solver selects approximately **247.3177 shares of the high-basis US lot**, not the low-basis lot. It then purchases approximately **317.4085 INTL shares and 151.6548 BOND shares**.

- Illustrative annual tracking risk: **6.37% → 0.33%**.
- Modeled positive-gain tax reserve: **$494.64**.
- Modeled purchase-plus-sale costs: **$27.88**.
- Ending investable cash: **$3,173.34**, above the **$1,000** floor.
- Ending investable NAV: **$84,477.48 = $85,000 − $27.88 − $494.64**.

This is an economically interpretable implementation decision, not a claim of enhanced returns. A larger tax budget is permission, not an instruction to realize more gains: under the fixed risk/cost objective the optimum does not use every additional dollar. Lower budgets retain more embedded gains and more exposure mismatch.

For the **$75,000 cash-first account**, existing cash funds purchases without selling appreciated holdings. Its modeled tax reserve is **zero**, trading costs are **$8.05**, and ending cash is **$3,901.19** against a **$1,500** floor. Illustrative annual tracking risk falls from **4.60% to 0.016%**. Raising its tax budget does not improve the same cash-funded solution. The two accounts never cross-fund.

## Decision criteria and important qualifications

The objective penalizes initial-NAV-normalized tracking variance plus **0.05 × (fees + reserve) / initial NAV**. That coefficient expresses a hypothetical preference, not a calibrated client utility function. Reported post-transition tracking risk uses ending investable NAV, so it is not numerically identical to the objective's variance term.

Input lot rates are assumptions. Positive gains are reserved separately; loss credits, netting, wash sales, account registration rules, actual settlement, fee-adjusted tax basis, and whole-share rounding are not implemented. The direction policy allows sales of initially overweight/restricted names and purchases of initially underweight names. This is a bounded convex problem, not unrestricted global tax optimization.

## Why a reviewer can challenge the result

The independent checker reconstructs lot availability, gross proceeds, purchases, costs, gains, reserves, cash, positions, NAV and risk without importing the optimizer's accounting helpers. It compares against a separately supplied cost policy, not a fee assumption copied out of the submitted plan. Eight deliberately damaged instructions are rejected and the original plan passes a clean retest.

The paper journal then demonstrates a contribution, duplicate retry, interrupted transition, reopening/recovery, second retry and two-for-one split. NAV changes are separated into external flows, fees and modeled reserves. A split preserves position value and total basis. These are executable operating controls, not an operating-history claim.

**Disposition:** suitable for demonstrating a bounded portfolio-implementation decision and its controls. Not authorized or suitable as a production trading instruction without expanding the tax/market model, independently reviewing specifications and integrating real operational controls.
