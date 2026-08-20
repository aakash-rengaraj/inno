"""What should this price have been?

Every detector and every case file compares an observation against an expected
band. Three bases, chosen per vertical by what is citable:

  model    — commodities. The LightGBM quantile band. Relative to the regional
             level, so it applies to wholesale and retail alike.
  necc     — eggs. The declared daily rate times a documented retail margin range.
  gazette  — autos. The notified fare for the ride's distance, times the margin
             the schedule itself tolerates.

A band whose basis is a published rate carries that rate's citation into the case
file. That is the difference between evidence and a chart.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from pipeline.ingest import gazette, necc_real as necc

# Retail margin ranges. Not fudge factors — the range a competitive retailer is
# expected to sit in above the published rate.
# x NECC declared rate. Calibrated against observed Vellore retail: a single
# egg sells at about Rs 7 while the declared rate sits near Rs 5.90, so the
# typical markup is ~1.2x. The earlier (1.15, 1.50) put the top of the band at
# Rs 8.80, above anything actually seen on the street.
EGG_RETAIL_BAND = (1.05, 1.30)
AUTO_FARE_BAND = (1.00, 1.30)    # x notified fare for the distance

BASIS_CITATION = {
    "necc": necc.CITATION,
    "gazette": None,   # filled from the gazette file at runtime
    "model": ("Agmarknet daily mandi report — Directorate of Marketing & Inspection, "
              "modal wholesale price, Vellore district"),
}


def attach_expectations(banded: pd.DataFrame) -> pd.DataFrame:
    """Add expected_lo / expected_mid / expected_hi / basis / citation / residual.

    `banded` is the output of model.predict_band.
    """
    df = banded.copy()
    sched = gazette.schedule()
    citations = dict(BASIS_CITATION, gazette=sched["citation"])

    df["basis"] = "model"
    df["expected_lo"] = df["p10"]
    df["expected_mid"] = df["p50"]
    df["expected_hi"] = df["p90"]

    # --- eggs: NECC declared rate x retail margin range ---
    declared = (df[df["source"] == "necc"]
                .set_index("date")["price"].groupby(level=0).median())
    is_egg = (df["item"] == "egg_table") & (df["source"] != "necc")
    rate = df.loc[is_egg, "date"].map(declared)
    df.loc[is_egg, "reference_rate"] = rate
    df.loc[is_egg, "expected_lo"] = rate * EGG_RETAIL_BAND[0]
    df.loc[is_egg, "expected_hi"] = rate * EGG_RETAIL_BAND[1]
    df.loc[is_egg, "expected_mid"] = rate * float(np.mean(EGG_RETAIL_BAND))
    df.loc[is_egg, "basis"] = "necc"

    # --- autos: notified fare for this ride's distance ---
    is_auto = df["item"] == "auto_ride"
    fare = df.loc[is_auto, "distance_km"].map(lambda km: gazette.fare_for(km, sched))
    df.loc[is_auto, "reference_rate"] = fare
    df.loc[is_auto, "expected_lo"] = fare * AUTO_FARE_BAND[0]
    df.loc[is_auto, "expected_hi"] = fare * AUTO_FARE_BAND[1]
    df.loc[is_auto, "expected_mid"] = fare * float(np.mean(AUTO_FARE_BAND))
    df.loc[is_auto, "basis"] = "gazette"

    # The declared rate is the reference, not an observation to be judged
    # against itself.
    df.loc[df["source"] == "necc", "basis"] = "reference"
    df["citation"] = df["basis"].map(citations)

    # standardised residual, in half-band units, on one scale for every vertical
    half = ((df["expected_hi"] - df["expected_lo"]) / 2).replace(0, np.nan)
    df["residual"] = (df["price"] - df["expected_mid"]) / half
    df["in_band"] = df["price"].between(df["expected_lo"], df["expected_hi"])

    # the cost/reference driver each price is supposed to track
    df["is_reference_series"] = df["source"] == "necc"
    df["cost_driver"] = df["reference_rate"] if "reference_rate" in df else np.nan
    df.loc[df["basis"] == "model", "cost_driver"] = df.loc[df["basis"] == "model", "peer_level"]
    return df


def comparable_price(df: pd.DataFrame) -> pd.Series:
    """Price on a scale comparable across sellers within a location.

    A ride's fare is not comparable to another ride's unless distance is divided
    out; everything else is already normalised at ingest.
    """
    out = df["price"].astype(float).copy()
    is_auto = df["item"] == "auto_ride"
    out.loc[is_auto] = df.loc[is_auto, "price"] / df.loc[is_auto, "reference_rate"]
    return out
