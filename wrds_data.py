"""Bounded, authenticated CRSP CIZ retrieval. No Yahoo or simulated-data fallback."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from portfolio_engine import TICKERS

ROOT = Path(__file__).resolve().parent
HOST = "wrds-pgdata.wharton.upenn.edu"
START = "2010-01-04"
END = "2025-12-31"
IDENTITY_SQL = """
SELECT ticker, permno, securitynm, secinfostartdt, secinfoenddt, securitybegdt
FROM crsp.stksecurityinfohist
WHERE ticker = ANY(%s) AND secinfostartdt <= %s AND secinfoenddt >= %s
ORDER BY ticker, permno
"""
RETURNS_SQL = """
SELECT permno, dlycaldt AS date, ticker AS observed_ticker,
       dlyret AS total_return, dlyretx AS ex_distribution_return,
       dlyprc AS price, dlyvol AS volume, dlybid AS bid, dlyask AS ask,
       dlyretmissflg, dlyretdurflg, dlydelflg, tradingstatusflg
FROM crsp.dsf_v2
WHERE permno = ANY(%s) AND dlycaldt BETWEEN %s AND %s
ORDER BY dlycaldt, permno
"""
CALENDAR_SQL = """
SELECT caldt AS date FROM crsp.metaexchangecalendar
WHERE caldt BETWEEN %s AND %s AND tradingflg = 'Y' AND exchangegroup = 'CIZ'
ORDER BY caldt
"""


def _read_query(connection, query, params):
    with connection.cursor() as cursor:
        cursor.execute(query, params)
        return pd.DataFrame(cursor.fetchall(), columns=[c[0] for c in cursor.description])


def validate_identity(identities, tickers=TICKERS):
    if identities.empty or identities.ticker.duplicated().any():
        raise ValueError("Missing or ambiguous historical ticker identity; inspect CRSP names.")
    if set(identities.ticker) != set(tickers) or identities.permno.duplicated().any():
        raise ValueError("Every requested ticker must resolve to one distinct PERMNO.")


def validate_panel(rows, identities, calendar):
    """Reject holes, duplicates, sentinel missing returns and multi-day returns."""
    validate_identity(identities)
    frame = rows.copy()
    frame["date"] = pd.to_datetime(frame.date)
    if frame.duplicated(["date", "permno"]).any():
        raise ValueError("Duplicate CRSP security/date observations.")
    if set(frame.permno) != set(identities.permno):
        raise ValueError("CRSP returned unexpected or missing permanent identifiers.")
    mapping = identities.set_index("permno").ticker.to_dict()
    frame["ticker"] = frame.permno.map(mapping)
    frame["total_return"] = pd.to_numeric(frame.total_return, errors="raise")
    if not np.isfinite(frame.total_return).all() or (frame.total_return <= -1).any():
        raise ValueError("Invalid/missing total return or total-loss event needs explicit handling.")
    if not frame.dlyretmissflg.eq("NA").all():
        raise ValueError("CRSP marks a missing/exceptional return; investigate the source.")
    if not frame.dlyretdurflg.isin(["D1", "D2", "D3", "D4", "DU"]).all():
        raise ValueError("Multi-trading-period or unknown return duration; cannot treat as daily.")
    if not frame.dlydelflg.eq("N").all() or not frame.tradingstatusflg.eq("A").all():
        raise ValueError("Delisted/non-active instrument requires an explicit liquidation/replacement policy.")
    dates = pd.DatetimeIndex(pd.to_datetime(calendar.date)).sort_values()
    if dates.duplicated().any() or len(dates) < 250:
        raise ValueError("Invalid reference trading calendar.")
    wide = frame.pivot(index="date", columns="ticker", values="total_return")
    wide = wide.reindex(index=dates, columns=TICKERS)
    if wide.isna().any().any() or len(frame) != len(dates) * len(TICKERS):
        raise ValueError("Incomplete CRSP calendar/panel. No row dropping or forward filling.")
    wide.index.name = "date"
    return frame, wide.astype(float)


def local_connection(username=None):
    """Use an existing libpq passfile; never print, embed, or copy its password.

    WRDS_USERNAME selects the account. If absent, infer only the username from
    a matching local passfile entry; libpq itself reads the credential.
    """
    import psycopg2
    default = (Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming")) /
               "postgresql/pgpass.conf") if os.name == "nt" else Path.home() / ".pgpass"
    passfile = Path(os.environ.get("PGPASSFILE", str(default)))
    username = username or os.environ.get("WRDS_USERNAME")
    if not username and passfile.exists():
        # Parse only non-secret fields. Escaped colons/backslashes in passwords
        # do not affect the first four fields for this allowlisted hostname.
        entries = [line.split(":", 4) for line in passfile.read_text().splitlines()
                   if line and not line.startswith("#")]
        users = {p[3] for p in entries if len(p) == 5 and p[0] == HOST
                 and p[1] in {"9737", "*"} and p[2] in {"wrds", "*"}}
        del entries
        if len(users) == 1:
            username = users.pop()
    if not username or not passfile.exists():
        raise RuntimeError("Configure a local WRDS/libpq passfile and WRDS_USERNAME; see docs/DATA.md.")
    try:
        connection = psycopg2.connect(host=HOST, port=9737, dbname="wrds", user=username,
            passfile=str(passfile), sslmode="require", connect_timeout=90,
            options="-c statement_timeout=180000")
    except psycopg2.Error as exc:
        raise RuntimeError("WRDS authentication/connection failed. Check account, network and Duo; credentials were not logged.") from None
    connection.set_session(readonly=True, autocommit=True)
    return connection


def fetch_wrds(cache_dir=None, connection=None):
    folder = Path(cache_dir or ROOT / "data/wrds")
    folder.mkdir(parents=True, exist_ok=True)
    owns = connection is None
    db = connection or local_connection()
    try:
        names = _read_query(db, IDENTITY_SQL, (TICKERS, START, START))
        validate_identity(names)
        rows = _read_query(db, RETURNS_SQL, (names.permno.astype(int).tolist(), START, END))
        calendar = _read_query(db, CALENDAR_SQL, (START, END))
        frame, returns = validate_panel(rows, names, calendar)
        if returns.index.min() != pd.Timestamp(START) or returns.index.max() != pd.Timestamp(END):
            raise ValueError("Licensed CRSP vintage does not cover the complete requested window.")
        flags = {col: frame[col].fillna("MISSING").astype(str).value_counts().to_dict()
                 for col in ["dlyretmissflg", "dlyretdurflg", "dlydelflg", "tradingstatusflg"]}
        receipt = {
            "source": "WRDS / CRSP US Stock Database, CIZ (Flat File Format 2.0)",
            "returns_table": "crsp.dsf_v2", "return_field": "dlyret",
            "identity_table": "crsp.stksecurityinfohist", "identity_asof": START,
            "calendar_table": "crsp.metaexchangecalendar", "requested_start": START, "requested_end": END,
            "retrieved_utc": datetime.now(timezone.utc).isoformat(),
            "rows": len(frame), "trading_days": len(returns), "assets": len(TICKERS),
            "flags": flags, "missing_returns": int(returns.isna().sum().sum()),
            "duplicate_security_dates": 0, "files": {},
            "return_treatment": "CIZ DlyRet includes distributions and delisting returns; do not add legacy DLRET.",
            "vintage_caveat": "Current database vintage; not an archived as-known-at-the-time extract.",
            "queries": {"identity": IDENTITY_SQL, "returns": RETURNS_SQL, "calendar": CALENDAR_SQL},
        }
        for name, table in [("daily.csv", frame), ("identities.csv", names), ("calendar.csv", calendar)]:
            path = folder / name
            table.to_csv(path, index=False)
            receipt["files"][name] = hashlib.sha256(path.read_bytes()).hexdigest()
        (folder / "manifest.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        return returns, frame, receipt
    finally:
        if owns:
            db.close()


def load_wrds(cache_dir=None):
    """Offline reproduction from the previously authenticated, hash-checked extract."""
    folder = Path(cache_dir or ROOT / "data/wrds")
    manifest = folder / "manifest.json"
    if not manifest.exists():
        raise FileNotFoundError("No WRDS extract. Run python wrds_data.py --download with licensed WRDS access.")
    receipt = json.loads(manifest.read_text(encoding="utf-8"))
    if receipt.get("returns_table") != "crsp.dsf_v2" or receipt.get("return_field") != "dlyret":
        raise ValueError("Unexpected data source; this study accepts CRSP CIZ only.")
    for name, expected in receipt["files"].items():
        if name not in {"daily.csv", "identities.csv", "calendar.csv"}:
            raise ValueError("Unexpected cache path in data manifest.")
        if hashlib.sha256((folder / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"CRSP cache hash mismatch: {name}; re-extract deliberately.")
    frame, returns = validate_panel(pd.read_csv(folder / "daily.csv", keep_default_na=False),
        pd.read_csv(folder / "identities.csv"), pd.read_csv(folder / "calendar.csv"))
    return returns, frame, receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true", help="Make an authenticated WRDS query.")
    args = parser.parse_args()
    _, _, receipt = fetch_wrds() if args.download else load_wrds()
    print(json.dumps({k: receipt[k] for k in ["source", "retrieved_utc", "rows", "trading_days", "flags"]}, indent=2))
