"""Incremental Agmarknet refresh from the data.gov.in open-data API.

`agmarknet_export.py` reads a hand-exported CSV of history. That export is a
snapshot: it stops on the day it was taken, and the detection window is the last
90 days, so a stale export slowly empties the queue. This module tops it up.

The resource is **Current Daily Price of Various Commodities from Various
Markets (Mandi)** — it serves only the last few days, not history. That is why
this runs on a schedule and *appends*: each run adds whatever is new, and the
committed file accumulates the history the portal will not give you twice. Miss
a fortnight and that fortnight is gone for good.

Two things this deliberately does not do:

**It does not touch the pipeline.** It writes into `data/raw/agmarknet_real/`
and stops. `pipeline.build` still reads only from disk and still opens no socket
— run it with the wifi off and it works. Fetching and building stay separate
steps, exactly as with `necc_real.fetch()`.

**It does not invent columns.** Rows are written in the same shape as the portal
export, so `agmarknet_export.parse()` is unchanged and the frozen contracts are
enforced by the same code path as before. A field the API does not supply
(Commodity_Code) is written empty rather than guessed.

The API key is read from DATA_GOV_API_KEY and is never written to disk or logged.
Register for one at https://data.gov.in/ — the free tier is ample here.
"""
from __future__ import annotations

import gzip
import io
import os
import time
from pathlib import Path

import httpx
import pandas as pd

from pipeline.ingest._common import RAW
from pipeline.ingest.agmarknet_export import TOWN_ALIASES, TOWNS, normalise_market

# data.gov.in silently stalls on the default python-httpx User-Agent: the request
# is accepted and then simply never answered, so it surfaces as ReadTimeout
# rather than a 403 and looks like a network fault. Any other UA is served in
# under a second. Measured: default httpx timed out at 15s on three attempts;
# "curl/8.7.1" and this string both returned 200 in 0.7-0.9s.
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; price-review/1.0)"}

RESOURCE = "9ef84268-d588-465a-a308-a864a43d0070"
URL = f"https://api.data.gov.in/resource/{RESOURCE}"
EXPORT = RAW / "agmarknet_real" / "vellore_export.csv.gz"

PAGE = 1000          # the API's own maximum
MAX_PAGES = 10

# Query by district, not by state: Tamil Nadu returns ~7,000 rows a day against
# ~520 for these three, and the rest are 500 km away.
#
# One district is not enough, and the reason is the 2019 bifurcation. The portal
# still files Thirupathur and Vaniyambadi under "Vellore", but it files Arcot --
# which is in the panel -- under "Ranipet", and it has a separate "Thirupathur"
# district too. Filtering on district=Vellore alone would silently drop markets
# the pipeline already models, and the loss would look like those markets simply
# having no trade that day.
DISTRICTS = ("Vellore", "Ranipet", "Thirupathur")

# The export's column order. Anything we write must match it exactly, or the
# concatenation below silently produces a ragged file.
COLUMNS = ["Arrival_Date", "Commodity", "Commodity_Code", "District", "Grade",
           "Market", "Max_Price", "Min_Price", "Modal_Price", "State", "Variety"]

# A row is the same observation if these match. The portal restates recent days
# on every call, so without this the file would grow by duplicates.
#
# NOT unique in the committed export: 38 rows there share a key with another,
# and they are real -- the same market reporting two lots of one commodity on one
# day at different prices. So this key can only ever be used to decide whether an
# *incoming* row is already present. Deduplicating the merged frame on it would
# quietly delete 19 rows of committed history on the first refresh.
KEY = ["Arrival_Date", "Market", "Commodity", "Variety", "Grade"]

# The API's field names have changed casing between versions; accept either.
FIELD_ALIASES = {
    "arrival_date": "Arrival_Date", "commodity": "Commodity",
    "district": "District", "grade": "Grade", "market": "Market",
    "max_price": "Max_Price", "min_price": "Min_Price",
    "modal_price": "Modal_Price", "state": "State", "variety": "Variety",
}


def api_key() -> str:
    key = os.environ.get("DATA_GOV_API_KEY", "").strip()
    if not key:
        raise SystemExit(
            "DATA_GOV_API_KEY is not set. Get a key from https://data.gov.in/ and\n"
            "  export DATA_GOV_API_KEY=...        (or set it in the service env)"
        )
    return key


def _known_market(name: str) -> bool:
    """True if this market resolves to a town the pipeline already models.

    Filtering on the market rather than on the District field is deliberate: the
    2019 bifurcation moved Ambur, Vaniyambadi and Gudiyatham into Tirupattur
    district and Arcot and Arakkonam into Ranipet, so a District == "Vellore"
    filter would quietly drop half the markets already in the panel.
    """
    try:
        normalise_market(name)
        return True
    except AssertionError:
        return False


def fetch(verbose: bool = True) -> pd.DataFrame:
    """Pull current daily prices for DISTRICTS, keep the markets we model."""
    log = print if verbose else (lambda *a, **k: None)
    key, rows = api_key(), []

    with httpx.Client(timeout=60, headers=HEADERS) as client:
      for district in DISTRICTS:
        empty_retries = 0
        page = -1
        while page < MAX_PAGES - 1:
            page += 1
            params = {"api-key": key, "format": "json",
                      "limit": PAGE, "offset": page * PAGE,
                      "filters[district]": district}
            # The endpoint is usually ~1.5s for a 1000-row page but occasionally
            # stalls. On a two-day schedule a transient timeout means two days of
            # prices lost for good, so retry rather than fail the run.
            for attempt in range(3):
                try:
                    r = client.get(URL, params=params)
                    break
                except httpx.TimeoutException:
                    if attempt == 2:
                        raise
                    log(f"    page {page + 1} timed out, retrying")
                    time.sleep(3 * (attempt + 1))
            if r.status_code == 403:
                raise SystemExit("data.gov.in rejected the key (403). Check DATA_GOV_API_KEY.")
            r.raise_for_status()
            body = r.json()
            batch = body.get("records", [])

            # An empty first page is ambiguous and must not be read as "this
            # district has no trade today". Under load the API answers 200 with
            # {"message": "No query was recieved", "records": []}, which is
            # indistinguishable from a real empty result unless you look at the
            # message. Treating it as end-of-data made a whole run report success
            # having fetched nothing at all -- and on a two-day schedule, a run
            # that silently fetches nothing is two days of prices lost.
            if page == 0 and not batch:
                msg = str(body.get("message", ""))
                if "no query" in msg.lower():
                    if empty_retries < 3:
                        empty_retries += 1
                        log(f"    {district}: '{msg}' - backing off and retrying")
                        time.sleep(5 * empty_retries)
                        page -= 1          # retry this page, not the next one
                        continue
                    raise SystemExit(
                        f"data.gov.in kept answering '{msg}' for {district}. "
                        "Usually rate limiting; try again in a few minutes."
                    )
                log(f"    {district}: no rows today")

            rows.extend(batch)
            log(f"    {district} page {page + 1}: {len(batch)} rows (total {len(rows)})")
            if len(batch) < PAGE:
                break
            time.sleep(0.5)          # courtesy to a free public API

    if not rows:
        return pd.DataFrame(columns=COLUMNS)

    df = pd.DataFrame(rows)
    df = df.rename(columns={c: FIELD_ALIASES.get(c.lower(), c) for c in df.columns})
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA
    df = df[COLUMNS]

    before = len(df)
    df = df[df["Market"].astype(str).str.strip().map(_known_market)]
    log(f"    {len(df)} of {before} rows are markets the panel already models")

    # The API returns dd/mm/YYYY like the export, but has been seen to return
    # ISO. Normalise to the export's format so the two files concatenate.
    parsed = pd.to_datetime(df["Arrival_Date"], format="mixed", dayfirst=True,
                            errors="coerce")
    df = df[parsed.notna()]
    df["Arrival_Date"] = parsed[parsed.notna()].dt.strftime("%d/%m/%Y")

    for col in ("Min_Price", "Max_Price", "Modal_Price"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df[df["Modal_Price"] > 0]


def merge(new: pd.DataFrame, export: Path = EXPORT, verbose: bool = True) -> dict:
    """Append new rows to the committed export. Returns what changed.

    Appends *text*, and never round-trips the existing file through pandas.
    Reading and rewriting it looks harmless and is not: `read_csv` types the
    price columns as float64 because some rows carry decimals, so every
    committed "1300" comes back as "1300.0" and a four-row update rewrites all
    246,882 lines. The values would survive; the file would churn completely on
    every refresh, and the history would no longer be the file that was reviewed.
    """
    log = print if verbose else (lambda *a, **k: None)

    old_text = gzip.decompress(export.read_bytes()).decode()
    if not old_text.endswith("\n"):
        old_text += "\n"

    old = pd.read_csv(io.StringIO(old_text))       # read-only, for the key set
    before = len(old)
    seen = set(map(tuple, old[KEY].astype("string").fillna("").to_numpy()))

    incoming = new[COLUMNS].drop_duplicates(subset=KEY)
    keys = map(tuple, incoming[KEY].astype("string").fillna("").to_numpy())
    fresh = incoming[[k not in seen for k in keys]]

    if fresh.empty:
        log("    nothing new")
        return {"added": 0, "rows": before, "through": _through(old["Arrival_Date"])}

    appended = fresh.to_csv(index=False, header=False, lineterminator="\n")

    # Write to a temp file and replace, so an interrupted run cannot leave a
    # truncated export where the committed history used to be.
    tmp = export.with_suffix(".tmp.gz")
    tmp.write_bytes(gzip.compress((old_text + appended).encode(), 9))
    tmp.replace(export)

    through = _through(pd.concat([old["Arrival_Date"], fresh["Arrival_Date"]]))
    log(f"    +{len(fresh)} rows -> {before + len(fresh)} total, through {through}")
    return {"added": len(fresh), "rows": before + len(fresh), "through": through}


def _through(dates: pd.Series) -> str:
    d = pd.to_datetime(dates, format="%d/%m/%Y", errors="coerce").max()
    return "unknown" if pd.isna(d) else f"{d:%Y-%m-%d}"
