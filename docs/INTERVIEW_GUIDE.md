# Portfolio Oversight Lab: Interview and Technical Field Guide

**Project:** Personalized Model Portfolios and Independent Portfolio Oversight  
**Prepared for:** Josh Gutierrez  
**Role alignment:** JPMorgan Chase / 55ip, Portfolio Research & Analytics, requisition 210775966  
**Research period:** 2014–2025; current-vintage WRDS/CRSP extract  
**Purpose:** Understand, demonstrate, and defend the actual work—not memorize claims of experience the project does not establish.

## 1. Start here: what this project actually demonstrates

The project asks two connected questions:

1. When a client cannot hold the model portfolio, how should an implementation balance tracking risk, restrictions, and trading?
2. Before a portfolio team relies on that answer, what evidence would establish that the holdings, returns, costs, constraints, and reporting are internally consistent?

The first question produced a walk-forward ETF implementation study. The second produced a separate oversight layer: an independent reconstruction, SQL reconciliations, deliberate fault injection, and a reviewable reporting package. Together, these are stronger than a standalone optimizer or attractive backtest. They demonstrate how a research result becomes a controlled decision aid.

The official posting identifies **Portfolio Research & Analytics Senior Associate** in its title and uses **Vice President** in the body heading. Refer to requisition 210775966 and the team/function if discussing the discrepancy; do not presume a final level. The relevant responsibilities include independent challenge of portfolio positioning, risk and performance; assessment of trade recommendations and constraints; investigation of attribution anomalies; reproducible simulation and stress testing; governance; executive communication; Python/SQL; and project or people leadership.

This project provides direct discussion material for the analytical and control responsibilities. It does not establish that you have supervised employees, owned production investment approvals, operated JIRA in a professional team, or managed live client capital. Acknowledge those boundaries without minimizing the work you can actually explain.

### The positioning sentence

> “My project examines the cost of implementing a model under client restrictions, then independently checks the resulting portfolio records. The main contribution is not a claim of alpha; it is a reproducible way to separate an investment trade-off from an implementation or reporting error.”

### The three things to show

- **A research decision:** the no-gold account's trade-off between tracking risk and turnover, expressed in basis points and dollars.
- **A validation decision:** independent holdings and performance reconstruction, with residuals and release-blocking controls.
- **An operating decision:** an injected incident, its root cause, the affected outputs, the corrective action, and a successful clean rerun.

Study this guide alongside the repository. Before an interview, personally run the available tests, inspect a reconciliation, and explain one deliberately broken example. Familiarity with an AI-assisted artifact is not the same as demonstrated technical ownership.

For an active assessment rather than another reading pass, use the [60-minute interview rehearsal](INTERVIEW_PRACTICE.md). Its questions precede the answer key; it combines hand calculations, actual code navigation, an incident decision, and a scored rubric. Complete it without the answer key before describing yourself as fluent in the implementation.

## 2. Business context: why 55ip should care

A model portfolio expresses desired exposures. An actual account can differ because of restricted securities, minimum retained positions, concentration limits, implementation timing, costs, or other client circumstances. At scale, the problem is not merely finding one mathematically feasible allocation. It is producing a repeatable process for many accounts, knowing when an exception is economically sensible, and detecting when an apparent investment result is actually an operational defect.

For a platform associated with personalized and tax-smart implementation, this study is relevant to the **risk/implementation/control** side of that problem. It deliberately does not implement tax-smart optimization. It contains no cost-basis lots, holding-period rules, wash-sale logic, realized tax accounting, or household-level tax coordination. The right pitch is an adjacent, credible foundation—not “I recreated 55ip.”

An oversight analyst must distinguish at least four situations:

- **Expected customization:** a prohibited exposure forces the account away from the model. The tracking difference is real and intentional.
- **Expected implementation friction:** trading costs lower account NAV while the benchmark remains frictionless.
- **Model limitation:** lagged covariance did not anticipate the next regime. The calculations can be correct while the forecast is weak.
- **Operational error:** duplicate rows, misaligned dates, omitted costs, incorrect weights, or a broken reporting join creates a misleading result.

These require different responses. A valid risk exception goes to an investment decision-maker. A corrupt feed or accounting failure blocks the affected analysis. An inaccurate risk forecast prompts research review. Treating every deviation as a trading instruction is a category error.

### Translate a job responsibility into evidence

| Responsibility | Evidence to open | Defensible claim |
|---|---|---|
| Independently challenge analytics | Independent reconstruction and validation receipt | “There is a second calculation path and explicit comparison tolerances.” |
| Evaluate exposures and restrictions | Scenario results, bounds checks, decision records | “The same restriction is applied across competing methods.” |
| Investigate anomalies | Injected-incident receipt and root-cause narrative | “Known defects must produce the expected blocking controls.” |
| Backtest and simulate reproducibly | Lagged clock, configuration, hashes, tests | “The saved result has a traceable input and code lineage.” |
| Communicate to decision-makers | Workbook, memo, aggregate dashboard | “I translate risk/turnover metrics into a decision and its limits.” |
| Python and SQL | Reconstruction source and DuckDB controls | “SQL checks relational integrity; Python rebuilds the economic path.” |
| Leadership | Your actual employment examples | “This project does not substitute for people-management evidence.” |

## 3. Three demo narratives

These scripts are scaffolds, not claims to recite without understanding. Substitute the actual current validation and incident receipt values after opening the saved run. If a live rerun fails, discuss the failure rather than quoting an older green result as current.

### A 60-second answer: “Tell me about the project”

> “I studied how to implement a multi-asset model when a client has restrictions, using eight ETFs and a lagged monthly simulation over 2014–2025. I compared bounded proportional allocation, minimum tracking risk, and lower turnover within a risk budget. The interesting result was economic: in the no-gold case, turnover fell about 60%, but at the assumed trading cost that saved only about $110 annually per $1 million while adding about 27 basis points of realized tracking risk. I then added an independent oversight layer to rebuild the holdings, costs, NAV, and contributions, check the ledger in SQL, and test whether deliberately injected defects are blocked. It is an AI-assisted research and validation project, not a tax engine or a live trading system. I can show the decision trade-off, the reconciliation evidence, and a root-cause workflow.”

### A three-minute explanation

**First minute—problem and design.** Explain that restrictions change exposures before they change returns. Show the policy weights, one restriction, and the three implementations. State that all methods face the same bounds. The minimum-risk method uses covariance; the proportional method does not. The lower-turnover method is allowed 25 basis points above the minimum feasible **estimated annualized** tracking error. This is not a promise about realized tracking error.

**Second minute—result and judgment.** Open the no-gold comparison. Minimum risk has approximately 1.37% realized gross TE and 18.23% annual one-way turnover. Lower turnover has approximately 1.64% TE and 7.25% turnover. Translate the 1.10-bp annual cost-rate difference to approximately $110 per $1 million of constant NAV. Explain that exposure paths dominate terminal wealth differences. Say, “I would not choose an implementation solely because a relative turnover improvement looks dramatic.”

**Third minute—oversight.** Open the validation summary and one incident. Explain that the checker does not accept the primary simulator's reported NAV as its own starting answer. It propagates sleeve holdings, applies saved trade amounts, recomputes costs, and compares the results. The SQL layer checks keys and joins and reconciles accounting at the appropriate grain. A passing run means the specified checks passed; it does not mean the strategy is suitable, optimal in an investment sense, or approved for production.

### A five-minute screen-share

1. **0:00–0:45, overview.** Open the repository and state the business question. Identify actual historical returns versus hypothetical account rules and costs.
2. **0:45–1:45, investment trade-off.** Open the scenario chart or workbook. Compare the no-gold minimum-risk and lower-turnover methods. Convert the cost-rate change into dollars and distinguish TE from return.
3. **1:45–2:45, reconstruction.** Open the methodology or a clearly labeled synthetic accounting example. Trace opening holdings → asset returns → pretrade NAV → trades/costs → closing NAV. Point out the different prior-NAV and pretrade-NAV denominators.
4. **2:45–3:45, controls.** Open the saved validation receipt. Explain schema, date/key coverage, self-financing, contributions, risk, and SQL controls. The private detailed ledger is not published; public evidence is aggregate or synthetic.
5. **3:45–4:30, incident.** Select a recorded injected defect. State the intended mutation, expected control, observed block, root cause, and clean recovery. Do not describe it as a real customer incident.
6. **4:30–5:00, limits and next step.** State the current-vintage, fixed-universe and no-tax-lot limitations. Name a concrete next step: point-in-time data, robust data contracts, or a separate tax-lot module with independent validation.

**If the interview is nontechnical:** spend more time on the dollar trade-off and incident decision. **If it is technical:** open the reconstruction and ask the interviewer which identity or assumption they would like to challenge. Do not overwhelm a portfolio leader with code before establishing the decision.

## 4. Architecture and data lineage

### The primary research path

- `wrds_data.py` retrieves and validates a bounded licensed CRSP CIZ extract, historical identities, and a reference trading calendar.
- `portfolio_engine.py` defines the hypothetical policy, account bounds, and convex allocation problems.
- `walkforward.py` estimates lagged covariance, computes proposals, executes at the next close, propagates holdings, and records decisions, trades, benchmark values, and daily metrics.
- `run_research.py` runs the baseline and sensitivity studies and writes aggregate results.
- The notebook and visual brief present that research.

### The oversight path

The independent checker reads the saved research records and source returns under their stated contracts. It has its own reconstruction logic, rather than importing the primary engine's accounting functions. It checks the portfolio roster and dates, rebuilds holdings and performance, estimates lagged risk, verifies restrictions, and performs SQL checks. The runner records input provenance and runs deliberate incident cases against copies.

This is **calculation-path independence**, not complete organizational independence. Both paths use the same source data and policy specification. A mistaken assumption shared by both paths can survive. The same Ledoit–Wolf library, authoring process, and AI assistance are also common dependencies. The checker recomputes the TE of the saved Minimum risk allocation; it does not independently prove that allocation's optimizer optimality. A production governance framework would require qualified human review and ownership distinct from the strategy developer; code separation alone does not create it.

### Four evidence layers

1. **Input contract:** identity, calendar coverage, uniqueness, valid returns, flags, and hashes.
2. **Economic identities:** holdings roll forward, buys/sells/costs fund, NAV reconciles, and contributions sum to returns.
3. **Analytical policy:** lagged windows, covariance, TE budgets, restrictions, and monitored drift.
4. **Presentation lineage:** the published chart, workbook, or memo agrees with aggregate source artifacts and labels synthetic illustrations as synthetic.

A chart is the last layer, not the first. A visually plausible result cannot establish input correctness. Conversely, a floating-point residual at a documented tolerance is not automatically an economic problem.

### What a hash does and does not prove

A SHA-256 hash fingerprints exact file bytes. It helps identify which input or code version produced a receipt and detects later changes. It does not establish that the data are economically correct, that the code is unbiased, that the retrieval was authorized, or that the analyst has redistribution rights. Hashes complement validation; they do not replace it.

For cross-platform source-code contract pins, this project normalizes text line endings to LF before hashing. Windows CRLF versus Unix LF alone should not invalidate that semantic source pin. Raw data hashes and the run receipt's actual file hashes retain byte-level identity. Distinguish these two policies when comparing hashes; a normalized source fingerprint is not a claim that physical file bytes are identical.

## 5. Holdings, costs, and NAV: the calculation to master

The simulator uses **total-return sleeve dollars**, not an actual share and tax-lot ledger. Let opening holdings for asset i be `h[i]`, the asset's close-to-close total return be `r[i]`, and opening account NAV be `V0 = sum(h)`.

Before any closing trade:

```text
pretrade_h[i] = h[i] × (1 + r[i])
Vpre = sum(pretrade_h)
gross_return = Vpre / V0 − 1
```

At a rebalance, the desired weights refer to **post-cost** NAV `A`. With cost rate `c` per dollar bought or sold:

```text
trade[i] = A × target_weight[i] − pretrade_h[i]
fee = c × sum(abs(trade[i]))
A + fee = Vpre
```

This is solved rather than pretending every pretrade dollar remains invested while also deducting a performance fee. The primary engine uses a monotone root solve. The independent checker uses the saved trades, recomputes their costs, reconstructs posttrade holdings, and challenges the saved outputs.

The key identities are:

```text
posttrade_h[i] = pretrade_h[i] + trade[i]
sum(posttrade_h) + fee = Vpre
sum(trade) + fee = 0
net_return = sum(posttrade_h) / V0 − 1
gross_return − net_return = fee / V0
```

Selling funds both purchases and fees. There is no external cash injection. On a nonrebalance date, trade amounts and costs are zero, and holdings simply drift with the asset returns.

### Worked example: two assets, one closing rebalance

This is a deliberately simple synthetic example, not a CRSP observation or a claimed investment result.

- Opening holdings: asset A $600, asset B $400; NAV $1,000.
- Returns: A +10%, B −5%.
- Pretrade holdings: $660 and $380; NAV $1,040.
- Desired closing weights: 50%/50%.
- Cost: 10 bp per traded dollar, or `c = 0.001`.

The post-cost NAV must satisfy:

```text
A + 0.001 × (abs(A/2 − 660) + abs(A/2 − 380)) = 1,040
```

In this example, the final half-NAV lies between $380 and $660, so gross trading equals $280. Cost is $0.28 and post-cost NAV is **$1,039.72**. Each sleeve ends at **$519.86**.

- Sell asset A: $140.14.
- Buy asset B: $139.86.
- Difference: $0.28, exactly funding the cost.
- Gross return: 4.000%.
- Cost contribution to return: `−0.28 / 1,000 = −0.028%`, or −2.8 bp.
- Net return: **3.972%**.
- Cost/pretrade NAV diagnostic: `0.28 / 1,040`, or approximately **2.6923 bp**.
- One-way turnover: `280 / (2 × 1,040)`, or approximately **13.4615%**.

**The interview trap:** cost divided by pretrade NAV is useful for a trading-cost-rate diagnostic, but it is not the exact subtraction from the day's return. The exact return contribution uses **opening/prior NAV**. This distinction matters even though the numerical difference is often small.

### Why not subtract costs twice?

The closing NAV already includes the fee through smaller funded holdings. Net return is closing NAV divided by opening NAV minus one. Subtracting the fee again from that return would double count it. Similarly, fund expenses embedded in the source total returns are not charged a second time as an extra management expense in the model.

### Why the first day matters

Each account starts with the same legacy allocation, not the model allocation. On the first execution date, that legacy portfolio earns the close-to-close return before the transition trade. Even the unrestricted account therefore has a small gross tracking difference during transition. Keeping that day is more faithful to the stated implementation than deleting it to make a control look perfect.

## 6. Total returns, distributions, and benchmark accounting

The study uses CRSP CIZ `dlyret`, a total-return field, rather than a simple percentage price change. A price-only return omits distributions. An ex-distribution return is not interchangeable with a total return.

For a simple illustration, suppose an instrument begins at $100, ends at $99, and pays a $2 distribution. A naive price return is −1%. Ignoring timing complications, the total economic return is approximately +1%. If you use a total-return series and also add the $2 cash distribution, you count it twice. The precise vendor convention must govern the implementation; do not reconstruct a field casually from a mental formula.

In this model distributions are reinvested within each sleeve. That abstraction is suitable for an exposure study but differs from actual distribution cash flows, withholding, reinvestment dates, fractional-share rules, and settlement. Those would need explicit modeling for an operational account ledger.

CRSP CIZ total returns already incorporate its relevant distribution/delisting treatment. The pipeline does not attach legacy delisting returns again. The fixed-universe workflow stops on a delisting requiring an unimplemented liquidation or replacement policy rather than silently dropping the security.

### Benchmark construction

The policy benchmark begins at the target allocation, earns the same total-return inputs, drifts between rebalances, and resets to policy weights at the same monthly execution closes. It is frictionless. The account pays modeled costs.

That asymmetric cost treatment is intentional: it makes implementation drag visible. It is not a claim that a real benchmark investor can trade for free. An alternative comparison could charge a consistent execution model to both portfolios, but it would answer a different implementation question and should be labeled accordingly.

SHY is not a bank balance or risk-free cash account. It is an ETF with market returns, duration exposure, and embedded fund costs. Calling a SHY floor a “cash allocation” without qualification would misstate the model.

## 7. Contributions, attribution, and geometric linking

### Daily arithmetic contributions

For opening asset weights `w[i]`, the day's gross asset contribution is:

```text
asset_contribution[i] = w[i] × asset_return[i]
sum(asset_contribution) = gross_portfolio_return
cost_contribution = −fee / opening_NAV
sum(asset_contribution) + cost_contribution = net_portfolio_return
```

The benchmark has its own **actual opening weights**, including interim drift. Subtract its asset contributions from the account's asset contributions and add the account's negative cost contribution. The sum equals that day's net arithmetic active return:

```text
net_active_return = net_portfolio_return − benchmark_return
```

Do not substitute target weights for opening weights on every date. That would describe a daily-rebalanced portfolio, not the monthly-drifting portfolio that actually generated the record.

### Why daily contributions cannot simply be added over years

A portfolio earning +10% and then −10% has a cumulative return of −1%, not zero. Arithmetic addition misses compounding. Even the sum of daily active returns need not equal the difference in cumulative portfolio and benchmark returns.

The oversight layer uses a transparent **initial-capital/wealth-scaled P&L decomposition**. Each asset's daily dollar P&L is opening sleeve value times its return. Add those dollar P&Ls over time and divide by the common initial NAV. Subtract cumulative modeled cost dollars divided by initial NAV. The contributions sum to the account's cumulative net return.

Equivalently, multiply each daily return contribution by `prior_account_NAV / initial_NAV` before summing. Perform the benchmark calculation with its **own** prior NAV. Then subtract the two sets of linked asset contributions and include the account's cost component:

```text
linked_asset_active[i]
  = sum(account_opening_h[i,t] × r[i,t]) / initial_NAV
  − sum(benchmark_opening_h[i,t] × r[i,t]) / initial_NAV

linked_cost = −sum(account_fee[t]) / initial_NAV

sum(linked_asset_active) + linked_cost
  = account_terminal_NAV / initial_NAV
  − benchmark_terminal_NAV / initial_NAV
```

This telescopes through the self-financing holdings identity. It requires no external contributions or withdrawals; cash flows would require a different treatment. It is one explicit, economically interpretable linking convention, not the unique possible attribution convention.

### A two-day linking check

For a $100 account with +10% and −10%, the first day's dollar gain is $10. The second day's opening value is $110, so the loss is $11. Summing dollar P&L gives −$1; dividing by initial $100 gives −1%.

A benchmark with +5% and −5% ends at $99.75. Its linked return is −0.25%, so the cumulative return difference is **−0.75 percentage points**. Daily arithmetic active returns are +5% and −5%, whose sum is zero. The difference demonstrates why a daily reconciliation and a multiperiod reconciliation are separate controls.

### What this attribution does not claim

It is not Brinson allocation/selection attribution, factor attribution, security-selection alpha, or tax attribution. It separates asset-sleeve P&L and modeled cost effects under a stated accounting convention.

The cumulative cost contribution is not the entire terminal-value impact of trading expenses versus a separately simulated zero-cost counterfactual. Costs also alter future invested capital and therefore future sleeve P&L. A zero-cost counterfactual must be rerun with its own evolving holdings; subtracting cumulative fees alone does not produce it.

## 8. Risk, turnover, and optimization: know the units

### Ex-ante tracking error

Let `a = w − b`, where `w` is the proposed account allocation and `b` is the policy allocation. For annual covariance `S`, estimated tracking error is:

```text
TE = sqrt(a' × S × a)
```

The covariance is estimated from the prior 756 trading observations, using Ledoit–Wolf shrinkage in the baseline, and multiplied by 252. The square root is already an annualized volatility measure; do not annualize it a second time.

Why covariance? If two sleeves are highly correlated, substituting one for another may preserve model exposure better than distributing the prohibited weight proportionally across unrelated assets. Correlation estimates are uncertain, however. They are a risk-model input, not a guarantee.

Ledoit–Wolf shrinks the empirical covariance toward a structured target, improving conditioning and reducing sampling noise. It does not cure nonstationarity, missing factors, stale prices, vendor errors, or hindsight in universe selection. There is no expected-return estimate in this optimizer, so describing it as a Sharpe-ratio optimization would be wrong.

### Realized tracking error

The realized statistic is the sample standard deviation of daily active returns, multiplied by `sqrt(252)`. Gross active returns isolate exposure variation before that day's cost; net active returns include cost debits.

TE measures variability around mean active return. A constant daily underperformance can have zero TE while still producing a substantial cumulative wealth shortfall. Conversely, lower TE does not imply higher return, a smaller terminal wealth gap, or better suitability for every client.

The usual square-root annualization assumes a conventional daily scaling. It is not a forecast interval or a proof that serial correlation is absent. The study also uses paired circular block resampling to describe uncertainty in one TE difference conditional on the sample.

### Compare like with like: proposed risk versus realized benchmark risk

The ex-ante calculation compares a **proposed allocation with fixed policy weights** using the lagged covariance. The realized calculation compares a **time series of earned account returns with an actually drifting monthly benchmark**. Execution-close weights, interim drift, changing covariance estimates, the legacy first-day allocation, and realized future returns all affect the relationship. They are not the same object measured twice. A 25-bp allowance at proposal time is therefore not a promise that the two full-history realized TE estimates will differ by no more than 25 bp.

If a PM asks why realized TE rose, first reconcile the accounting and benchmark. Then separate forecast error, changing exposures, and implementation effects before proposing a new risk model. The saved study compares these quantities; it does not implement a formal out-of-sample calibration test of predicted versus realized TE.

### The lower-turnover optimization

It minimizes the L1 distance between proposed weights and signal-date weights subject to the same restrictions and a risk budget:

```text
estimated_TE ≤ minimum_feasible_estimated_TE + 0.0025
```

The allowance is **25 basis points of annualized volatility**, not a 25% relative increase, not 25 basis points of variance, and not a limit on annual underperformance. Realized TE can exceed the estimated budget because future returns differ from the estimated covariance.

The optimized trading proxy uses signal-date weights; actual closing trades occur after the execution day's return. This means realized trade dollars need not exactly equal the signal-date objective. The model assumes fractional closing-price allocation, not guaranteed fills of fixed advance share quantities.

### Turnover and cost units

One-way turnover is half gross traded dollars divided by pretrade NAV. The cost assumption applies to **both** buys and sells. Therefore 10% one-way turnover corresponds to approximately 20% gross trading and, at 5 bp per gross traded dollar, approximately 1 bp of account-level cost for that period.

“Turnover fell by 60%” is a relative statement. It is not a 60-percentage-point reduction and does not tell you the dollar benefit without the starting turnover, traded-dollar cost, NAV, and horizon.

### Constraint policy and drift

Bounds are checked at execution closes. Between rebalances, market moves can cause a cap or floor to drift. The project reports that drift; it does not silently rebalance every day to eliminate it. A zero position remains zero absent a trade, but a positive exposure cap can drift upward.

A minimum weight is not a no-sale rule, a specified lot-retention rule, or a tax restriction. Holding at least 40% in SPY permits transactions as long as the final weight meets that floor. In a real mandate, the policy language must be translated precisely before testing compliance.

## 9. SQL controls: grain before formulas

The independent Python reconstruction checks the evolving economic state. The SQL layer answers complementary questions about saved records and joins. It is not merely a second language for repeating a displayed percentage.

### Know the grain of each input

- Daily performance: one row per **date × client scenario × method**.
- Decisions: one row per **execution date × client scenario × method**.
- Trade ledger: one row per **date × client scenario × method × ticker** on rebalance dates.
- Benchmark: one row per **date**.
- Return panel: one value per **date × ticker**.

Names are part of keys here because the scenario roster is controlled. A production system would normally use stable identifiers and effective-dated reference data rather than free-text account names.

### Three common traps

**Duplicate amplification.** If a benchmark date appears twice, joining it to daily accounts doubles rows and can inflate sums. Check uniqueness before joining and compare expected and actual postjoin cardinality.

**Missing-row concealment.** An inner join can remove an unmatched account/date, leaving a perfectly reconciling subset. Perform anti-joins or coverage checks and compare complete key sets, not just totals of matched records.

**Mixed-grain sums.** Joining one daily cost to eight trade rows and summing the daily cost produces an eightfold overstatement. Aggregate trade rows to account/date/method before joining to daily results, or explicitly preserve one-to-many semantics.

### Explain a representative reconciliation

At the trade grain, verify `posttrade_dollars − pretrade_dollars = trade_dollars` and recompute each cost as `abs(trade_dollars) × cost_rate`. Aggregate by date/client/method. Then compare aggregate cost and posttrade NAV with the daily record and verify `sum(trade_dollars) + sum(cost_dollars) = 0`.

SQL arithmetic can all pass on a consistently corrupted ledger. That is why source-driven holdings reconstruction matters: it challenges saved values using prior economic state and returns. The two layers have different failure surfaces.

### NULLs, types, and dates

Missing is not zero. `SUM` often ignores NULLs, so a NULL check must precede arithmetic aggregation. NaN or infinity needs explicit finite-value treatment. Dates must be parsed consistently and ordered; strings that happen to sort lexicographically are not a reliable chronology contract. A numeric type conversion that silently creates missing values is a data-quality incident, not a formatting nuisance.

## 10. Incident lifecycle: detection is not enough

The incident harness mutates copies of clean saved records and checks whether specified controls block the altered run. These are **deliberately injected defects**, not defects discovered in client accounts. The implemented suite contains five cases: ex-distribution returns substituted for total returns; a duplicate trade row; a same-day signal timestamp; a 1-percentage-point prohibited GLD allocation; and a $100 recorded-fee error. Detection outcomes belong in the generated incident receipt; do not invent them or confuse them with the original research's 22-test historical receipt.

The wrong-return case holds the saved trade ledger fixed. It measures disagreement with the original total-return accounting, not the performance of a self-consistent alternative strategy. Its blocked outputs are diagnostic, not valid investment results. A successful case requires an expected domain-specific control to fail, not merely any exception or generic block. “Corrected retest” means rerunning the unchanged original input after in-memory mutations; it is not a claim that production records were repaired.

### The operating sequence

1. **Detect.** A concrete control fails: duplicate key, date mismatch, funding residual, NAV disagreement, contribution residual, or risk inconsistency.
2. **Contain.** Do not release the affected report or infer a trading action from unreliable output. Preserve the input and receipt for diagnosis.
3. **Scope.** Identify affected dates, scenarios, methods, and dependent aggregate reports. Distinguish one corrupt field from a systemic source failure.
4. **Diagnose.** Trace backward from the failed identity to the earliest divergent layer. Determine whether the cause is data, transformation, model specification, timing, or presentation.
5. **Correct.** Repair the cause, not merely the reported total. Do not “fix” a balance by inserting a compensating unexplained cash flow.
6. **Retest.** Demonstrate that the dirty case is caught, the clean case passes, and related identities still reconcile.
7. **Prevent.** Add a durable ingestion, key, denominator, schema, or lineage control and document the owner and release criterion.
8. **Close.** Record actual impact, action, and evidence. A green rerun is necessary but not sufficient if the root cause is still unknown.

### Example A: cost was recorded but not funded

**Symptom:** the daily record deducts a fee, but closing sleeve values still sum to the full pretrade NAV. **Impact:** future invested capital is overstated and net-return accounting can disagree with actual holdings. **Root cause:** performance and holdings paths applied different cost conventions. **Correction:** fund costs through smaller closing holdings and reconcile the funding identity. **Prevention:** require both `closing_NAV + fee = pretrade_NAV` and `sells − buys = fee` before release.

### Example B: duplicate record in a reporting join

**Symptom:** an aggregate cost or return appears inflated only after a join. **Impact:** portfolio decisions could be based on false implementation drag. **Root cause:** a supposedly unique table is not unique at the intended key, or the query combines different grains. **Correction:** fix the source/key relationship or aggregate correctly; do not hide duplicate rows with an unexplained `DISTINCT`. **Prevention:** uniqueness, anti-join and cardinality controls with explicit expected grains.

### Example C: execution-day information entered the risk estimate

**Symptom:** a history window ends on or after execution, or an independently recomputed TE differs. **Impact:** the backtest claims information unavailable when the decision should have been made. **Root cause:** an inclusive slice or date-index alignment error. **Correction:** end the training window at the prior close and rerun affected decisions and downstream paths. **Prevention:** verify both the date ordering and the exact training-window membership, not just a metadata label.

These examples explain failure mechanisms. In a live demo, use the actual cases and control identifiers written by the implemented incident harness, not these examples as a substitute for evidence.

## 11. What the research actually found

The saved baseline studies 10 hypothetical account scenarios and three methods, creating 30 portfolio paths. There are 144 monthly execution dates and 4,320 allocation decisions over 2014–2025. The source sample contains 32,192 security-day records: eight ETFs across 4,024 trading dates from 2010–2025. The earlier research receipt documents 22 tests and eight executed notebook code cells; the new oversight suite has its own current receipt.

The independent baseline reconstructs **90,540 account/method/date records** and checks **34,560 trade rows**. Its saved maximum cumulative-active-linking residual is approximately **4.47 × 10⁻¹⁴** in decimal return, against a **1 × 10⁻¹⁰** tolerance. This is a numerical reconciliation result, not an estimate of investment risk or financial significance. Open the current receipt for the complete control count and the incident receipt for final fault-detection and clean-retest outcomes.

Across all nine constrained scenarios, minimum tracking risk reduced realized gross TE relative to bounded proportional allocation by **19.75–68.86%**, with a **35.50% median reduction**. The unrestricted case is a control, not a tenth constrained comparison.

### The no-gold decision

| Metric | Minimum risk | Lower turnover |
|---|---:|---:|
| Realized annualized gross TE | 1.37% | 1.64% |
| Annualized one-way turnover | 18.23% | 7.25% |
| Annualized modeled trading cost | 1.82 bp | 0.72 bp |
| Total simulated trading expenses | $3,009.62 | $1,281.23 |
| Net annualized return | 7.03% | 7.81% |
| Terminal value from $1 million | $2.26 million | $2.46 million |

The roughly 60.26% turnover reduction comes with **26.99 bp** more realized tracking risk. The annual cost-rate difference is approximately **1.10 bp**, or **$110 per year on a constant $1 million NAV**. That is a scale illustration, not an exact annual invoice or CAGR benefit. Actual cost dollars depend on the evolving simulated account.

The reported annualized cost rate is the sum of individual cost/pretrade-NAV fractions divided by the study's year convention, `evaluation_sessions / 252`. It is not total dollar costs divided by initial wealth and elapsed years. That distinction explains why multiplying the illustrative $110 by twelve does not reproduce the difference between the two total-expense figures. Do not conflate an annualized fraction, an actual dollar sum, and a change in compound annual return.

The paired 21-day circular block bootstrap gives an approximately **20.0–35.6 bp** interval for the TE increment at the stated 95% level and 1,000 resamples. The procedure preserves contemporaneous pairing between methods and some temporal dependence. It does not represent all possible regimes, model choices, or future market histories.

Increasing the risk allowance to 50 bp approximately doubled the realized extra TE to 54 bp while increasing modeled annual savings only to roughly $115 per $1 million. This makes diminishing cost savings visible. A higher assumed per-trade cost changes the economics, but it is another modeled assumption, not observed market impact.

### The recommendation you can defend

> “Use the model to quantify the exposure cost of a restriction. Do not spend tracking risk just to achieve an impressive percentage reduction in turnover without pricing the benefit. In this liquid-ETF example, direct modeled cost savings are small. A tax-lot model, illiquid instrument, minimum trade size, or operational constraint could change the choice, but this experiment does not measure those benefits.”

Do not turn that into “always choose minimum risk.” The client may value nontrading benefits that are absent here. Conversely, do not select lower turnover because it happened to end with higher wealth: the optimizer did not forecast the return path, and the observed ordering is not established alpha.

## 12. Limits and a credible production roadmap

### Limits to say clearly

- **Retrospective history:** the 2014–2025 period has been inspected during project development. It is not a never-seen prospective holdout or a preregistered experiment.
- **Current-vintage source:** lagging returns addresses chronology within the extract, not subsequent data revisions. There is no archive of what CRSP knew on each historical day.
- **Fixed, retrospectively selected universe:** historical identity resolution reduces ticker confusion; it does not remove selection or survivorship concerns.
- **ETF sleeves, not direct indexing:** there are no stock-level point-in-time eligibility rules or corporate-action workflows for a broad constituent universe.
- **No tax engine:** no lots, wash sales, realized-gain budgets, tax rates, or household coordination.
- **Simplified execution:** fractional closing allocations and a fixed bps cost, without calibrated spread, impact, fill uncertainty, settlement, or order-routing behavior.
- **No client cash flows:** external contributions, withdrawals and money-weighted/time-weighted performance treatment are outside this path model.
- **Research controls, not operational approval:** no live OMS, deployment signoff, service-level agreement, or institutional model-risk validation is established.
- **Licensed data:** raw CRSP rows and detailed paths derived from them stay local; public code and aggregates are not a redistribution license for the source feed.

### Prioritize the roadmap

**First, harden the existing scope.** Stable identifiers; versioned schemas; source-calendar contracts; immutable receipts; explicit report-release states; reviewed tolerances; designated owners; and reproducible environments. Expand failure cases according to real failure risk, not to make a test count larger.

**Second, improve the research question.** Broaden sensitivity to execution assumptions and risk-model choices, evaluate regime behavior, and define a genuinely prospective monitoring period. Keep a record of which decisions were made before versus after seeing that period.

**Third, add tax-aware implementation as a separate module.** Introduce an explicit lot ledger, realistic tax policy, household restrictions, and independent tax/accounting tests. Define whether the objective concerns after-tax wealth, realized-gain budgets, tracking risk, or a combination. Do not attach a “tax aware” label to a turnover penalty.

**Fourth, integrate operationally only with governance.** Approval rights, exceptions, audit retention, deployment controls, execution systems, capacity, security, and qualified review are separate deliverables. A correct research notebook is a useful input—not the production system itself.

### Role-specific extension: from ETF weights to factor, sector, and country risk

The posting asks about factor/sector/country/style exposures. This project currently reconciles **ETF sleeve weights and return-covariance risk**, not a vendor factor model or historical constituent look-through. A US-listed ETF is not automatically a US-only economic exposure, and assigning one sector label to a broad equity ETF would be misleading.

A credible extension would obtain effective-dated holdings or factor loadings, align their availability to each signal date, and document coverage and stale/missing exposures. With security-by-factor exposures `B`, factor covariance `F`, specific covariance `D`, and active security weights `a`, a conventional model decomposes active variance as `a' B F B' a + a' D a`. Specific risk cannot be omitted merely because factor exposures reconcile. Country and sector mappings also need explicit classification rules and an unknown bucket rather than silently redistributing missing coverage.

The acceptance criterion is not an attractive exposure chart. Require point-in-time availability, reconciled holdings coverage, units and currency conventions, factor-plus-specific variance reconciliation to total modeled variance, and a controlled response when coverage is inadequate. Present this as a design proposal unless you have actually implemented and tested it; do not imply Bloomberg, FactSet, or Barra integration exists here.

### Role-specific extension: a change ticket a PM could review

For a hypothetical proposal to shorten the risk lookback from 756 to 252 sessions, record: **question**—does faster adaptation justify increased estimate noise; **scope**—same universe, clock, restrictions and cost model; **evidence**—paired exposure, TE, turnover, feasibility and regime comparisons; **acceptance**—accounting stays reconciled, no chronology breach, changes are explained rather than selected solely for higher returns; **decision owner**—a designated PM/research reviewer; and **rollback**—retain the previous configuration and its immutable outputs.

This is a proposed work item suitable for a JIRA-style workflow, not a claim that this repository is integrated with JIRA or that a committee approved a model change. The hypothesis and acceptance criteria should be written before inspecting a new genuinely prospective period. Previously inspected history remains development evidence even when rerun under a new ticket.

## 13. Ownership, AI assistance, and interview honesty

The existing research and this extension used AI coding assistance. A credible ownership statement is:

> “I developed this as an AI-assisted research project. The repository separates the specification, code, independent checks, and outputs so I can inspect and explain the assumptions. I would not present the generated code or a passing test suite as a substitute for my own review or an institutional validator.”

Adjust “developed” to accurately reflect what you personally did. If you have not personally written or reviewed a module, say so. You can discuss why its design matters, then demonstrate that you understand it. Do not claim “I coded every line,” “I independently audited my employer's portfolios,” or “I managed the engineering team” based on agent-assisted project work.

### Before claiming mastery, personally complete this checklist

- Explain the two-asset example without the guide.
- Locate the source code implementing the decision clock and the checker verifying it.
- Reconcile a synthetic trade by hand and identify the correct denominator.
- Run the tests available without licensed data and inspect their output.
- If locally entitled to the data, run the oversight pipeline and inspect the receipts.
- Explain one failed case and why changing a displayed number would not fix its cause.
- Name three shared assumptions that both primary and validator could get wrong.
- Distinguish this project from your actual employment responsibilities and management experience.

### If asked about leadership

Use a real work example where you coordinated people, resolved disagreement, improved a process, or communicated an error. The project can illustrate how you would structure ownership: analyst prepares evidence, reviewer challenges it, designated decision-maker approves exceptions, and a tracked issue owns remediation. That is a governance proposal, not proof you have already managed that organization.

## 14. Technical mock interview: questions and strong answers

### “Why build an independent validator instead of more unit tests?”

“Unit tests can check local functions but still share the same assumptions or miss interactions across saved artifacts. The independent reconstruction starts from source returns, prior holdings, and saved trades, then challenges reported NAV and contributions. SQL tests keys and joins. The methods complement each other. The validator still shares source and policy assumptions, so I do not call it complete institutional independence.”

### “Why trust a validator written with the same AI assistance?”

“I do not infer correctness from who or what wrote it. I look for a different calculation path, transparent identities, deliberate known faults, tests with hand-checkable examples, and human review. Common-mode specification risk remains, which is an explicit limitation and a reason for external review before operational use.”

### “Why use Ledoit–Wolf for eight ETFs?”

“It is a reproducible regularized covariance estimator with good numerical conditioning, rather than an unexamined raw sample matrix. Eight assets and a long window reduce some dimensionality concerns, but correlations can still be unstable. I include sample-covariance and shorter-window sensitivities instead of treating shrinkage as proof of superior forecasting.”

### “How do you prevent look-ahead?”

“The proposal uses a window ending at the signal close. The next close-to-close return is earned by old positions, and the proposal executes at that next close. The checker verifies chronology and independently rebuilds risk estimates. This prevents return look-ahead within the data, but it does not make the current-vintage source point-in-time or erase hindsight in universe selection.”

### “Your optimizer says optimal. What else is there to check?”

“Optimal means a numerical solver satisfied its conditions for the supplied mathematical problem within tolerances. I still check finiteness, bounds, full investment, TE budget, funded trades, and realized accounting. It says nothing by itself about whether the objective, risk model, cost assumption, or client policy is appropriate.”

### “What if the constraints make the problem infeasible?”

“Fail explicitly and show the conflicting bounds. I would not silently relax a client restriction or normalize an invalid solution. In production, an authorized policy owner would decide whether the request changes; the analyst should preserve the failed case and the proposed resolution.”

### “What is the difference between an active return and TE?”

“Active return is the portfolio return minus benchmark return for a period. TE is the standard deviation of that series, conventionally annualized. TE does not tell us the mean active return or cumulative wealth shortfall, so I report those separately and avoid calling lower TE outperformance.”

### “How can a 60% turnover reduction save only $110?”

“The starting turnover is not enormous, the instruments are liquid ETFs, and the assumed cost is 5 bp per dollar traded. The change from about 18.23% to 7.25% annual one-way turnover implies about 21.96 percentage points less gross trading. Multiplying by 5 bp yields roughly 1.10 bp of account-level annual cost rate, or $110 on a constant $1 million.”

### “Where do transaction costs show up in attribution?”

“They are a separate negative daily contribution, fee divided by prior NAV. Sleeve contributions sum to gross return; adding cost reconciles to net return. Across time, dollar P&L and fees scaled by initial capital reconcile to terminal wealth. That fee term is not the complete zero-cost counterfactual effect because costs alter future capital.”

### “Why not just sum daily active contributions?”

“Because compounding changes the capital base. A +10%, −10% sequence is −1%, not zero. I link dollar P&L using each portfolio's evolving wealth and common initial capital, then reconcile to the difference in cumulative returns. The convention is explicit and is not Brinson or factor attribution.”

### “How would you diagnose a performance break?”

“First determine whether it is a data/control failure or a genuine exposure outcome. Check dates and keys, then holdings/returns/costs, then benchmark alignment and linking. Identify the earliest divergence and its affected outputs. Contain the release, repair the cause, retest the bad and clean cases, and add a durable prevention control.”

### “Why is a SQL join dangerous if all the formulas are right?”

“The formulas apply to a grain. A duplicate benchmark key or a one-to-many trade join can multiply a correct daily value. An inner join can also conceal missing rows. I check unique keys and complete coverage before arithmetic and verify cardinality after joining.”

### “Is the lower-turnover portfolio tax optimized?”

“No. Turnover is not realized taxable gain. Without cost basis, lots, tax rates, holding periods, wash-sale rules, and household policy, I cannot measure tax outcomes. This is a controlled implementation study that could support a separately specified tax module.”

### “What would make you reject your own result?”

“A broken source contract, look-ahead, inconsistent cash funding, attribution that fails to reconcile, or a materially changed result under plausible assumptions without an explanation. I would also reject an interpretation that the code does not support, such as alpha, future performance, or measured tax savings.”

### “What did the project change about your judgment?”

“It made me price operational metrics in economic units. A large relative turnover improvement can have a small direct dollar value. I would discuss the cost/risk frontier and any unmodeled client benefit, rather than treating lower turnover or a more complex optimizer as automatically better.”

## 15. Behavioral mock interview: use the project without inventing a history

### “Tell me about a time you challenged an attractive result.”

Project-based answer: “The lower-turnover method looked compelling on a relative percentage basis. I translated the improvement into costs per $1 million and compared it with added TE. The direct cost benefit was small at the stated assumption. The conclusion became a conditional trade-off rather than a blanket recommendation.” Describe your personal review work precisely; do not imply this happened at an employer if it did not.

### “How do you communicate a technical failure to a senior stakeholder?”

“I lead with the decision impact: what output is unreliable, what is paused, what is still usable, and when the next evidence-based update will occur. Then I give the failure category, scope, and owner. I keep detailed reconciliation evidence available without burying the message in stack traces.”

### “How would you handle disagreement with a portfolio manager?”

“Separate factual reconciliation from investment judgment. An accounting identity must reconcile; an investment preference can be debated. Present the exposure and cost trade-off, acknowledge omitted benefits, document the decision owner, and escalate only the actual unresolved policy or control issue.” Use an actual prior-work example if asked for a past event.

### “How do you balance speed and rigor?”

“Define a narrow scope and minimum release criteria early. Automate repeatable checks, use hand-checkable examples for core accounting, and label uncertain assumptions. Time pressure can reduce the scope of a claim; it should not convert a failed reconciliation into an acceptable result.”

### “Why are you a fit for this role?”

“My evidence for this role is the combination of portfolio reasoning, reproducible Python/SQL analysis, controls, and communication. This project lets me walk from source data through a portfolio decision and into an oversight finding. For responsibilities such as people management or specific production systems, I would draw on my actual work history rather than claim the project proves them.”

## 16. Hard traps: statements to avoid

| Tempting statement | More accurate statement |
|---|---|
| “I built 55ip.” | “I built a focused ETF implementation and oversight prototype relevant to parts of the role.” |
| “This is a tax-loss-harvesting engine.” | “There is no tax-lot or tax-outcome model.” |
| “No look-ahead means unbiased.” | “The decision clock is lagged; vintage and selection limitations remain.” |
| “Lower TE means better returns.” | “Lower TE means less variable active return.” |
| “The strategy saved $110 every year.” | “The modeled annual cost-rate difference scales to about $110 per constant $1 million.” |
| “The TE budget guarantees future TE.” | “It constrains estimated risk using the lagged covariance.” |
| “The validator proves the model is right.” | “Specified controls passed on identified inputs.” |
| “The injected incident was a client loss.” | “It was a deliberate mutation used to test detection.” |
| “A cost contribution is full cost impact.” | “It is an accounting component; the full counterfactual needs a rerun.” |
| “Everything is public and reproducible without access.” | “Public code and aggregates are reviewable; licensed-data reruns require entitlement.” |
| “I managed the agents, so I managed a team.” | “AI-assisted project work is not people-management experience.” |

## 17. Study drills with answer key

### Drill 1: turnover economics

An account has 12% one-way turnover, a 5-bp charge per traded dollar, and $2 million of constant NAV. Approximate period trading cost?

**Answer:** gross trading is 24% of NAV. Cost rate is `0.24 × 0.0005 = 0.00012`, or 1.2 bp. The constant-NAV dollar illustration is **$240**. Use the actual funded ledger for exact simulated cost.

### Drill 2: annualization

Daily active-return sample standard deviation is 0.10%. Annualized TE?

**Answer:** `0.10% × sqrt(252) ≈ 1.587%`. Do not multiply volatility by 252. If covariance was already annualized, do not multiply the resulting TE again.

### Drill 3: constant underperformance

The portfolio underperforms by exactly 1 bp each trading day. Is TE necessarily large?

**Answer:** the arithmetic active-return series is constant, so its standard deviation is zero. The mean active return is negative and cumulative underperformance can be substantial. TE is not a complete measure of benchmark-relative outcome.

### Drill 4: funded costs

Opening NAV is $1 million, pretrade NAV is $1.02 million, and funded costs are $510. What is net return?

**Answer:** closing NAV is $1,019,490; net return is **1.949%**. Gross return is 2%, and the exact cost contribution is 5.1 bp of opening NAV. Cost/pretrade NAV is 5 bp, a different denominator.

### Drill 5: compounding

A portfolio returns +20% and then −20%. Why is the net result not zero?

**Answer:** wealth changes from 100 to 120 to 96. The second loss is applied to a larger base. The cumulative result is −4%; linked dollar contributions are +20 and −24 per 100 initial capital.

### Drill 6: date logic

The proposal executes on the first trading close of February. May its covariance include that day's close-to-close return?

**Answer:** not under this model. The proposal is based on the prior close, and old holdings earn execution day's return. Including it introduces look-ahead relative to the stated clock.

### Drill 7: duplicate benchmark

A benchmark has two records for one date. A join to 30 portfolio paths returns 60 rows for that day. Should you divide the sum by two?

**Answer:** no. Identify and repair the broken uniqueness contract and investigate the cause. Arithmetic compensation masks an invalid join and may fail on other dates.

### Drill 8: cost-free counterfactual

Can you obtain a zero-cost portfolio's terminal wealth by adding cumulative fees to the cost-bearing terminal NAV?

**Answer:** not generally. Fees change future invested holdings and returns. A zero-cost counterfactual needs a separate simulation. Cumulative fee attribution is a valid component of the actual path, not the whole counterfactual difference.

### Drill 9: bounds versus drift

A position is capped at 20% at monthly rebalances and becomes 20.4% midmonth solely through returns. Is the engine necessarily wrong?

**Answer:** no, not under this stated policy. Execution-close compliance and interim drift are different checks. Report the drift and discuss whether the real mandate instead requires continuous limits.

### Drill 10: independence

The primary and checker both use the wrong total-return field but reconcile perfectly. What failed?

**Answer:** shared specification or source interpretation. Separate arithmetic paths cannot eliminate common-mode risk. Validate vendor semantics and obtain independent review of the data contract.

### Drill 11: risk allowance units

Minimum feasible estimated TE is 1.20%, and the allowance is 25 bp. What is the budget?

**Answer:** **1.45% annualized TE**. It is not 1.50% from multiplying by 1.25, and it is not a cap on realized annual active return.

### Drill 12: total versus price return

An ETF begins at $100, ends at $99, and distributes $2. What is wrong with using −1% price return and separately calling that a total-return backtest?

**Answer:** it omits the distribution. A simplified total-return illustration is approximately +1%, but actual vendor timing conventions govern. If the source already supplies total return, adding the distribution again also creates an error.

## 18. A practical preparation loop

**Loop 1—explain:** deliver the 60-second narrative without notes. Check that you mention the economic result, independent control layer, and one scope boundary.

**Loop 2—calculate:** solve the accounting, turnover, annualization, and linking drills by hand. Stop and resolve any unit error before practicing polished answers.

**Loop 3—trace:** open one actual source function, one control result, and one artifact. Explain the lineage from input to decision. Be able to name what is shared and what is independent.

**Loop 4—break and recover:** examine a recorded incident, identify the expected detector, and explain why recovery requires a clean rerun rather than editing a chart.

**Loop 5—challenge:** answer “What would make this result misleading?” Give current-vintage data, fixed universe, simplistic costs, omitted taxes, and exposed historical development as separate limitations.

**Loop 6—communicate:** deliver the three-minute version to someone who has not seen the code. Ask them to repeat the business decision back to you. If they remember only “an optimizer,” simplify the message.

The goal is not to sound certain about everything. It is to be precise about what the evidence establishes, fast at detecting unit and accounting errors, and credible about the judgment still required.

## 19. Evidence and reading map

- [Project overview](../README.md): entry point and public artifact links.
- [Research methodology](METHODOLOGY.md): original optimization, timing, and funding specification.
- [Oversight methodology](OVERSIGHT_METHODOLOGY.md): independent checks, SQL, attribution, and incident semantics.
- [60-minute rehearsal and answer key](INTERVIEW_PRACTICE.md): question-first calculations, exact code-navigation tasks, incident communication, and scoring.
- [Data contract](DATA.md): CIZ fields, historical identities, coverage, vintage, and licensing.
- [Research results](RESULTS.md): exact aggregate comparisons and interpretation.
- [Reproduction guide](REPRODUCING.md): environment, commands, entitlement, and known historical receipts.
- `outputs/oversight/validation_summary.json`: current saved clean-run control evidence.
- `outputs/oversight/incident_summary.json`: deliberate-fault evidence and recovery status.
- `outputs/oversight/Portfolio_Oversight.xlsx`: public review workbook; any detailed trade illustration must be labeled synthetic.
- `outputs/oversight/Portfolio_Oversight_Memo.pdf`: concise stakeholder readout.
- `outputs/oversight/Interview_Guide.pdf` and `.docx`: portable editions of this guide.

Official role: [JPMorgan Chase requisition 210775966](https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/job/210775966/). The public posting is role-alignment context, not evidence of employment, endorsement, or interview selection.
