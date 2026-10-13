# Personalized Model Portfolios

## Portfolio Validation & Investment Oversight Lab

**Would I approve this rebalance—and can I independently explain its risks, costs and performance?**

The portfolio implementation study below now has a separately implemented **Python + SQL challenger**. It reconstructs holdings, fees, NAV, benchmark returns and cumulative return contributions; challenges the decision clock, risk calculations and client constraints; and demonstrates a complete injected-fault → diagnosis → correction → retest workflow.

**Start here:** [Interactive evidence dashboard](https://joshgutierrez56.github.io/personalized-model-portfolios/) · [Two-page decision memo](outputs/oversight/Portfolio_Oversight_Memo.pdf) · [Excel control workbook](outputs/oversight/Portfolio_Oversight.xlsx)

**Understand and defend it:** [Interview field guide · PDF](outputs/oversight/Interview_Guide.pdf) · [Editable guide · DOCX](outputs/oversight/Interview_Guide.docx) · [Technical methodology](docs/OVERSIGHT_METHODOLOGY.md)

[![Portfolio oversight dashboard showing baseline PASS, five detected injected failures, thirty reconstructed paths and the investment decision.](docs/assets/oversight-preview.png)](https://joshgutierrez56.github.io/personalized-model-portfolios/)

| Verified evidence | Scope |
| :--- | :--- |
| **30 paths / 90,540 daily records** independently reconstructed | 10 hypothetical accounts × 3 methods; actual WRDS/CRSP returns |
| **115 baseline controls passed** | Accounting, source/configuration provenance, chronology, risk windows, constraints and versioned SQL |
| **5 / 5 deliberately injected faults blocked** | Wrong return definition, duplicate trade, look-ahead timestamp, prohibited allocation and fee error |
| **Clean retest passed; original input hashes unchanged** | Mutations operate only on in-memory copies |
| **Public tests run with warnings treated as errors** | Original research, hand-derived challenger fixtures and independent adversarial cases; [commit-specific Linux/Windows results](https://github.com/JoshGutierrez56/personalized-model-portfolios/actions/workflows/validation.yml) |

This is **retrospective research validation**, not a production trading platform. Passing the technical gate releases evidence for review; it does not authorize an investment decision. The main investment conclusion remains: in the no-gold account, roughly 60% less turnover saved only about $110 annually per constant $1m at the assumed cost rate, while adding about 27bp of realized tracking risk.

### Try the validator without a data subscription

```bash
python -m pip install -r requirements-demo.txt
python run_public_demo.py --no-write
```

This small walkthrough uses **clearly artificial, hand-derived inputs**, not substitute market data. Follow an accounting reconciliation, observe named broken inputs get blocked, and inspect the corrected retest. The WRDS/CRSP investment evidence remains a separate research result.

[60-minute rehearsal PDF](outputs/oversight/Interview_Practice.pdf) | [Editable rehearsal DOCX](outputs/oversight/Interview_Practice.docx) | [60-minute interview practice and answer key](docs/INTERVIEW_PRACTICE.md) · [Reproduction routes](docs/OVERSIGHT_REPRODUCING.md)

### Review or reproduce

The dashboard, workbook, reports and aggregate receipts are public. Licensed source rows and detailed security-day ledgers are not distributed. The public release guard also reconciles every displayed scenario metric to independently reconstructed accounting and risk results, checks artifact hashes, and rejects inconsistent incident evidence. Anyone can run the artificial validation fixtures without a WRDS login:

```bash
python -m pip install -r requirements.txt
python -m pytest -q -W error
```

With your own licensed inputs and the saved original research ledgers:

```bash
python run_oversight.py
python build_oversight_reports.py
python build_oversight_dashboard.py
```

[Reproduction routes and privacy boundaries](docs/OVERSIGHT_REPRODUCING.md) · [Baseline receipt](outputs/oversight/validation_summary.json) · [Incident evidence](outputs/oversight/incident_summary.json) · [Run fingerprints](outputs/oversight/run_receipt.json) · [Independent SQL](sql/)

The checker uses a separately declared [policy contract](oversight_contract.json), not the production engine's validation/accounting functions. It still shares source data, economic assumptions and a numerical covariance dependency; it does not certify optimizer optimality. Faults are deliberately injected tests—not client incidents—and a wrong-return replay with fixed recorded trades is diagnostic disagreement, not an investable alternative strategy. The project was built with AI coding and drafting assistance, with source, checks and interpretation kept inspectable.

---

## Original portfolio implementation research

**The cost of customization · Multi-asset portfolio research · WRDS / CRSP**

How much tracking risk should a portfolio manager accept to accommodate a client's restrictions—and how much is avoiding a trade actually worth?

This study follows constrained ETF portfolios through a **2014–2025 walk-forward simulation**. It combines actual CRSP total returns, lagged risk estimates, monthly execution, drifting holdings, and transaction costs funded by the account.

[**Executed notebook →**](01_cost_of_customization.ipynb) · [**Results brief →**](docs/RESULTS.md) · [**Four-page PDF →**](outputs/wrds/visual_brief/WRDS_results_visual_brief.pdf) · [**Reproduce →**](docs/REPRODUCING.md)

| Evidence | Research design | Validation |
| :--- | :--- | :--- |
| **32,192** CRSP security-day observations | **10** account scenarios × **3** methods | **4,320** checked allocation decisions |
| **8 ETFs**, 2010–2025 source history | **12 years**, 2014–2025 evaluation | **22 tests** and an accounting audit |
| Historical identities and source hashes | **8** sensitivity specifications | **8** executed notebook code cells |

> **The investment conclusion:** risk-aware allocation improved model tracking across every constrained scenario. But for these liquid ETFs, a large reduction in turnover bought surprisingly little in direct trading-cost savings.

The returns are observed data. Account restrictions, policy weights, initial wealth, and execution costs are explicit experimental assumptions.

## Results at a glance

### 01 / Risk-aware allocation improved tracking in all nine constrained cases

Minimum-tracking-risk allocation reduced realized tracking error by **20–69%** relative to bounded proportional allocation, with a **35.5% median reduction**. Both methods faced identical account restrictions.

[![All nine constrained scenarios: realized annualized tracking error is lower with minimum-risk allocation than proportional allocation; reductions range from 20 to 69 percent.](outputs/wrds/visual_brief/01_risk_aware_allocation.png)](outputs/wrds/visual_brief/01_risk_aware_allocation.png)

**Read the chart:** tracking error is the annualized standard deviation of active daily returns. Lower tracking error means less variable deviation from the model, not necessarily a higher return or a smaller cumulative return gap.

[Scenario results, CSV](outputs/wrds/scenario_summary.csv) · [All scenarios and methods](docs/RESULTS.md#complete-scenario-comparison)

### 02 / Sixty percent less turnover saved about $110 a year per $1 million

For the no-gold account, lower-turnover allocation reduced annual one-way turnover from **18.23% to 7.25%**. Realized tracking error increased from **1.37% to 1.64%**. The modeled annual cost benefit was just **1.10 basis points of account value**.

[![No-gold account: turnover falls 60 percent, tracking error increases 27 basis points, and annualized modeled trading costs fall 1.10 basis points of account value.](outputs/wrds/visual_brief/02_turnover_tradeoff.png)](outputs/wrds/visual_brief/02_turnover_tradeoff.png)

**Why it matters:** at 5 bp per dollar bought or sold, avoiding trades in liquid ETFs is inexpensive in dollar terms. The $110 figure scales the annual cost-rate difference to a constant $1 million NAV; it is not an exact CAGR benefit or a guaranteed annual saving. The added-risk estimate has a paired 95% block-bootstrap interval of **20.0–35.6 bp**, conditional on this historical sample.

[Uncertainty intervals, CSV](outputs/wrds/tracking_risk_intervals.csv) · [Cost accounting](docs/METHODOLOGY.md#funding-transaction-costs)

### 03 / Closest tracking did not mean highest return

The no-gold portfolios ended with **$2.26m–$2.46m** from a $1m starting account. The frictionless policy benchmark, which retained its 10% gold allocation, ended at **$2.54m**. Exposure differences—not small trading-cost savings—dominate this comparison.

[![No-gold portfolio growth and rolling tracking risk, 2014–2025. Terminal wealth: minimum risk 2.26 million dollars, proportional 2.42 million, lower turnover 2.46 million, and policy benchmark 2.54 million.](outputs/wrds/visual_brief/03_wealth_and_risk.png)](outputs/wrds/visual_brief/03_wealth_and_risk.png)

**Interpretation:** minimizing active-return variance is not the same objective as maximizing wealth. The observed return ranking is not evidence of alpha.

### 04 / A larger risk allowance reached diminishing cost savings quickly

Doubling the no-gold allowance from 25 to 50 bp roughly doubled the additional realized tracking risk, while increasing modeled annual savings from only **$110 to $115 per $1m**. The chart includes the baseline and all eight sensitivity runs; each is a complete portfolio simulation.

[![All eight no-gold sensitivity specifications and the base case: doubling the risk allowance adds approximately twice the tracking risk, but only five dollars more annual cost savings per million.](outputs/wrds/visual_brief/04_sensitivity_economics.png)](outputs/wrds/visual_brief/04_sensitivity_economics.png)

[Full sensitivity results, CSV](outputs/wrds/sensitivity_summary.csv) · [Visual-brief calculations](outputs/wrds/visual_brief/no_gold_sensitivity_comparison.csv)

## Research design

The policy model allocates **30/10/15/5/20/5/10/5%** to SPY / IWM / EFA / EEM / IEF / TLT / GLD / SHY. Each account starts from the same legacy allocation and $1 million of total-return holdings.

| Implementation | Objective | What changes |
| :--- | :--- | :--- |
| **Proportional** | Redistribute model weights within the bounds | No covariance estimate |
| **Minimum tracking risk** | Minimize estimated active-return variance | Uses lagged Ledoit–Wolf covariance |
| **Lower turnover** | Minimize trading within a tracking-risk budget | Allows 25 bp above minimum feasible estimated TE |

![Monthly decision sequence: estimate risk and set allocations at the previous month-end close; old holdings earn the next trading day's return; execute at that day's close and fund costs from the account; subsequent returns accrue to the new drifting holdings.](docs/assets/decision-clock.svg)

**Timing discipline:** a return on execution day cannot influence that day's allocation proposal. The old positions earn that return before the planned allocation trades at the close. Holdings then drift until the next rebalance.

[Full methodology](docs/METHODOLOGY.md) · [Data contract and provenance](docs/DATA.md) · [Run configuration](outputs/wrds/run_summary.json)

## Reproduce the research

**To review:** the executed notebook, charts, aggregate CSVs, and PDF are committed and readable without a WRDS login.

**To rerun:** Python 3.10–3.12 and your own licensed WRDS/CRSP access are required. After cloning, creating a virtual environment, and configuring local credentials:

```bash
python -m pip install -r requirements.txt
python wrds_data.py --download
python run_research.py
python check_notebook.py
python build_visual_brief.py
```

There is no Yahoo or simulated-performance fallback. The first run performs all eight sensitivity studies. See the [reproduction guide](docs/REPRODUCING.md) for setup, validation commands, cached reruns, and expected artifacts.

## Evidence and validation

The saved study passed **22 tests**, executed **all eight notebook code cells**, and passed an independent accounting/chronology audit across **4,320 decisions**. The visual-brief metrics reconcile to the underlying daily portfolio records.

- [Data-quality receipt](outputs/wrds/data_quality.json): coverage, identifiers, return flags, and source hashes.
- [Research audit](outputs/wrds/AUDIT.json): chronology, constraint feasibility, risk budgets, wealth compounding, and self-financing trades.
- [Validation receipt](outputs/wrds/VALIDATION.json): test and notebook checks.
- [Visual-brief provenance](outputs/wrds/visual_brief/visual_brief_receipt.json): source hashes and displayed calculations.

Artificial data appear only in validation fixtures, never as market evidence.

## Scope and limitations

This is a retrospective, fixed-universe **ETF implementation study**. It does not model tax lots, calibrated market impact, actual client activity, or production order management. The benchmark is frictionless; account results include assumed trading costs. SHY is a short-duration Treasury fund, not cash. Weight bounds apply at execution closes; interim drift is measured rather than silently corrected.

The CRSP extract is current-vintage. Lagged decisions prevent return look-ahead but do not eliminate database revisions or retrospective universe-selection bias. The analysis supports discussion of risk and implementation, not a claim of future outperformance. [Detailed limits →](docs/METHODOLOGY.md#scope)

## Repository guide

| Start here | Supporting material |
| :--- | :--- |
| [Executed notebook](01_cost_of_customization.ipynb) | The complete empirical narrative |
| [Results](docs/RESULTS.md) · [Methodology](docs/METHODOLOGY.md) | Findings, definitions, and model assumptions |
| [Reproduction](docs/REPRODUCING.md) · [Data](docs/DATA.md) | Setup, WRDS access, and licensing |
| [Research outputs](outputs/wrds/) | Current aggregate results and figures |
| [Visual brief](outputs/wrds/visual_brief/) | Four charts in PNG/SVG, PDF, and source calculations |
| [Source map](docs/REPRODUCING.md#source-map) · [Tests](tests/) | Data pipeline, optimizers, simulation, and checks |
| [Historical archive](archive/README.md) | Superseded Yahoo prototype, explicitly separated |

Licensed source rows and detailed daily simulations remain local and are excluded from Git. Built with pandas, NumPy, scikit-learn, CVXPY/CLARABEL, Matplotlib, and PostgreSQL/libpq, with AI coding assistance.

**Josh Gutierrez** · [GitHub](https://github.com/JoshGutierrez56)
