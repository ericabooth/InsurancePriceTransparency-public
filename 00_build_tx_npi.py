#!/usr/bin/env python3
"""STAGE 0 (quarterly) — build the Texas NPI crosswalk for "all Texas providers".

Reads the CMS NPPES Full Replacement Monthly file (the big npidata_pfile_*.csv)
and emits a small crosswalk of Texas NPIs to inner-join onto the providers
crosswalk from stage 2.

Source (download once per quarter, ~1.08 GB zip -> ~9 GB csv):
  https://download.cms.gov/nppes/NPI_Files.html
Stata-friendly alternative (pre-made .dta): https://data.nber.org/npi/YYYY/MM/

We stream the CSV (csv.DictReader) and keep only the columns we need, so the
9 GB file never lands in memory. "Texas" = NPPES practice-location state == TX
(primary), with an optional widening to mailing state.

Example
  python3 scripts/00_build_tx_npi.py --nppes data/raw/npidata_pfile_20260501-20260531.csv \
      --out config/npi_tx_xwalk.csv --define practice
"""
from __future__ import annotations

import argparse
import csv
import sys

PRACTICE = "Provider Business Practice Location Address State Name"
MAILING = "Provider Business Mailing Address State Name"
ENTITY = "Entity Type Code"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build Texas NPI crosswalk from NPPES")
    ap.add_argument("--nppes", required=True, help="path to npidata_pfile_*.csv")
    ap.add_argument("--out", default="config/npi_tx_xwalk.csv")
    ap.add_argument("--state", default="TX")
    ap.add_argument("--define", choices=["practice", "practice_or_mailing"],
                    default="practice",
                    help="practice = where care is delivered (recommended); "
                         "practice_or_mailing = wider net")
    args = ap.parse_args(argv)

    st = args.state.upper()
    csv.field_size_limit(1 << 24)
    n_in = n_tx = 0
    with open(args.nppes, newline="", encoding="utf-8", errors="replace") as fin, \
         open(args.out, "w", newline="", encoding="utf-8") as fout:
        reader = csv.DictReader(fin)
        for col in (PRACTICE, ENTITY):
            if col not in reader.fieldnames:
                sys.exit(f"ERROR: expected NPPES column not found: {col!r}. "
                         "Are you using the V.2 layout?")
        w = csv.writer(fout)
        w.writerow(["npi", "entity_type", "practice_state", "mailing_state", "is_tx"])
        for row in reader:
            n_in += 1
            practice = (row.get(PRACTICE) or "").strip().upper()
            mailing = (row.get(MAILING) or "").strip().upper()
            is_tx = (practice == st) or (args.define == "practice_or_mailing" and mailing == st)
            if not is_tx:
                continue
            n_tx += 1
            w.writerow([row.get("NPI", ""), row.get(ENTITY, ""), practice, mailing, 1])
            if n_in % 1_000_000 == 0:
                print(f"  ...scanned {n_in:,} NPIs, {n_tx:,} {st}", file=sys.stderr)

    print(f"WROTE {args.out}: {n_tx:,} {st} NPIs out of {n_in:,} scanned "
          f"(definition={args.define})", file=sys.stderr)
    print("Note: TIN-only rate rows (npi:[0]) cannot be resolved here; recover them "
          "via network_name scoping if needed.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
