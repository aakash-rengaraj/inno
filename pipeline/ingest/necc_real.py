"""NECC declared egg rates, pulled from e2necc.com.

`necc.coop` does not resolve; the live site is e2necc.com. The daily-rate page is
a plain POST form (`ddlMonth`, `ddlYear`, `rblReportType`) with no captcha and no
VIEWSTATE — ironically the pattern CLAUDE.md 5.1 expected of Agmarknet.

`fetch()` walks a month range and writes one tidy CSV. Run it once, commit the
output, never call it again: the demo path must not touch the network.

IMPORTANT — NECC publishes this clarification alongside the rates, and requires
anyone disseminating them to carry it. It is reproduced in `CITATION_NOTE` and
belongs in any case file that cites NECC:

    The daily egg prices suggested by NECC are merely suggestive and not
    mandatory, and are published solely for the reference and information of the
    trade and industry. NECC does not enforce compliance with them.

That constrains our language: a price above the NECC rate is a deviation from a
published benchmark, never a breach of a mandated rate.
"""
from __future__ import annotations

import re
import time
from datetime import date

import pandas as pd

from pipeline.contracts import validate_observations, validate_references
from pipeline.ingest._common import RAW, blank_frame, per_hundred_to_each

URL = "https://e2necc.com/home/eggprice"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; price-review/1.0)"}

CITATION = ("National Egg Coordination Committee — suggested daily egg rate, "
            "Namakkal zone (suggestive, not mandatory)")
CITATION_NOTE = ("NECC suggested egg prices are merely suggestive and not mandatory, "
                 "published for the reference and information of the trade. NECC does "
                 "not enforce compliance with them.")

# The zone that actually supplies northern Tamil Nadu.
ZONE = "Namakkal"

# Zones are price-setting regions, not addresses; the coordinate is the zone
# centre and exists only to satisfy the Observation contract.
ZONE_COORDS = {"Namakkal": (11.2189, 78.1674), "Chennai": (13.0827, 80.2707)}

RAW_PATH = RAW / "necc_real" / "necc_daily.csv"


def _month_table(month: int, year: int) -> dict[str, list[str]]:
    import httpx
    body = {"rblReportType": "DailyReport", "ddlMonth": f"{month:02d}",
            "ddlYear": str(year), "btnReport": "View Report"}
    r = httpx.post(URL, data=body, timeout=30, verify=False, headers=HEADERS)
    r.raise_for_status()
    out = {}
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", r.text, re.S):
        cells = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", c)).replace("&nbsp;", " ").strip()
                 for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
        if len(cells) > 15 and cells[0]:
            out[cells[0]] = cells[1:]
    return out


def fetch(start: tuple[int, int] = (2025, 1), end: tuple[int, int] = (2026, 8)) -> None:
    """Walk months and write data/raw/necc_real/necc_daily.csv. Offline step."""
    rows = []
    y, m = start
    while (y, m) <= end:
        table = _month_table(m, y)
        for zone, days in table.items():
            if zone not in ZONE_COORDS:
                continue
            for i, value in enumerate(days, start=1):
                value = value.strip()
                if not value or value in {"-", "0"} or not value.replace(".", "").isdigit():
                    continue
                try:
                    d = date(y, m, i)
                except ValueError:
                    continue  # day column past the end of a short month
                rows.append({"date": d.isoformat(), "zone": zone,
                             "rate_per_100": float(value)})
        print(f"  {y}-{m:02d}: {len(table)} zones")
        time.sleep(0.6)
        m += 1
        if m > 12:
            m, y = 1, y + 1

    RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows).drop_duplicates(subset=["date", "zone"]).sort_values(["date", "zone"])
    df.to_csv(RAW_PATH, index=False)
    print(f"  -> {RAW_PATH} ({len(df)} rows)")


def _raw() -> pd.DataFrame:
    df = pd.read_csv(RAW_PATH)
    return df[df["zone"] == ZONE].copy()


def parse() -> pd.DataFrame:
    """The suggested rate, carried as a tier-A observation so charts can draw it."""
    raw = _raw()
    lat, lng = ZONE_COORDS[ZONE]
    n = len(raw)
    df = pd.DataFrame({
        "item": "egg_table", "location": "necc_declared",
        "lat": lat, "lng": lng, "date": raw["date"],
        "price": per_hundred_to_each(raw["rate_per_100"]),
        "unit": "per_piece", "seller_id": "necc_declared",
        "source": "necc", "tier": "A", **blank_frame(n),
    })
    return validate_observations(df, "necc_real")


def references(locations: list[str]) -> pd.DataFrame:
    raw = _raw()
    frames = [pd.DataFrame({
        "item": "egg_table", "location": loc, "date": raw["date"],
        "rate": per_hundred_to_each(raw["rate_per_100"]), "unit": "per_piece",
        "source": "necc", "citation": CITATION,
    }) for loc in locations]
    return validate_references(pd.concat(frames, ignore_index=True), "necc_real")


if __name__ == "__main__":
    fetch()
