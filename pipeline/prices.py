"""Daily commodity price ranges for the public page.

What a citizen actually wants to know is narrow: what did this cost in the
market today, and what is normal. So this carries one row per commodity and
nothing else -- low, typical, high, and how many markets that rests on.

Three things it deliberately does not carry, because the public bundle must not
be able to reconstruct the enforcement view:

  * **No market names.** A price attached to a named market, next to a queue of
    flagged markets, is a way of pointing at somebody. The range is across the
    district; which market sat at either end is an enforcement detail.
  * **No modelled band.** The expected range is what the detectors trigger
    against. Publishing it tells anyone minded to manipulate a price exactly how
    far they may go before anything fires.
  * **No flags, tiers, detectors or thresholds.**

Wholesale only, and labelled as such on the page. Mixing the mandi's wholesale
prices with retail listings would produce a "range" spanning two different
markets in the economic sense, and a reader would reasonably assume the low end
was a price they could go and pay.
"""
from __future__ import annotations

import pandas as pd

# A range needs something to range over. Two markets is a pair of numbers, not a
# distribution, and one market's price presented as a district range is
# misleading -- so those commodities are simply not listed.
MIN_MARKETS = 3

# Eggs and autorickshaw fares are not mandi commodities and do not belong in the
# same table: eggs are priced per piece against a declared national rate, and a
# fare is a function of distance rather than a per-kilo price. Putting them in
# the commodity list would have meant either inventing a "per kg" for them or
# leaving a column blank on every row.
#
# Both carry a published reference the public is entitled to see -- the NECC
# declared rate and the TN gazetted fare schedule -- so each block states the
# reference alongside what people are actually paying.
FARE_DISTANCES = (2.0, 3.0, 5.0, 8.0, 10.0)
RETAIL_WINDOW_DAYS = 30


def _range(prices: pd.Series) -> dict | None:
    """Low / typical / high, or nothing if there is too little to describe."""
    p = prices.dropna()
    if len(p) < 3:
        return None
    return {"low": round(float(p.min()), 2),
            "typical": round(float(p.median()), 2),
            "high": round(float(p.max()), 2),
            "n": int(len(p))}


def eggs(obs: pd.DataFrame) -> dict | None:
    """Declared rate against what shops are charging."""
    e = obs[obs["item"] == "egg_table"]
    if e.empty:
        return None

    declared = e[e["source"] == "necc"]
    if declared.empty:
        return None
    day = str(declared["date"].max())
    rate = float(declared[declared["date"] == day]["price"].median())

    cutoff = (pd.to_datetime(e["date"].max())
              - pd.Timedelta(days=RETAIL_WINDOW_DAYS)).strftime("%Y-%m-%d")
    shop = e[(e["source"] != "necc") & (e["date"] >= cutoff)]

    return {
        "date": day,
        "unit": "per_piece",
        "declared": round(rate, 2),
        "observed": _range(shop["price"]),
        "window_days": RETAIL_WINDOW_DAYS,
        # NECC requires this alongside any dissemination of its rates, and it is
        # what stops a price above the rate reading as a breach. The page renders
        # its own translated copy of it (i18n `eggsNote`); this stays as the
        # record of what the source requires, and travels with the API response.
        "note": ("The NECC rate is suggestive, not mandatory. Shops add their own "
                 "margin, so a higher shop price is normal."),
        "source": "National Egg Coordination Committee, Namakkal zone",
    }


def autos(obs: pd.DataFrame) -> dict | None:
    """Notified fare per distance, against what riders report paying."""
    from pipeline.ingest import gazette

    a = obs[obs["item"] == "auto_ride"]
    if a.empty:
        return None
    sched = gazette.schedule()

    cutoff = (pd.to_datetime(a["date"].max())
              - pd.Timedelta(days=RETAIL_WINDOW_DAYS)).strftime("%Y-%m-%d")
    recent = a[a["date"] >= cutoff]

    rows = []
    for km in FARE_DISTANCES:
        # rides within 20% of this distance, so the comparison is like for like
        near = recent[(recent["distance_km"] >= km * 0.8)
                      & (recent["distance_km"] <= km * 1.2)]
        rows.append({"km": km,
                     "notified": round(float(gazette.fare_for(km, sched)), 2),
                     "observed": _range(near["price"])})

    return {
        "date": str(a["date"].max()),
        "unit": "per_ride",
        "rows": rows,
        "window_days": RETAIL_WINDOW_DAYS,
        "note": ("The notified fare is the regulated rate for the distance. "
                 "Waiting time and night trips are charged extra."),
        "source": str(sched["citation"]),
    }


def build(obs: pd.DataFrame, labels: dict[str, str] | None = None) -> dict:
    """Latest day's wholesale range per commodity. Public-safe by construction."""
    mandi = obs[obs["source"] == "agmarknet"]
    if mandi.empty:
        return {"date": None, "unit": "per_kg", "items": []}

    day = str(mandi["date"].max())
    today = mandi[mandi["date"] == day]

    labels = labels or {}
    rows = []
    for item, g in today.groupby("item", observed=True):
        markets = int(g["location"].nunique())
        if markets < MIN_MARKETS:
            continue
        rows.append({
            "item": str(item),
            "label": labels.get(str(item), str(item).replace("_", " ").title()),
            "low": round(float(g["price"].min()), 2),
            "typical": round(float(g["price"].median()), 2),
            "high": round(float(g["price"].max()), 2),
            "markets": markets,
        })

    rows.sort(key=lambda r: r["label"].lower())
    return {
        "date": day,
        "unit": "per_kg",
        "basis": "wholesale",
        "eggs": eggs(obs),
        "autos": autos(obs),
        "source": "Agmarknet daily mandi prices, Government of India",
        "min_markets": MIN_MARKETS,
        "items": rows,
    }
