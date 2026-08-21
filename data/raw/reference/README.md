# Reference-rate source material

**Committed by hand. Nothing here is generated.** `citation` strings are copied
verbatim into case files, so a wrong string here becomes a wrong citation in a
document that looks like an enforcement record.

## tn_auto_fare.json

Autorickshaw fares in Tamil Nadu have two numbers, and conflating them is the
mistake this file exists to prevent.

| | minimum | per km after | authority |
|---|---|---|---|
| **statutory** | ₹25 / 1.8 km | ₹12 | announced August 2013, **unrevised for 13 years** |
| **prevailing** | ₹50 / 1.8 km | ₹18 | declared by drivers' unions, in force from 1 Feb 2025 — **not a government order** |

`benchmark` selects which one the pipeline measures against. It is set to
`prevailing`, because a 2013 rate is not a fair yardstick for a 2026 ride: the
gap against it is mostly thirteen years of inflation, and a detector fed that
rate would flag every honest driver in the district.

The prevailing rate is **not law**, and a case file citing it must say so. It is
what riders are actually quoted against, which makes it the honest comparison —
but a fare above it is a deviation from a trade-declared rate, never a breach of
a notified one.

A revision is pending: the State Transport Authority forwarded a proposal to the
Home Department in July 2026, with unions seeking a ₹70 minimum. **When that
order is issued, replace `prevailing` with it and set `benchmark` to the new
block** — at that point the benchmark becomes law and the language in
`pipeline/cases.py` can harden accordingly.

Sources, August 2026:

- <https://www.dtnext.in/news/tamilnadu/auto-rickshaw-fares-to-increase-in-tamil-nadu-from-february-1-818862>
- <https://www.prokerala.com/news/articles/a1796092.html>

## necc_citation.txt

NECC publishes a *suggested* daily egg rate and requires the suggestive-not-
mandatory clarification to travel with it. See `pipeline/ingest/necc_real.py`.
