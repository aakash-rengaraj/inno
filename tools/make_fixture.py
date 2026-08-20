"""Generate SYNTHETIC raw files in the shape the real upstream sources emit.

This exists so the pipeline, detectors and demo can be built and rehearsed
before/without live scrape output. Every file it writes lands in /data/raw and
is deliberately in the *upstream* format, so the ingest parsers do real work and
can be pointed at genuine scrape output later with no code change.

Run:  python -m tools.make_fixture
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np

RAW = Path("data/raw")
RNG = np.random.default_rng(20260819)

START = date(2025, 1, 1)
END = date(2026, 8, 10)
DEMO_START = date(2026, 5, 1)

DAYS = [START + timedelta(days=i) for i in range((END - START).days + 1)]
DEMO_DAYS = [d for d in DAYS if d >= DEMO_START]

# --- the demo world: one district ------------------------------------------

MANDIS = {
    "vellore_market":      (12.9165, 79.1325),
    "vellore_gudiyatham":  (12.9450, 78.8700),
    "vellore_vaniyambadi": (12.6820, 78.6200),
    "vellore_arakkonam":   (13.0830, 79.6700),
}
ZONES = {
    "vellore_katpadi":       (12.9698, 79.1325),
    "vellore_bagayam":       (12.9060, 79.0930),
    "vellore_sathuvachari":  (12.9340, 79.1560),
    "vellore_thorapadi":     (12.9010, 79.1420),
}

# The market/zone we inject a manipulation signal into.
SUSPECT_MANDI = "vellore_vaniyambadi"   # tomato: variance collapse + persistence
SUSPECT_ZONE = "vellore_katpadi"        # autos: quantised fares
EVENT_START = date(2026, 6, 1)

QC_PLATFORMS = ["qc_alpha", "qc_beta", "qc_gamma"]
RH_PLATFORMS = ["rh_one", "rh_two"]


def seasonal(d: date, amp: float, phase: float) -> float:
    doy = d.timetuple().tm_yday
    return amp * np.sin(2 * np.pi * (doy / 365.25) + phase)


# --- 1. Agmarknet: daily mandi modal price + arrivals -----------------------

COMMODITIES = {
    # name: (base Rs/quintal, seasonal amp, arrivals base tonnes, elasticity)
    "Tomato": (1850.0, 520.0, 95.0, 0.55),
    "Onion":  (2250.0, 430.0, 140.0, 0.42),
}


def gen_agmarknet() -> None:
    for commodity, (base, amp, arr_base, elast) in COMMODITIES.items():
        rows = []
        for mandi in MANDIS:
            # each mandi has its own level and its own AR(1) shock path
            level = base * RNG.uniform(0.94, 1.06)
            shock = 0.0
            mandi_arr = arr_base * RNG.uniform(0.7, 1.3)
            for d in DAYS:
                shock = 0.82 * shock + RNG.normal(0, 0.028)
                arr_season = 1.0 + seasonal(d, 0.30, 1.1)
                arrivals = max(4.0, mandi_arr * arr_season * np.exp(RNG.normal(0, 0.22)))
                # competitive price: tracks the cost/supply driver
                supply_term = (mandi_arr * arr_season / arrivals) ** elast
                price = level * (1 + seasonal(d, amp / base, 0.4)) * supply_term * np.exp(shock)

                if commodity == "Tomato" and mandi == SUSPECT_MANDI and d >= EVENT_START:
                    # collusive regime: decoupled from arrivals, elevated, very smooth
                    ramp = min(1.0, (d - EVENT_START).days / 10)
                    price = level * (1 + seasonal(d, amp / base, 0.4))
                    price *= (1 + 0.42 * ramp) * np.exp(0.15 * shock)

                lo = price * RNG.uniform(0.86, 0.93)
                hi = price * RNG.uniform(1.07, 1.15)
                rows.append({
                    "District Name": "Vellore",
                    "Market Name": mandi,
                    "Commodity": commodity,
                    "Variety": "Local",
                    "Grade": "FAQ",
                    "Min Price (Rs./Quintal)": round(lo),
                    "Max Price (Rs./Quintal)": round(hi),
                    "Modal Price (Rs./Quintal)": round(price),
                    "Arrivals (Tonnes)": round(arrivals, 2),
                    "Price Date": d.strftime("%d %b %Y"),
                })
        rows.sort(key=lambda r: (r["Price Date"], r["Market Name"]))
        out = RAW / "agmarknet" / f"agmarknet_{commodity.lower()}.csv"
        cols = ["Sl no.", "District Name", "Market Name", "Commodity", "Variety", "Grade",
                "Min Price (Rs./Quintal)", "Max Price (Rs./Quintal)",
                "Modal Price (Rs./Quintal)", "Arrivals (Tonnes)", "Price Date"]
        with out.open("w") as fh:
            fh.write(",".join(cols) + "\n")
            for i, r in enumerate(rows, 1):
                r["Sl no."] = i
                fh.write(",".join(str(r[c]) for c in cols) + "\n")
        print(f"  agmarknet/{out.name}: {len(rows)} rows")


# --- 2. NECC declared egg rate (the reference rate for eggs) ----------------

def necc_rate(d: date) -> float:
    """Rs per 100 eggs, declared daily."""
    base = 560 + 55 * np.sin(2 * np.pi * (d.timetuple().tm_yday / 365.25) + 3.9)
    return float(np.round(base + RNG.normal(0, 6)))


NECC = {}


def gen_necc() -> None:
    lines = ["Date,Zone,Rate (Rs./100 eggs)"]
    for d in DAYS:
        r = necc_rate(d)
        NECC[d] = r
        lines.append(f"{d.strftime('%d-%m-%Y')},Chennai,{r:.0f}")
    (RAW / "necc" / "necc_declared_rates.csv").write_text("\n".join(lines) + "\n")
    print(f"  necc/necc_declared_rates.csv: {len(DAYS)} rows")


# --- 3. q-commerce catalogue snapshots (eggs) ------------------------------

PACKS = {"6 pcs": 6, "12 pcs": 12, "30 pcs": 30}


EGG_ANCHOR: dict[date, float] = {}


def _build_egg_anchor() -> None:
    """A focal price the suspect zone settles on, drifting on its own schedule
    and not following the declared rate."""
    level = NECC[EVENT_START] / 100.0 * 1.58
    for d in DEMO_DAYS:
        level *= float(np.exp(RNG.normal(0, 0.014)))
        EGG_ANCHOR[d] = level


def gen_qcommerce() -> None:
    _build_egg_anchor()
    for plat in QC_PLATFORMS:
        markup = {"qc_alpha": 1.34, "qc_beta": 1.31, "qc_gamma": 1.37}[plat]
        with (RAW / "qcommerce" / f"{plat}.jsonl").open("w") as fh:
            for d in DEMO_DAYS:
                declared = NECC[d] / 100.0  # Rs per egg
                for zone, (lat, lng) in ZONES.items():
                    # everyone marks up; in one zone the markup widens and freezes
                    if zone == SUSPECT_ZONE and d >= EVENT_START:
                        # prices track a shared drifting anchor instead of the
                        # declared rate: the pattern detector 2 exists to find
                        per_egg = EGG_ANCHOR[d] * np.exp(RNG.normal(0, 0.002))
                    else:
                        per_egg = declared * markup * np.exp(RNG.normal(0, 0.02))
                    results = []
                    for pack, n in PACKS.items():
                        price = round(per_egg * n * RNG.uniform(0.995, 1.005), 1)
                        results.append({
                            "sku_id": f"{plat}-egg-{n}",
                            "title": f"Table Eggs, pack of {n}",
                            "pack": pack,
                            "mrp": round(price * 1.12, 1),
                            "price": price,
                            "in_stock": True,
                        })
                    fh.write(json.dumps({
                        "captured_at": f"{d.isoformat()}T07:15:00+05:30",
                        "platform": plat,
                        "pincode": "632007",
                        "zone": zone,
                        "lat": lat, "lng": lng,
                        "results": results,
                    }) + "\n")
        print(f"  qcommerce/{plat}.jsonl: {len(DEMO_DAYS) * len(ZONES)} snapshots")


# --- 4. ride-hail fare estimates (autos) -----------------------------------

GAZETTE_MIN_FARE = 25.0     # first 1.8 km
GAZETTE_INCLUDED_KM = 1.8
GAZETTE_PER_KM = 12.0


def gazetted_fare(km: float) -> float:
    return GAZETTE_MIN_FARE + max(0.0, km - GAZETTE_INCLUDED_KM) * GAZETTE_PER_KM


def gen_ridehail() -> None:
    for plat in RH_PLATFORMS:
        with (RAW / "ridehail" / f"{plat}.jsonl").open("w") as fh:
            n = 0
            for d in DEMO_DAYS:
                for zone, (lat, lng) in ZONES.items():
                    for _ in range(6):
                        km = float(np.round(RNG.uniform(1.2, 7.5), 1))
                        if zone == SUSPECT_ZONE and d >= EVENT_START:
                            # fares quantised to Rs 10 steps, weak distance response
                            # near-flat zone rate: barely responds to distance
                            raw = 76 + 2.0 * km + RNG.normal(0, 6)
                            fare = float(np.round(raw / 10.0) * 10)
                        else:
                            fare = gazetted_fare(km) * RNG.uniform(1.02, 1.22)
                            fare = float(np.round(fare))
                        fh.write(json.dumps({
                            "captured_at": f"{d.isoformat()}T09:30:00+05:30",
                            "platform": plat,
                            "zone": zone,
                            "pickup": {"lat": round(lat, 5), "lng": round(lng, 5)},
                            "distance_km": km,
                            "eta_min": int(RNG.integers(3, 12)),
                            "fare_estimate_low": round(fare * 0.95),
                            "fare_estimate_high": round(fare * 1.08),
                            "fare_estimate": fare,
                            "currency": "INR",
                        }) + "\n")
                        n += 1
        print(f"  ridehail/{plat}.jsonl: {n} estimates")


# --- 5. field reports (form CSV, tier C) -----------------------------------

def jitter(v: float, m: float = 0.0009) -> float:
    return float(v + RNG.normal(0, m))


def gen_reports() -> None:
    cols = ["submitted_at", "lat", "lng", "item", "price_inr", "unit", "distance_km", "note"]
    rows = []
    for d in DEMO_DAYS:
        # tomato retail reports at the mandi towns
        for mandi, (lat, lng) in MANDIS.items():
            for _ in range(RNG.integers(2, 5)):
                base = 26.0 + 8 * np.sin(2 * np.pi * (d.timetuple().tm_yday / 365.25) + 0.4)
                if mandi == SUSPECT_MANDI and d >= EVENT_START:
                    price = base * 1.45 * np.exp(RNG.normal(0, 0.012))
                else:
                    price = base * np.exp(RNG.normal(0, 0.11))
                rows.append([f"{d.isoformat()}T10:05:00+05:30", round(jitter(lat), 6),
                             round(jitter(lng), 6), "tomato", round(price, 1), "per_kg", "",
                             "retail shop"])
        # egg + auto reports in the zones
        for zone, (lat, lng) in ZONES.items():
            for _ in range(RNG.integers(1, 4)):
                declared = NECC[d] / 100.0
                if zone == SUSPECT_ZONE and d >= EVENT_START:
                    price = EGG_ANCHOR[d] * RNG.uniform(0.997, 1.003)
                else:
                    price = declared * RNG.uniform(1.25, 1.45) * RNG.uniform(0.97, 1.03)
                rows.append([f"{d.isoformat()}T18:40:00+05:30", round(jitter(lat), 6),
                             round(jitter(lng), 6), "egg_table",
                             round(price, 2), "per_piece", "", "local shop"])
            for _ in range(RNG.integers(1, 4)):
                km = float(np.round(RNG.uniform(1.5, 6.0), 1))
                if zone == SUSPECT_ZONE and d >= EVENT_START:
                    fare = float(np.round((76 + 2.0 * km + RNG.normal(0, 6)) / 10.0) * 10)
                else:
                    fare = float(np.round(gazetted_fare(km) * RNG.uniform(1.0, 1.25)))
                rows.append([f"{d.isoformat()}T19:10:00+05:30", round(jitter(lat), 6),
                             round(jitter(lng), 6), "auto_ride", fare, "per_ride", km,
                             "street quote"])

    # A location covered ONLY by field reports, from two grid cells. It exists to
    # exercise the evidence floor: the pattern is real but the evidence is thin,
    # and the pipeline must refuse to put it in the inspection queue.
    for d in DEMO_DAYS[-45:]:
        declared = NECC[d] / 100.0
        for lat, lng in [(12.95000, 79.33000), (12.95040, 79.33050)]:
            rows.append([f"{d.isoformat()}T17:20:00+05:30", lat, lng, "egg_table",
                         round(declared * 1.78 * RNG.uniform(0.99, 1.01), 2),
                         "per_piece", "", "single-source zone"])

    # dirty rows the parser must reject: no geotag, no timestamp
    for _ in range(18):
        d = DEMO_DAYS[int(RNG.integers(0, len(DEMO_DAYS)))]
        rows.append([f"{d.isoformat()}T12:00:00+05:30", "", "", "tomato", 31.0, "per_kg", "", "no geotag"])
    for _ in range(11):
        rows.append(["", 12.9165, 79.1325, "egg_table", 8.4, "per_piece", "", "no timestamp"])

    RNG.shuffle(rows)
    with (RAW / "reports" / "field_reports.csv").open("w") as fh:
        fh.write(",".join(cols) + "\n")
        for r in rows:
            fh.write(",".join(str(x) for x in r) + "\n")
    print(f"  reports/field_reports.csv: {len(rows)} rows (29 intentionally invalid)")


# --- 6. reference rate sources not covered above ---------------------------

def gen_reference() -> None:
    (RAW / "reference" / "tn_auto_fare.json").write_text(json.dumps({
        "source": "tn_gazette",
        "citation": "Tamil Nadu Motor Vehicles (Autorickshaw Fare) Notification, "
                    "G.O. (Ms) No. 41, Transport Dept — Vellore district schedule",
        "effective_from": "2025-01-01",
        "currency": "INR",
        "minimum_fare": GAZETTE_MIN_FARE,
        "minimum_fare_included_km": GAZETTE_INCLUDED_KM,
        "per_km_after": GAZETTE_PER_KM,
        "waiting_per_15_min": 7.5,
    }, indent=2) + "\n")
    (RAW / "reference" / "necc_citation.txt").write_text(
        "National Egg Coordination Committee — declared daily egg rate, Chennai zone\n")
    (RAW / "reference" / "README.md").write_text(
        "Reference-rate source material. `citation` strings here are copied verbatim "
        "into case files.\n")
    print("  reference/: gazette schedule + citations")


def main() -> None:
    print("generating synthetic raw fixtures into data/raw/ ...")
    gen_agmarknet()
    gen_necc()
    gen_qcommerce()
    gen_ridehail()
    gen_reports()
    gen_reference()
    (RAW / "README.md").write_text(
        "# data/raw\n\n"
        "**These files are SYNTHETIC**, generated by `python -m tools.make_fixture`.\n"
        "They are written in the same formats the real upstream sources emit, so the\n"
        "ingest parsers do real parsing work and can be pointed at genuine scrape\n"
        "output with no code change.\n\n"
        "Replace file-by-file with real scrape output as it lands. Nothing downstream\n"
        "needs to change when you do.\n\n"
        "Note: agmarknet.gov.in has been rebuilt as a SPA whose API is captcha-gated;\n"
        "the `__VIEWSTATE` postback flow described in CLAUDE.md 5.1 no longer exists.\n"
    )
    print("done.")


if __name__ == "__main__":
    main()
