"""Real Agmarknet portal export (Vellore district).

The portal's CSV differs from the report format CLAUDE.md 5.1 described, and in
two ways that matter:

  * **No arrivals column.** Section 5.1 calls arrivals load-bearing, and it is
    right: without them the model cannot separate scarcity from manipulation.
    Every row here gets `arrivals = NaN`, and the supply features that carry
    ~78% of the fitted model's signal are simply unavailable. Pull the portal's
    separate arrivals report to restore them.
  * **Whatever date range was requested.** The current export covers 66 days
    (2026-06-15 to 2026-08-19), which is enough for cost-correlation and
    persistence but not for any seasonal feature.

Columns: Arrival_Date, Commodity, Commodity_Code, District, Grade, Market,
Max_Price, Min_Price, Modal_Price, State, Variety. Prices are Rs/quintal.
"""
from __future__ import annotations

import pandas as pd

from pipeline.contracts import validate_observations
from pipeline.ingest._common import RAW, blank_frame, pseudonym, quintal_to_kg

# Canonical ids for the markets that actually appear in the export.
# COORDINATES ARE APPROXIMATE — good enough to group by locality, but verify
# before anything is plotted on a map or used for a distance calculation.
MARKETS = {
    "Vellore APMC":                      ("vellore_apmc",         12.9165, 79.1325),
    "Katpadi APMC":                      ("katpadi_apmc",         12.9698, 79.1325),
    "Katpadi (Uzhavar Sandhai )":        ("katpadi_sandhai",      12.9698, 79.1400),
    "Gudiyatham APMC":                   ("gudiyatham_apmc",      12.9450, 78.8700),
    "Gudiyatham(Uzhavar Sandhai )":      ("gudiyatham_sandhai",   12.9470, 78.8760),
    "Thirupathur APMC":                  ("thirupathur_apmc",     12.4950, 78.5700),
    "Pallikonda(Uzhavar Sandhai)":       ("pallikonda_sandhai",   12.9200, 78.9100),
    "Perampet(Uzhavar Sandhai)":         ("perampet_sandhai",     12.8500, 79.0500),
    "Kahithapattarai(Uzhavar Sandhai )": ("kahithapattarai_sandhai", 12.8800, 79.2000),
    "Ammoor APMC":                       ("ammoor_apmc",          12.8800, 79.2500),
    "Vaniyambadi APMC":                  ("vaniyambadi_apmc",     12.6820, 78.6200),
    "Ambur APMC":                        ("ambur_apmc",           12.7900, 78.7200),
    "Arcot APMC":                        ("arcot_apmc",           12.9060, 79.3200),
    "Kalavai APMC":                      ("kalavai_apmc",         12.7700, 79.4000),
    "Kaveripakkam APMC":                 ("kaveripakkam_apmc",    12.9200, 79.4300),
}

# Section 8 caps the demo at three commodities. The band model may still be
# fitted on the full cross-section — it learns how far a market may sit from its
# peers, which is commodity-agnostic — but only these are shown.
DEMO_COMMODITIES = {"Tomato": "tomato", "Onion": "onion", "Potato": "potato"}


def canonical_item(name: str) -> str:
    """Any commodity -> a snake_case id the Observation contract accepts."""
    return (name.lower().replace("(", "_").replace(")", "").replace("-", "_")
            .replace(".", "").replace("/", "_").replace(" ", "_")
            .replace("__", "_").strip("_"))


def fetch() -> None:
    raise NotImplementedError(
        "Exported by hand from the Agmarknet portal (its API is captcha-gated) "
        "and committed to data/raw/agmarknet_real/."
    )


def parse(demo_only: bool = True) -> pd.DataFrame:
    path = RAW / "agmarknet_real" / "vellore_export.csv"
    raw = pd.read_csv(path)

    market = raw["Market"].str.strip()
    unknown = sorted(set(market) - set(MARKETS))
    assert not unknown, f"unmapped market(s) in {path.name}: {unknown}"

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
        "location": [MARKETS[m][0] for m in market],
        "lat": [MARKETS[m][1] for m in market],
        "lng": [MARKETS[m][2] for m in market],
        "date": pd.to_datetime(raw["Arrival_Date"], format="%d/%m/%Y")
                  .dt.strftime("%Y-%m-%d").to_numpy(),
        "price": quintal_to_kg(raw["Modal_Price"]).to_numpy(),
        "unit": "per_kg",
        "seller_id": [pseudonym("mandi", MARKETS[m][0]) for m in market],
        "source": "agmarknet",
        "tier": "A",
        **blank_frame(n),
    })
    # arrivals are absent from this export; the contract allows NaN, the model
    # does not benefit from it
    return validate_observations(df, "agmarknet_export")
