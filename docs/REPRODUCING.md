# Reproducing the study

[Overview](../README.md) · [Results](RESULTS.md) · [Methodology](METHODOLOGY.md) · [Data contract](DATA.md)

## Review without a WRDS account

The [executed notebook](../01_cost_of_customization.ipynb),
[four-page visual brief](../outputs/wrds/visual_brief/WRDS_results_visual_brief.pdf),
and [aggregate result tables](../outputs/wrds/) are committed. They can be reviewed
on GitHub without downloading licensed source records.

Re-executing the research requires your own WRDS/CRSP access. Missing input data
stop the pipeline; the project does not substitute another vendor or synthetic
portfolio performance.

## Set up Python

Use Python 3.10–3.12. The saved run used Python 3.10.11; package versions are in
[requirements.txt](../requirements.txt) and the
[run receipt](../outputs/wrds/run_summary.json).

```bash
git clone https://github.com/JoshGutierrez56/personalized-model-portfolios.git
cd personalized-model-portfolios
python -m venv .venv
```

Activate the environment:

```powershell
# Windows PowerShell
.venv\Scripts\Activate.ps1
```

```bash
# macOS / Linux
source .venv/bin/activate
```

```bash
python -m pip install -r requirements.txt
```

## Retrieve licensed input data

Configure PostgreSQL's local password-file mechanism and your licensed WRDS
account as described in [DATA.md](DATA.md#authentication). Do not put credentials
in source files or notebook cells. Complete WRDS/Duo verification if requested.

```bash
python wrds_data.py --download
python wrds_data.py
```

The first command retrieves the bounded extract. The second checks its local
hashes, identities, calendar coverage, and return-quality contract.

Expected input: eight ETFs × 4,024 trading days, or **32,192 security-day rows**,
January 4, 2010 through December 31, 2025. A fresh CRSP vintage may differ from the
saved September 30, 2026 extract; inspect provenance before comparing results.

## Run and inspect

```bash
python run_research.py
python check_notebook.py
python build_visual_brief.py
python -m jupyterlab
```

Run from the repository root. `run_research.py` performs the baseline and all
eight sensitivity specifications. This is the main compute-intensive step;
runtime depends on the machine and solver. It writes:

| Location | Contents | Committed? |
| :--- | :--- | :--- |
| `data/wrds/` | Licensed inputs, historical identities, extraction manifest | No |
| `outputs/wrds_private/` | Daily portfolios, benchmark, allocations, trade ledger | No |
| `outputs/wrds/` | Aggregate metrics, figures, and run/data receipts | Yes |
| `outputs/wrds/visual_brief/` | Presentation charts, PDF, comparison CSV, provenance | Yes |

`check_notebook.py` executes and saves all notebook cells. Verified complete
research artifacts are reused when the source hashes and configuration match;
set `RECOMPUTE=True` in the notebook to force recalculation. The local licensed
extract and detailed simulation records are still needed for relevant checks and
the visual brief; cloning the aggregate outputs alone is not a complete cache.

`build_notebook.py` is the notebook authoring source. It regenerates the notebook
structure without executed outputs, so run it only when editing the narrative,
then re-execute with `check_notebook.py`.

## Validate

```bash
python -m unittest discover -s tests -v
python audit_research.py
```

Unit tests use controlled fixtures and do not need a new WRDS download. The audit
requires the completed local research run. It independently checks source hashes,
decision chronology, portfolio bounds, estimated TE budgets, return compounding,
cost funding, and completeness of sensitivity results.

The saved validation is **22 passing tests**, **8 executed notebook code cells**,
and an audit of **4,320 allocation decisions**. Treat committed receipts as
evidence for the saved run, not as a substitute for validating your own rerun.

## Source map

| File | Responsibility |
| :--- | :--- |
| [wrds_data.py](../wrds_data.py) | Read-only retrieval, historical IDs, coverage, flags, and hashes |
| [portfolio_engine.py](../portfolio_engine.py) | Bounded proportional allocation and checked convex optimizers |
| [walkforward.py](../walkforward.py) | Lagged decisions, drifting holdings, self-funded costs, and metrics |
| [run_research.py](../run_research.py) | Baseline, sensitivities, uncertainty intervals, and original figures |
| [audit_research.py](../audit_research.py) | Independent source, chronology, and ledger reconciliation |
| [build_notebook.py](../build_notebook.py) | Notebook narrative and cell definitions |
| [check_notebook.py](../check_notebook.py) | Execute and save the notebook |
| [build_visual_brief.py](../build_visual_brief.py) | Four-chart presentation and source-reconciled calculations |

## Troubleshooting

- **WRDS authentication failure:** verify your local password-file setup and
  institutional entitlement; do not disable TLS or embed passwords in code.
- **Missing records or source-hash mismatch:** investigate the extraction and
  manifest. Do not fill missing returns or relabel a new file as the old extract.
- **Solver failure:** inspect the recorded status and feasibility checks. Do not
  accept an inaccurate solution merely to finish a run.
- **Notebook requests a long rerun:** source hashes, configuration, or complete
  research artifacts no longer match. Review the change before recomputing.

See [methodology](METHODOLOGY.md) for the accounting and numerical policies.
