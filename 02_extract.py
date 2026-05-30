#!/usr/bin/env python3
"""STAGE 2 — EXTRACT (stream + filter + flatten).

Reads ONE in-network rate file (local .json or .json.gz) and emits two narrow,
long-format tables suitable for Stata:

  rates_long.csv : one row per (billing_code x provider_group x negotiated_price)
  providers.csv  : crosswalk, one row per (provider_group_id x npi) with TIN info

Keeping NPIs in a separate normalized crosswalk avoids Stata's 2045-char string
limit and keeps the rates table narrow. Merge on provider_group_id in Stata.

The parse is streamed with ijson so a 100+GB uncompressed file never lands in RAM.
Filtering happens in cheap-to-expensive order: billing_code first, then provider.

Handles all three provider-linkage patterns seen in the wild:
  (a) schema 2.x internal  : root provider_references[] {provider_group_id, provider_groups[]}
  (b) legacy inline        : negotiated_rates[].provider_groups[]  (no id)
  (c) legacy external file  : provider_references[].location URL (warned; resolve separately)

Example
  python3 scripts/02_extract.py --in data/raw/sample_innetwork.json \
      --codes config/target_codes.csv --providers-filter config/target_providers.csv \
      --out-rates data/staging/rates_long.csv --out-providers data/staging/providers.csv
"""
from __future__ import annotations

import argparse
import csv
import sys

import ijson

import tic_common as tc

RATE_COLS = [
    "source_file", "reporting_entity_name", "reporting_entity_type",
    "schema_version", "last_updated_on",
    "billing_code_type", "billing_code_type_version", "billing_code",
    "name", "negotiation_arrangement",
    "negotiated_type", "negotiated_rate", "billing_class", "setting",
    "service_codes", "billing_code_modifiers", "expiration_date",
    "provider_group_id",
]
PROV_COLS = [
    "source_file", "provider_group_id", "npi", "tin_type", "tin_value",
    "business_name", "network_names",
]


def load_code_set(path):
    """Return a set of (billing_code_type_upper, billing_code) and a code-only set."""
    pairs, codes_only = set(), set()
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            code = str(row.get("billing_code", "")).strip()
            ctype = str(row.get("billing_code_type", "")).strip().upper()
            if not code:
                continue
            codes_only.add(code)
            pairs.add((ctype, code))
    return pairs, codes_only


def load_provider_filter(path):
    """Return (npi_set, tin_set) or (None, None) if no data rows (=> keep all)."""
    if not path:
        return None, None
    npis, tins = set(), set()
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(r for r in fh if not r.lstrip().startswith("#")):
            npi = str(row.get("npi", "")).strip()
            tin = str(row.get("tin_value", "")).strip()
            if npi:
                npis.add(npi)
            if tin:
                tins.add(tin.replace("-", ""))
    if not npis and not tins:
        return None, None
    return (npis or None), (tins or None)


def build_provider_map(path, prov_writer, source_file, npi_filter, tin_filter):
    """First pass: stream root provider_references[] -> {gid: keep_bool} and write crosswalk.

    Returns the set of provider_group_ids that pass the provider filter (or None
    meaning "no provider filter, keep all gids").
    """
    keep_gids = set()
    any_ref = False
    with tc.open_maybe_gzip(path) as f:
        for ref in ijson.items(f, "provider_references.item"):
            any_ref = True
            gid = ref.get("provider_group_id")
            if "location" in ref and not ref.get("provider_groups"):
                tc.log(f"   !! provider_group_id {gid} uses external 'location' file "
                       "(legacy) — resolve separately; skipped in this pass.")
                continue
            nets = ";".join(ref.get("network_name", []) or [])
            no_filter = (npi_filter is None and tin_filter is None)
            gid_keep = no_filter
            for grp in ref.get("provider_groups", []) or []:
                tin = grp.get("tin", {}) or {}
                tin_val = str(tin.get("value", "")).replace("-", "")
                npis = [str(n) for n in (grp.get("npi", []) or [])]
                tin_match = bool(tin_filter) and tin_val in tin_filter
                # Decide which NPIs to KEEP. With a Texas NPI filter active, keep only
                # the matching (Texas) NPIs and drop "0" (TIN-only, unresolvable to a state).
                if no_filter:
                    keep_npis = npis
                elif tin_match:
                    keep_npis = [n for n in npis if n != "0"]
                else:
                    keep_npis = [n for n in npis if npi_filter and n in npi_filter]
                if keep_npis or tin_match:
                    gid_keep = True
                for npi_s in keep_npis:
                    prov_writer.writerow([source_file, gid, npi_s,
                                          tin.get("type", ""), tin.get("value", ""),
                                          tin.get("business_name", ""), nets])
            if gid_keep:
                keep_gids.add(gid)
    if not any_ref:
        tc.log("   (no root provider_references[] — expecting inline provider_groups)")
        return None  # signal: resolve providers inline during rate pass
    if npi_filter is None and tin_filter is None:
        return None  # keep all
    tc.log(f"   provider filter keeps {len(keep_gids)} provider groups")
    return keep_gids


def read_header(path):
    """Cheaply grab the top-level identifier scalars, stopping as soon as the
    first big array begins so we never stream the whole file just for the header."""
    wanted = {"reporting_entity_name", "reporting_entity_type", "version", "last_updated_on"}
    fields = {}
    with tc.open_maybe_gzip(path) as f:
        for prefix, event, value in ijson.parse(f):
            if prefix in wanted and event in ("string", "number"):
                fields[prefix] = value
            if prefix in ("in_network", "provider_references") and event == "start_array":
                break
    return fields


def extract(in_path, codes_pairs, codes_only, rate_writer, prov_writer,
            keep_gids, npi_filter, tin_filter, source_file):
    n_seen = n_kept = n_rows = 0
    header = read_header(in_path)  # captured top-level identifiers
    with tc.open_maybe_gzip(in_path) as f:
        # Pull a few top-level scalars first (they precede in_network in well-formed files;
        # if absent we just emit blanks).
        for obj in ijson.items(f, "in_network.item"):
            n_seen += 1
            ctype = str(obj.get("billing_code_type", "")).upper()
            code = str(obj.get("billing_code", ""))
            if codes_only and code not in codes_only:
                continue
            if codes_pairs and (ctype, code) not in codes_pairs:
                # code present under a different code type; skip unless code-only matched intentionally
                pass
            n_kept += 1
            base = [source_file, header.get("reporting_entity_name", ""),
                    header.get("reporting_entity_type", ""),
                    header.get("version", ""), header.get("last_updated_on", ""),
                    ctype, obj.get("billing_code_type_version", ""), code,
                    obj.get("name", ""), obj.get("negotiation_arrangement", "")]
            for nr in obj.get("negotiated_rates", []) or []:
                gids = list(nr.get("provider_references", []) or [])
                inline = nr.get("provider_groups")  # legacy inline form
                for price in nr.get("negotiated_prices", []) or []:
                    row_tail = [
                        price.get("negotiated_type", ""), price.get("negotiated_rate", ""),
                        price.get("billing_class", ""), price.get("setting", ""),
                        ";".join(str(s) for s in price.get("service_code", []) or []),
                        ";".join(str(s) for s in price.get("billing_code_modifier", []) or []),
                        price.get("expiration_date", ""),
                    ]
                    if gids:
                        for gid in gids:
                            if keep_gids is not None and gid not in keep_gids:
                                continue
                            rate_writer.writerow(base + row_tail + [gid])
                            n_rows += 1
                    elif inline:
                        # legacy: providers embedded; write crosswalk on the fly with a synthetic gid
                        for grp in inline:
                            tin = grp.get("tin", {}) or {}
                            tin_val = str(tin.get("value", "")).replace("-", "")
                            npis = [str(n) for n in (grp.get("npi", []) or [])]
                            no_filter = (npi_filter is None and tin_filter is None)
                            tin_match = bool(tin_filter) and tin_val in tin_filter
                            if no_filter:
                                keep_npis = npis
                            elif tin_match:
                                keep_npis = [n for n in npis if n != "0"]
                            else:
                                keep_npis = [n for n in npis if npi_filter and n in npi_filter]
                            if not (keep_npis or tin_match):
                                continue
                            syn_gid = f"inline:{code}:{tin_val or 'na'}"
                            for npi_s in keep_npis:
                                prov_writer.writerow([source_file, syn_gid, npi_s,
                                                      tin.get("type", ""), tin.get("value", ""),
                                                      tin.get("business_name", ""), ""])
                            rate_writer.writerow(base + row_tail + [syn_gid])
                            n_rows += 1
    tc.log(f"   in_network records: {n_seen} seen, {n_kept} matched codes -> {n_rows} rate rows")
    return n_rows


def main(argv=None):
    ap = argparse.ArgumentParser(description="TiC in-network extractor")
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--codes", required=True)
    ap.add_argument("--providers-filter", default="")
    ap.add_argument("--out-rates", default="data/staging/rates_long.csv")
    ap.add_argument("--out-providers", default="data/staging/providers.csv")
    args = ap.parse_args(argv)

    codes_pairs, codes_only = load_code_set(args.codes)
    npi_filter, tin_filter = load_provider_filter(args.providers_filter)
    source_file = tc.filename_from_url(args.inp)
    tc.log(f"codes: {len(codes_only)} | provider filter: "
           f"{'NONE (keep all)' if npi_filter is None and tin_filter is None else 'ACTIVE'}")

    import os
    for p in (args.out_rates, args.out_providers):
        os.makedirs(os.path.dirname(p) or ".", exist_ok=True)

    with open(args.out_providers, "w", newline="", encoding="utf-8") as pf:
        prov_writer = csv.writer(pf)
        prov_writer.writerow(PROV_COLS)
        tc.log("pass 1/2: provider references")
        keep_gids = build_provider_map(args.inp, prov_writer, source_file,
                                       npi_filter, tin_filter)
        with open(args.out_rates, "w", newline="", encoding="utf-8") as rf:
            rate_writer = csv.writer(rf)
            rate_writer.writerow(RATE_COLS)
            tc.log("pass 2/2: in_network rates")
            extract(args.inp, codes_pairs, codes_only, rate_writer, prov_writer,
                    keep_gids, npi_filter, tin_filter, source_file)

    tc.log(f"\nWROTE {args.out_rates} and {args.out_providers}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
