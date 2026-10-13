# Reproduce the portfolio oversight layer

There are two distinct reproduction routes. Neither silently substitutes fabricated market evidence for the CRSP-backed study.

## 1. Public, no-login verification

For a quick, inspectable walkthrough of the validator itself:

```bash
python -m venv .venv
# Windows PowerShell: .venv/Scripts/Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements-demo.txt
python run_public_demo.py --no-write
```

This route uses explicitly artificial, hand-derived two-sleeve inputs. It demonstrates accounting, deliberately broken inputs, and correction/retest without a WRDS account or the research notebook stack. It is **not a reproduction of the empirical investment results** and never overwrites the published research. Omit `--no-write` to save its separate teaching receipt under `outputs/public_demo/`.

For the full automated test suite, use the broader research environment below.

The repository includes the independent code, policy contract, versioned SQL, hand-derived test fixtures, aggregate research evidence, Excel workbook, decision memo and interview guide. It does not include the licensed security-day source or detailed simulation/trade ledgers.

```bash
python -m venv .venv
# Activate your environment using the command appropriate to your shell.
python -m pip install -r requirements.txt
python -m pytest -q -W error
```

These tests require no WRDS login. Artificial inputs are labeled validation fixtures, not evidence of investment performance. CI runs this same test command on Linux and Windows with Python 3.11, then runs the public walkthrough and rebuilds the dashboard from the hash-bound aggregate evidence.

Read the saved receipts in `outputs/oversight/`:

- `validation_summary.json`: baseline independent control results and aggregate attribution.
- `incident_summary.json`: five explicitly injected fault cases, required domain detectors, corrections and clean retest.
- `run_receipt.json`: run identity, timestamps, input/challenger fingerprints and release status.
- `historical_stress.json`: aggregate replay of two already-exposed historical periods.
- `release_verification.json`: final local test/report/publishing verification, when present.

`run_receipt.json` binds the baseline, incident, stress and scenario artifacts by exact SHA-256. Report/dashboard generation checks their agreement, statuses, domain-specific incident detection, corrected retests, and shared source fingerprints before rendering. `.gitattributes` preserves those artifact bytes across Windows/Linux clones. This detects accidental mixed or altered evidence; hashes are not an external attestation or a substitute for the licensed source.

The public guard also checks internal financial identities even when altered artifacts have been rehashed: linked portfolio contributions plus costs must reconcile to portfolio return, benchmark contributions to benchmark return, and active contributions to the portfolio-minus-benchmark difference. Contribution maps must cover the same assets and the shared benchmark must agree across paths. Historical-stress gaps must equal net minus benchmark return; returns cannot fall below −100%, drawdown must be between −100% and zero and include the loss from starting wealth, and each episode must use one shared benchmark return. Reconciliation tolerances are `1e-10` in return fractions and `1e-8` in percentage points. These checks establish aggregate consistency, not that a self-consistent replacement bundle came from authentic market observations.

Guard-only changes can be verified against the existing public bundle without rerunning the licensed study. The original empirical run receipt remains a historical record of the code and inputs used then; the separately dated release-verification receipt records later guard/test checks. Do not relabel an old empirical run as newly executed merely because its public evidence passes a newer guard.

The public attribution checks do not infer initial capital or equate a return fraction with terminal dollar NAV. Cross-table capital-scale reconstruction still belongs to the independent validator with its explicit policy contract and licensed input ledgers.

The dashboard embeds aggregate receipts and works without an API. Open `docs/index.html` locally, or use the published Pages link in the README. Selecting an injected case changes the fault explanation and failure evidence. Selecting an account changes the risk/cost comparison. This is a saved-evidence viewer, not a live market terminal.

## 2. Empirical rerun with licensed data

Use your own authorized WRDS/CRSP access. Follow [the original reproduction guide](REPRODUCING.md) to obtain the source and generate the original portfolio ledgers. Never share credentials or acquire licensed data from another person's clone.

The oversight layer expects:

```text
data/wrds/{daily,identities,calendar}.csv
data/wrds/manifest.json
outputs/wrds/run_summary.json
outputs/wrds/scenario_summary.csv
outputs/wrds_private/{daily,decisions,trades,benchmark}.csv
```

Then run:

```bash
python run_oversight.py
python build_oversight_reports.py
python build_oversight_dashboard.py
```

The runner makes no new network/data request. It checks the existing source/run provenance, independently reconstructs the baseline, applies five in-memory fault copies, retests the unchanged original inputs, and confirms original input hashes did not change. A domain-specific failure is required for a mutation to count as detected. A generic exception is not a successful fault test.

The original study uses actual CRSP CIZ returns with explicit hypothetical restrictions, model weights and trading costs. A different downloaded data vintage can change results; do not describe a new extract as identical solely because the dates match. Pin and disclose its actual manifest.

## Fingerprints and portability

Licensed input bytes retain exact SHA-256 hashes. Each receipt also fingerprints the actual challenger code bytes used for that run. The production-source contract uses a separately declared canonical newline convention so a Git LF versus Windows CRLF checkout does not create a false economic drift finding. A substantive source change still requires explicit review of the contract and rerun.

The independently declared policy contract must remain consistent with the original executed configuration. This checks specification drift, not the optimality of the original optimizer. The checker does not call the production engine's validation/accounting functions; it shares declared policy, source data and the numerical Ledoit–Wolf dependency.

## Public versus private outputs

- Public: aggregate control receipts, cumulative contribution totals, scenario economics, selected historical stress summaries, PDF/DOCX reports, charts and workbook.
- Private: original licensed rows, full security-day contributions/holdings, detailed historical trades and unaggregated diagnostic ledgers.
- `outputs/oversight_private/` is ignored by Git. The validator refuses a detailed-output destination outside that directory, including resolved path escapes.
- The public workbook's `WorkedExample` sheet is a fabricated two-asset accounting exercise with visible formulas. Its numbers are not part of the empirical study. Materialized empirical summaries on the other sheets are readable without recalculation; opening the file in Excel or LibreOffice recalculates the teaching formulas.

## How to inspect a failure

1. Read the control's ID, units, maximum error and tolerance in `validation_summary.json`.
2. Distinguish a missing/duplicate-key failure from an economic reconciliation failure. Structural failures stop before a potentially many-to-many join.
3. For an injected case, inspect `failed_checks` and `expected_domain_checks_any` in the incident receipt.
4. The wrong-return case holds recorded trades fixed while changing the return definition. Its blocked replay is diagnostic disagreement, not a viable counterfactual strategy or an observed client loss.
5. Correct the source/policy issue rather than widening tolerances to obtain a PASS. Re-run the dirty-case regression and clean baseline.
6. A technical PASS releases the evidence for review. It does not authorize investment decisions or live trades.

## Scope

The public pipeline does not include a new pristine holdout, a production order-management connection, tax-lot accounting, observed transaction-cost calibration, or a stock-level risk model. Full-history contribution linking is an exact dollar-P&L decomposition relative to initial capital, not Brinson or factor attribution. See [the technical method](OVERSIGHT_METHODOLOGY.md) and [interview guide](INTERVIEW_GUIDE.md) for the distinction.
