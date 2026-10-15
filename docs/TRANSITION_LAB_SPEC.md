# Tax-lot transition and operating-controls lab

## Decision and scope

Given explicitly hypothetical long-only accounts, lot-level share quantities and bases, contemporaneous illustrative prices, a strictly prior risk estimate and a target allocation, how much tracking-risk reduction is worth modeled realization taxes and trading costs? Can a separate ledger reject an invalid instruction and recover safely after an interrupted write?

This additive lab does not alter the 2014–2025 WRDS/CRSP study or its 115-control receipt. It is not connected to a broker, real client accounts, actual tax records or a live order workflow. Inputs and outputs are hypothetical; no investment-performance claim is made.

## Bounded optimization

Use the existing CVXPY/CLARABEL stack. Each account has its own cash floor and gross positive-gain tax-reserve budget; accounts cannot fund one another. Lot-level sales are bounded by available shares. Existing positions above target may be sold; positions below target may be bought. Restricted names may only be sold and must be fully exited. This declared direction policy excludes simultaneous buy/sell churn but narrows the feasible search: do not claim unrestricted global tax-optimality.

Minimize annual tracking variance on initial-NAV-normalized dollar positions plus a declared penalty on modeled transaction costs and positive-gain tax reserves. Both purchases and sales incur costs. Reserve positive realized gains at the lot's input rate; do not credit losses, assume loss netting, infer holding-period tax rates, or implement a wash-sale engine. Reserve cash is removed from investable NAV, not represented as an actual paid tax. Basis excludes modeled transaction fees. Fractional shares are allowed; whole-share execution, broker-specific lot selection, market impact, financing and tax advice are outside scope.

The risk matrix is an annualized illustrative PSD covariance. Its timestamp must precede the decision date. Prices must be dated at the decision date. Inputs must have unique account/lot IDs, explicit currency amounts, valid targets/rates and finite numbers. An infeasible cash/restriction/tax combination stops rather than weakening a constraint.

## Independent challenge

The challenger must not call the optimizer's accounting/summary helpers. Reconstruct lot availability, sales proceeds, purchases, costs, positive gains, tax reserves, cash, ending positions and net investable NAV. Check per-account identities, risk/price chronology, directional policy, prohibited positions, post-cost caps, tax budget and cash floor. A plan is bound to the exact source snapshot and policy by hash. A technical PASS permits paper-ledger recording only; it does not authorize trading.

## Operating demonstration

Use a local SQLite journal with atomic commits, optimistic state versions and idempotency keys. Repeated identical events do not apply twice; reuse of an ID with a different payload fails. Stale plans and stale state versions fail. An exception before commit rolls back both the journal entry and state. A reopened database must recover the last committed snapshot. Demonstrate external cash-flow timing and a split preserving position value/basis, with explicit event provenance.

## Evidence required before release

Hand-calculated tax-lot/fee/cash fixtures; a separately calculated optimal or monotonic fixture; stale/future inputs; overselling; tax/cash constraints; no cross-account subsidies; duplicate/conflicting journal IDs; interrupted-write recovery; split/value/basis conservation; cash-flow attribution. Publish all budget-frontier scenarios and named incident outcomes, plus a concise portfolio-manager memo and a responsive interactive evidence exhibit. Keep the original research artifacts byte-identical.
