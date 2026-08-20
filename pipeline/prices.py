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
        "source": "Agmarknet daily mandi prices, Government of India",
        "min_markets": MIN_MARKETS,
        "items": rows,
    }
