"""Flag -> case file.

Two jobs:

1.  `narrate` renders a flag's finding as a sentence. It is a template, never an
    LLM: it has to be deterministic because it is read aloud on stage and because
    an enforcement document cannot say something different each time it is built.

2.  `build_case` renders the printable case file — reference rate with citation,
    observed values with provenance and tier mix, residual, peer comparison,
    duration, and a plain-language account of what the detector measured.

Language discipline: these screens prioritise investigation. Nothing here states
that any party has manipulated prices. The phrase is "flagged for investigation",
everywhere, without exception.
"""
from __future__ import annotations

from typing import Any

from pipeline.contracts import json_safe

DETECTOR_LABELS = {
    "variance_collapse": "Prices stopped varying between sellers",
    "cost_correlation": "Prices track each other, not costs",
    "persistence": "Sustained gap above the reference rate",
    "quantisation": "Fares cluster at round values",
}

DETECTOR_EXPLANATIONS = {
    "variance_collapse": (
        "Independent sellers facing the same costs still disagree on price, because "
        "they buy at different times and carry different stock. This measure is the "
        "day-to-day spread of prices across sellers in one location. A spread that "
        "stays near zero for weeks is what a single repeated price looks like."),
    "cost_correlation": (
        "A competitive price moves when costs move. This measure compares how "
        "closely each seller's price follows its neighbours' prices against how "
        "closely it follows the published reference rate. A price that follows the "
        "neighbours and ignores the reference rate is the pattern this system exists "
        "to surface."),
    "persistence": (
        "Any location can sit above its expected range for a day. This measure counts "
        "consecutive days above the range, and reports which neighbouring locations "
        "stayed inside it over the same period. Named in-band neighbours are what "
        "distinguishes a local pricing pattern from a district-wide supply shock."),
    "quantisation": (
        "A metered fare varies continuously with distance. This measure reports the "
        "share of quoted fares landing on round multiples, together with how much of "
        "the fare is explained by distance at all. Round numbers with weak distance "
        "response describe a fare that was set rather than measured."),
}

BASIS_LABEL = {
    "model": "Modelled competitive range from wholesale mandi prices",
    "necc": "NECC declared daily egg rate",
    "gazette": "Notified autorickshaw fare schedule",
}

UNIT_LABEL = {"per_kg": "per kg", "per_piece": "per piece",
              "per_ride": "per ride", "per_km": "per km"}

TIER_LABEL = {3: "Priority", 2: "Review", 1: "Insufficient evidence"}
TIER_SOURCE_LABEL = {"A": "authoritative", "B": "commercial listing", "C": "field report"}

# A flag resting only on a handful of field reports is not an inspection target.
# Data-quality defence, anti-gaming defence and defamation defence, all at once.
MIN_TIER_C_SELLERS = 3


def _pct_above(observed_median: float, expected_rate: float) -> float:
    if not expected_rate:
        return 0.0
    return (observed_median / expected_rate - 1.0) * 100.0


def _peer_phrase(peers: list[str]) -> str:
    if not peers:
        return "no comparable peer location stayed in-band"
    if len(peers) == 1:
        return f"peer location {pretty_location(peers[0])} remained in-band"
    named = ", ".join(pretty_location(p) for p in peers[:2])
    extra = f" and {len(peers) - 2} other" + ("s" if len(peers) - 2 > 1 else "") \
        if len(peers) > 2 else ""
    return f"peer locations {named}{extra} remained in-band"


def pretty_location(location: str) -> str:
    """Market ids are <town>_apmc / <town>_sandhai; zones are vellore_<zone>.

    Stripping the "vellore_" prefix first turns `vellore_apmc` into "Apmc" and
    loses the town, so a case file for the district's principal mandi named a
    market that does not exist. Suffix first; prefix only for the zones, which
    carry no suffix. Mirrors data.js prettyLocation and engine.report_places --
    all three are read off the same printed page during a demo, and disagreeing
    about a market's name in a case file is worse than an ugly name.
    """
    if location.endswith("_sandhai"):
        return f"{location[: -len('_sandhai')].replace('_', ' ').title()} Sandhai"
    if location.endswith("_apmc"):
        return f"{location[: -len('_apmc')].replace('_', ' ').title()} APMC"
    return location.replace("vellore_", "").replace("_", " ").title()


ITEM_LABELS: dict[str, str] = {}


def set_item_labels(labels: dict[str, str]) -> None:
    """Display names, supplied by the ingest layer from the source data."""
    ITEM_LABELS.clear()
    ITEM_LABELS.update(labels)


def pretty_item(item: str) -> str:
    return ITEM_LABELS.get(item, item.replace("_", " ").title())


def narrate(flag: dict[str, Any]) -> str:
    """Deterministic template. No LLM, no randomness, no free text."""
    stat = flag["statistic"]
    obs, exp = flag["observed"], flag["expected"]
    pct = _pct_above(obs["median"], exp["rate"])
    peers = _peer_phrase(flag["peers_in_band"])
    days = (pd_days(flag["window"]))
    det = flag["detector"]

    if det == "variance_collapse":
        return (f"Prices from {obs['n']} observations across the location stayed within "
                f"{stat['value'] * 100:.1f}% of one another for {days} days, against a "
                f"{stat['threshold'] * 100:.1f}% threshold; median {pct:+.0f}% relative to "
                f"the reference rate while {peers}.")
    if det == "cost_correlation":
        return (f"Listed prices follow one another (correlation "
                f"{stat.get('peer_correlation', float('nan')):.2f}) far more closely than "
                f"they follow the reference rate (correlation "
                f"{stat.get('cost_correlation', float('nan')):.2f}); median {pct:+.0f}% "
                f"relative to the reference rate while {peers}.")
    if det == "persistence":
        return (f"Prices stayed above the expected range for {stat['value']} consecutive "
                f"days; median {pct:+.0f}% relative to the reference rate while {peers}.")
    if det == "quantisation":
        return (f"Quoted fares cluster at round values "
                f"({stat['value'] * 100:.0f}% of quotes) with weak distance sensitivity "
                f"(R² {stat.get('distance_r2', float('nan')):.2f}); median {pct:+.0f}% "
                f"relative to the notified rate while {peers}.")
    raise AssertionError(f"no narrative template for detector {det!r}")


def pd_days(window: dict[str, str]) -> int:
    from datetime import date
    a = date.fromisoformat(window["start"])
    b = date.fromisoformat(window["end"])
    return (b - a).days + 1


def apply_evidence_floor(flag: dict[str, Any], distinct_sellers: int) -> dict[str, Any]:
    """Downgrade a flag that rests only on a few field reports.

    Enforced here rather than left as a convention: a tier-C-only flag with fewer
    than three independent sellers is not an inspection target, it is a rumour.
    """
    mix = flag["observed"]["tier_mix"]
    tier_c_only = set(mix) == {"C"}
    if tier_c_only and distinct_sellers < MIN_TIER_C_SELLERS:
        flag = dict(flag, tier=1)
        flag["evidence_floor"] = (
            f"Downgraded: all {flag['observed']['n']} observations are field reports "
            f"from {distinct_sellers} independent localit"
            f"{'y' if distinct_sellers == 1 else 'ies'}; "
            f"{MIN_TIER_C_SELLERS} required. Nearby reports quoting the same price "
            f"are counted once.")
    return flag


def in_queue(flag: dict[str, Any]) -> bool:
    return flag["tier"] >= 2


def build_case(flag: dict[str, Any], series: list[dict] | None = None) -> dict[str, Any]:
    """Render one flag into the printable case-file document."""
    obs, exp = flag["observed"], flag["expected"]
    basis = flag.get("basis", "model")
    unit = UNIT_LABEL.get(exp["unit"], exp["unit"])
    pct = _pct_above(obs["median"], exp["rate"])

    case = {
        "flag_id": flag["flag_id"],
        "title": f"{pretty_item(flag['item'])} — {pretty_location(flag['location'])}",
        "status": "Flagged for investigation",
        "tier": flag["tier"],
        "tier_label": TIER_LABEL[flag["tier"]],
        "finding": DETECTOR_LABELS[flag["detector"]],
        "narrative": flag["narrative"],
        "window": flag["window"],
        "duration_days": pd_days(flag["window"]),
        "reference": {
            "basis": BASIS_LABEL[basis],
            "rate": exp["rate"],
            "band": exp["band"],
            "unit": unit,
            "citation": flag.get("citation", ""),
        },
        "observed": {
            "median": obs["median"],
            "unit": unit,
            "n": obs["n"],
            "pct_vs_reference": round(pct, 1),
            "provenance": [
                {"tier": t, "label": TIER_SOURCE_LABEL[t], "n": n}
                for t, n in sorted(obs["tier_mix"].items())
            ],
            "distinct_localities": flag.get("distinct_sellers"),
        },
        "measure": {
            "detector": flag["detector"],
            "name": flag["statistic"]["name"],
            "value": flag["statistic"]["value"],
            "threshold": flag["statistic"]["threshold"],
            "extra": {k: v for k, v in flag["statistic"].items()
                      if k not in {"name", "value", "threshold"}},
            "explanation": DETECTOR_EXPLANATIONS[flag["detector"]],
        },
        "residual_sd": flag["residual_sd"],
        "peers_in_band": [pretty_location(p) for p in flag["peers_in_band"]],
        "series": series or [],
        "caveat": (
            "This document records a statistical pattern flagged for investigation. "
            "It does not establish that any party has set prices unlawfully. Sellers "
            "are identified only by pseudonymous location codes."),
    }
    if "evidence_floor" in flag:
        case["evidence_floor"] = flag["evidence_floor"]
    return json_safe(case)
