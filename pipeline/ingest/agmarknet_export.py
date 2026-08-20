"""Real Agmarknet portal export (Vellore district).

The portal's CSV differs from the report format SPEC.md 5.1 described, and in
two ways that matter:

  * **No arrivals column.** Section 5.1 calls arrivals load-bearing, and it is
    right: without them the model cannot separate scarcity from manipulation.
    Every row here gets `arrivals = NaN`, and the supply features that carry
    ~78% of the fitted model's signal are simply unavailable. Pull the portal's
    separate arrivals report to restore them.
  * **Whatever date range was requested.** The current export spans 2020-04 to
    2026-08, but is sparse before 2024-06 (~250 rows/month against ~8,000
    after). Rows without enough same-day peers drop out on their own, since the
    band is defined against a peer median.

Columns: Arrival_Date, Commodity, Commodity_Code, District, Grade, Market,
Max_Price, Min_Price, Modal_Price, State, Variety. Prices are Rs/quintal.
"""
from __future__ import annotations

import re

import pandas as pd

from pipeline.contracts import validate_observations
from pipeline.ingest._common import RAW, blank_frame, pseudonym, quintal_to_kg

# Canonical ids for the markets that actually appear in the export.
# COORDINATES ARE APPROXIMATE — good enough to group by locality, but verify
# before anything is plotted on a map or used for a distance calculation.
# Town coordinates. APPROXIMATE — good enough to group by locality, but verify
# before anything is plotted on a map or used for a distance calculation.
TOWNS = {
    "vellore":         (12.9165, 79.1325),
    "katpadi":         (12.9698, 79.1325),
    "gudiyatham":      (12.9450, 78.8700),
    "thirupathur":     (12.4950, 78.5700),
    "pallikonda":      (12.9200, 78.9100),
    "perampet":        (12.8500, 79.0500),
    "kahithapattarai": (12.8800, 79.2000),
    "ammoor":          (12.8800, 79.2500),
    "vaniyambadi":     (12.6820, 78.6200),
    "ambur":           (12.7900, 78.7200),
    "arcot":           (12.9060, 79.3200),
    "arakkonam":       (13.0830, 79.6700),
    "kalavai":         (12.7700, 79.4000),
    "kaveripakkam":    (12.9200, 79.4300),
    "thimiri":         (12.8300, 79.3000),
}

# Spelling variants seen in the export.
TOWN_ALIASES = {"arkonam": "arakkonam", "tirupathur": "thirupathur",
                "tirupattur": "thirupathur", "amoor": "ammoor"}

_SANDHAI = re.compile(r"uzhavar\s*(sandhai|santhai)", re.I)


def normalise_market(name: str) -> tuple[str, float, float]:
    """One physical market, one id.

    The export spells the same market several ways — "Vellore" and "Vellore
    APMC"; "Katpadi (Uzhavar Sandhai )", "Katpadi(Uzhavar Santhai)" and
    "Katpadi (Uzhavar Sandhai ) APMC". Left alone each variant becomes a separate
    location, which splits a market's time series in half and lets one market
    appear in the queue several times over.

    The regulated market (APMC) and the farmers' market (Uzhavar Sandhai) in the
    same town are genuinely different venues and stay separate.
    """
    raw = name.strip()
    kind = "sandhai" if _SANDHAI.search(raw) else "apmc"

    town = _SANDHAI.sub(" ", raw)
    town = re.sub(r"\bAPMC\b", " ", town, flags=re.I)
    town = re.sub(r"[()\-]", " ", town)
    town = re.sub(r"\s+", " ", town).strip().lower()
    town = TOWN_ALIASES.get(town, town)

    assert town in TOWNS, f"unmapped market town {town!r} (from {name!r})"
    lat, lng = TOWNS[town]
    return f"{town}_{kind}", lat, lng


# Section 8 caps the demo at three commodities. The band model may still be
# fitted on the full cross-section — it learns how far a market may sit from its
# peers, which is commodity-agnostic — but only these are shown.
DEMO_COMMODITIES = {"Tomato": "tomato", "Onion": "onion", "Potato": "potato"}

REJECTED: dict[str, int] = {}

# Markets excluded from the district panel entirely — not merely hidden from the
# queue. An excluded market must also leave the peer sets and the training data,
# or it keeps shaping the expected band for everyone else.
#
# Thirupathur sits ~50km south of the rest and was administratively separated
# into Tirupattur district in 2019, though this export still labels it Vellore.
# A structurally separate market carries legitimately different prices, and it
# was producing repeat flags across unrelated commodities — one market looking
# like four findings.
EXCLUDED_MARKETS = {"thirupathur_apmc", "thirupathur_sandhai"}


def canonical_item(name: str) -> str:
    """Any commodity -> a snake_case id the Observation contract accepts.

    Agmarknet commodity names carry commas, slashes, brackets and stray dots
    ("Sesamum(Sesame,Gingelly,Til)"), so anything outside [a-z0-9_] goes.
    """
    slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower())
    return re.sub(r"_+", "_", slug).strip("_")


def fetch() -> None:
    raise NotImplementedError(
        "Exported by hand from the Agmarknet portal (its API is captcha-gated) "
        "and committed to data/raw/agmarknet_real/."
    )


def parse(demo_only: bool = True) -> pd.DataFrame:
    # gzipped: the full history is ~24MB of CSV, which is unfriendly in a repo.
    # pandas reads .gz transparently.
    path = RAW / "agmarknet_real" / "vellore_export.csv.gz"
    raw = pd.read_csv(path, compression="gzip")

    # A handful of real rows carry a zero modal price (31 of ~247k). They are
    # missing data reported as a number, not a free commodity, and the contract
    # rightly refuses them.
    before = len(raw)
    raw = raw[raw["Modal_Price"] > 0]
    REJECTED["non_positive_price"] = before - len(raw)

    resolved = {m: normalise_market(m) for m in raw["Market"].str.strip().unique()}
    market_id = raw["Market"].str.strip().map(lambda m: resolved[m][0])

    keep_market = ~market_id.isin(EXCLUDED_MARKETS)
    raw, market_id = raw[keep_market], market_id[keep_market]

    commodity = raw["Commodity"].str.strip()
    if demo_only:
        keep = commodity.isin(DEMO_COMMODITIES)
        raw, market, commodity = raw[keep], market[keep], commodity[keep]
        item = commodity.map(DEMO_COMMODITIES)
    else:
        item = commodity.map(canonical_item)

    n = len(raw)
    df = pd.DataFrame({
        "item": item.to_numpy(),
        "location": market_id.to_numpy(),
        "lat": [TOWNS[m.rsplit("_", 1)[0]][0] for m in market_id],
        "lng": [TOWNS[m.rsplit("_", 1)[0]][1] for m in market_id],
        "date": pd.to_datetime(raw["Arrival_Date"], format="%d/%m/%Y")
                  .dt.strftime("%Y-%m-%d").to_numpy(),
        "price": quintal_to_kg(raw["Modal_Price"]).to_numpy(),
        "unit": "per_kg",
        "seller_id": [pseudonym("mandi", m) for m in market_id],
        "source": "agmarknet",
        "tier": "A",
        **blank_frame(n),
    })
    # arrivals are absent from this export; the contract allows NaN, the model
    # does not benefit from it
    return validate_observations(df, "agmarknet_export")


def references(obs: pd.DataFrame) -> pd.DataFrame:
    """Wholesale modal price is the cost reference for retail in the same town."""
    from pipeline.contracts import validate_references

    src = obs[obs["source"] == "agmarknet"]
    refs = pd.DataFrame({
        "item": src["item"], "location": src["location"], "date": src["date"],
        "rate": src["price"], "unit": src["unit"],
        "source": "agmarknet_wholesale",
        "citation": ("Agmarknet daily mandi report - Directorate of Marketing & "
                     "Inspection, modal wholesale price, Vellore district"),
    }).reset_index(drop=True)
    return validate_references(refs, "agmarknet_export")


def display_labels() -> dict[str, str]:
    """canonical item id -> the name Agmarknet actually prints.

    `canonical_item` flattens "Mint(Pudina)" to `mint_pudina`, and title-casing
    that back gives "Mint Pudina". An enforcement document should carry the
    source's own wording, so the original is kept alongside the id.
    """
    path = RAW / "agmarknet_real" / "vellore_export.csv.gz"
    names = pd.read_csv(path, compression="gzip", usecols=["Commodity"])
    out: dict[str, str] = {}
    for name in names["Commodity"].dropna().str.strip().unique():
        out.setdefault(canonical_item(name), name)
    return out
