#!/usr/bin/env python3
"""STAGE 3 — CONVERT to Stata .dta.

Reads the long-format CSV(s) from stage 2 and writes a labeled .dta. Uses
pandas.to_stata (available everywhere); swap in pyreadstat.write_dta if you
want richer value-label control. version=118 supports UTF-8 + long strings.

Example
  python3 scripts/03_to_dta.py --in data/staging/rates_long.csv \
      --out data/dta/bcbstx_rates.dta
"""
from __future__ import annotations

import argparse
import sys

import pandas as pd

VAR_LABELS = {
    "source_file": "Source MRF filename",
    "reporting_entity_name": "Reporting entity (payer/TPA)",
    "reporting_entity_type": "Reporting entity type",
    "schema_version": "CMS schema version",
    "last_updated_on": "File last-updated date",
    "billing_code_type": "Code system (CPT/HCPCS/MS-DRG/...)",
    "billing_code_type_version": "Code system version/year",
    "billing_code": "Procedure/service code",
    "name": "Service description (payer-provided)",
    "negotiation_arrangement": "ffs / bundle / capitation",
    "negotiated_type": "Rate basis (negotiated/derived/fee schedule/percentage/per diem)",
    "negotiated_rate": "Negotiated amount (dollars; pct if type=percentage)",
    "billing_class": "professional / institutional / both",
    "setting": "inpatient / outpatient / both",
    "service_codes": "Place-of-service code(s)",
    "billing_code_modifiers": "Code modifier(s)",
    "expiration_date": "Rate expiration (9999-12-31 = evergreen)",
    "provider_group_id": "FK -> providers crosswalk",
}


def main(argv=None):
    ap = argparse.ArgumentParser(description="CSV -> Stata .dta")
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--label", default="TiC negotiated rates (long)")
    args = ap.parse_args(argv)

    df = pd.read_csv(args.inp, dtype=str, keep_default_na=False)
    if "negotiated_rate" in df.columns:
        df["negotiated_rate"] = pd.to_numeric(df["negotiated_rate"], errors="coerce")

    # Stata var names: lowercase, <=32 chars, no dots
    df.columns = [c.lower().replace(".", "_")[:32] for c in df.columns]
    labels = {k[:32]: v[:80] for k, v in VAR_LABELS.items() if k[:32] in df.columns}

    df.to_stata(args.out, write_index=False, version=118,
                data_label=args.label[:80], variable_labels=labels)
    print(f"WROTE {args.out}: {len(df):,} rows x {len(df.columns)} vars", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
