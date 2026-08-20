"""Top up the committed Agmarknet export, then rebuild.

    DATA_GOV_API_KEY=... python -m tools.refresh_agmarknet

Run on a schedule (deploy/refresh.ps1 does this every two days). The portal's
open-data resource serves only current prices, so each run captures a few days
and the committed file accumulates the history. A run that is missed is data
that cannot be recovered later.

    fetch  ->  data/raw/agmarknet_real/vellore_export.csv.gz  ->  pipeline.build

The two halves stay separate on purpose. Only this script touches the network;
`pipeline.build` reads the file from disk and opens no socket, so the offline
guarantee still holds and the demo still works with the wifi off.

--dry-run fetches and reports without writing anything.
"""
from __future__ import annotations

import argparse
import sys

from pipeline.ingest import agmarknet_api


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="fetch and report, write nothing")
    ap.add_argument("--no-build", action="store_true",
                    help="update the export but skip pipeline.build")
    args = ap.parse_args()

    print("fetching current daily prices from data.gov.in")
    new = agmarknet_api.fetch()
    if new.empty:
        print("  no rows returned - nothing to do")
        return 0

    dates = sorted(set(new["Arrival_Date"]))
    print(f"  {len(new)} usable rows covering {len(dates)} day(s): "
          f"{dates[0]} .. {dates[-1]}")

    if args.dry_run:
        print("  --dry-run: not writing")
        return 0

    print("merging into the committed export")
    result = agmarknet_api.merge(new)

    if result["added"] == 0:
        # Nothing changed, so the artifacts cannot have changed either. Skipping
        # the build here is what makes a 2-day schedule cheap to run.
        print("no new observations - skipping the rebuild")
        return 0

    if args.no_build:
        print("--no-build: export updated, artifacts are now stale")
        return 0

    print("rebuilding artifacts")
    from pipeline import build
    build.main()

    print(f"\ndone: +{result['added']} rows, data through {result['through']}")
    print("  the API server fits its band model at startup - restart it to pick this up")
    return 0


if __name__ == "__main__":
    sys.exit(main())
