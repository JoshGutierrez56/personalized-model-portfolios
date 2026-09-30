# Data contract: WRDS / CRSP

The active study accepts only an authenticated CRSP CIZ extract from WRDS. There
is no Yahoo download or synthetic research mode. Fixtures in automated tests are
for checking code, not for generating the empirical results.

## Queries and identity

- Daily observations: `crsp.dsf_v2`, `dlyret` (total return).
- Historical security identity: `crsp.stksecurityinfohist`, effective on
  **January 4, 2010**, rather than selecting a security by its current ticker.
- Calendar: `crsp.metaexchangecalendar`, `tradingflg = 'Y'`, `exchangegroup = 'CIZ'`.
- Requested window: **January 4, 2010–December 31, 2025**, inclusive.
- Universe: SPY, IWM, EFA, EEM, IEF, TLT, GLD and SHY. Each symbol must resolve to
  exactly one distinct permanent security identifier at the identity date.

The legacy `crsp.dsi` calendar in the available vintage ends in 2024. It is not
used to truncate or validate the CIZ sample that extends through 2025.

CRSP CIZ total returns incorporate distributions and delisting returns. They are
used directly, not reconstructed from price changes, and legacy `DLRET` is **not**
added again. Prices and volumes serve only the lagged dollar-volume diagnostic.

The data controls require one row per requested security per reference trading
date, finite returns greater than -100%, missing-return flag `NA`, active status
`A`, and daily duration flags `D1`, `D2`, `D3`, `D4` or `DU`. `DU` still means one
trading period: a long holiday closure is not a missing return. Multi-trading-period
returns are rejected. Any delisting in this fixed ETF universe also stops the
pipeline until an explicit liquidation/replacement policy is implemented; no
security is silently dropped to obtain a complete panel.

## Authentication

Use your own licensed WRDS account. The retrieval command uses PostgreSQL's
existing local password-file mechanism, with TLS required and read-only queries.

- Windows default: `%APPDATA%/postgresql/pgpass.conf`.
- macOS/Linux default: `~/.pgpass` (restrict permissions to the owner).
- Override the path with `PGPASSFILE`; select the account with `WRDS_USERNAME`.
- If there is exactly one matching WRDS account in that file, its username can
  be inferred locally. Passwords are read by libpq and are never printed or copied
  into the repository.
- The endpoint is `wrds-pgdata.wharton.upenn.edu:9737`, database `wrds`.
- Complete WRDS/Duo verification if your account requests it. A successful
  existing authentication session need not generate a new prompt.

See [WRDS Python access](https://wrds-www.wharton.upenn.edu/pages/support/programming-wrds/programming-python/python-from-your-computer/)
for the institution's current setup instructions. Do not paste credentials into
the notebook, source files, issue trackers or chat.

```bash
python wrds_data.py --download
python wrds_data.py
```

The second command verifies the saved extract without making a network request.
Every source file is SHA-256 checked before reuse. The manifest stores the SQL,
retrieval timestamp, schema, date limits, row counts, quality flags and file hashes.
A changed file is an error, not silently treated as the same research run.

## Storage and licensing

`data/wrds/` contains the licensed rows, identifier history and manifest. Detailed
simulated daily paths, allocations and trade records go to `outputs/wrds_private/`.
Both directories are ignored by Git. The repository contains code, aggregate
research summaries, charts and non-secret provenance; no raw CRSP rows are pushed.
WRDS access does not itself grant redistribution rights. Another researcher needs
their own access and appropriate permission to obtain the input data.

## Limits of the data claim

This is a **current-vintage historical extract**, not an archive of what CRSP had
published on each historical date. Lagged decisions prevent return look-ahead;
they do not remove subsequent database revisions. Historical name resolution
protects against ticker reuse. It does not make a retrospectively chosen,
fixed eight-ETF universe survivorship-free. All eight existed at the sample start;
this is an exposure-implementation experiment, not an ETF-selection strategy.

References: [CRSP Format 2.0 guide](https://crsp.org/wp-content/uploads/guides/CRSP_US_Stock_&_Indexes_Database_Guide_Flat_File_Format_2.0.pdf),
[WRDS CIZ overview](https://wrds-www.wharton.upenn.edu/pages/support/manuals-and-overviews/crsp/stocks-and-indices/crsp-stock-and-indexes-version-2/crsp-ciz-overview/),
[Tidy Finance CIZ changes](https://blog.tidy-finance.org/posts/crsp-v2-update/).
