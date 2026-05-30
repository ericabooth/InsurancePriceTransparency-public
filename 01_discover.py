#!/usr/bin/env python3
"""STAGE 1 — DISCOVER.

Resolve a payer config into a concrete inventory of files to (maybe) pull,
WITHOUT downloading any large rate file. For BCBSTX/HCSC this means:

  si-filelist.json  -->  filter to state  -->  (optional EIN subset)
                    -->  fetch each employer Table-of-Contents
                    -->  emit one inventory row per referenced file.

Output: data/staging/<payer>_inventory.csv with columns
  payer, ein, employer_name, plan_market_type, schema_version,
  file_type (in_network|allowed_amounts), description, location_url, toc_url

Examples
  python3 scripts/01_discover.py --config config/payers/bcbstx.json --route aso \
      --max-employers 3 --out data/staging/bcbstx_inventory.csv
  # restrict to specific employers:
  python3 scripts/01_discover.py --config config/payers/bcbstx.json --route aso \
      --eins 201968466,472642179
"""
from __future__ import annotations

import argparse
import csv
import re
import sys

import tic_common as tc


# US state/territory postal codes EXCEPT TX. BCBSTX home-plan networks (Blue Choice
# PPO, Blue Advantage HMO, Blue Essentials, ...) appear UNPREFIXED; out-of-state
# Blue Card host networks start with a foreign-state prefix. So excluding any
# description that begins with one of these = "keep Texas-provider networks only".
NON_TX_PREFIX = re.compile(
    r"^(AL|AK|AZ|AR|CA|CO|CT|DE|DC|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|"
    r"MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|PR|RI|SC|SD|TN|UT|VT|VA|VI|WA|"
    r"WV|WI|WY)\b", re.I)


def discover_aso(sess, route, eins=None, state_filter=None, max_employers=None,
                 network_re=None, exclude_re=None):
    filelist = tc.get_json(sess, route["filelist_url"])
    tc.log(f"si-filelist.json: {len(filelist)} records")

    rmap = route.get("record_map", {})
    f_ein = rmap.get("ein", "ein")
    f_name = rmap.get("name", "name")
    f_url = rmap.get("toc_url", "url")
    f_state = rmap.get("state", "state")

    states = set(s.upper() for s in (state_filter or route.get("state_filter") or []))
    want_eins = set(eins) if eins else None

    # Filter + de-duplicate on EIN (a few EINs repeat across states/plans).
    seen, employers = set(), []
    for rec in filelist:
        ein = str(rec.get(f_ein, "")).strip()
        st = str(rec.get(f_state, "")).strip().upper()
        if states and st not in states:
            continue
        if want_eins and ein not in want_eins:
            continue
        if ein in seen:
            continue
        seen.add(ein)
        employers.append(rec)

    tc.log(f"after state={sorted(states) or 'ALL'} / EIN filter: {len(employers)} unique employers")
    if max_employers:
        employers = employers[:max_employers]
        tc.log(f"limited to first {len(employers)} employers for this run")

    rows = []
    for i, rec in enumerate(employers, 1):
        ein = str(rec.get(f_ein, "")).strip()
        name = rec.get(f_name, "")
        toc_url = rec.get(f_url, "")
        tc.log(f"[{i}/{len(employers)}] {ein} {name}")
        try:
            toc = tc.get_json(sess, toc_url)
        except Exception as e:  # noqa: BLE001 - report and continue
            tc.log(f"   !! failed to fetch ToC: {e}")
            continue
        version = str(toc.get("version", ""))
        for struct in toc.get("reporting_structure", []):
            plans = struct.get("reporting_plans", [])
            market = ";".join(sorted({p.get("plan_market_type", "") for p in plans}))
            for f in struct.get("in_network_files", []) or []:
                desc = f.get("description", "")
                # network scoping: keep only files whose description matches (e.g. TX networks)
                if network_re and not network_re.search(desc):
                    continue
                if exclude_re and exclude_re.search(desc):
                    continue
                rows.append([rec.get("payer", ""), ein, name, market, version,
                             "in_network", desc,
                             f.get("location", ""), toc_url])
            # allowed_amount_file may be a single object (per schema) or a list (seen live)
            aa = struct.get("allowed_amount_file")
            aa_list = aa if isinstance(aa, list) else ([aa] if aa else [])
            for f in aa_list:
                rows.append([rec.get("payer", ""), ein, name, market, version,
                             "allowed_amounts", f.get("description", ""),
                             f.get("location", ""), toc_url])
    return rows


def find_fi_index_url(sess, route):
    """Scrape the member page for the current month's FI index URL (date rolls monthly)."""
    html = sess.get(route["landing_url"], timeout=120).text
    m = re.search(route["index_url_regex"], html)
    if not m:
        raise RuntimeError("FI index URL not found on landing page; check index_url_regex")
    return m.group(0)


def discover_fi(sess, route, network_re=None, exclude_re=None):
    """Fully-insured route: ONE big issuer-level ToC. Stream it (27MB, ~6.9k file refs)."""
    import ijson
    url = find_fi_index_url(sess, route)
    tc.log(f"FI index: {url}")
    dest = f"data/raw/{tc.filename_from_url(url)}"
    tc.download_to_disk(sess, url, dest)
    rows = []
    with tc.open_maybe_gzip(dest) as f:
        for struct in ijson.items(f, "reporting_structure.item"):
            plans = struct.get("reporting_plans", []) or []
            market = ";".join(sorted({p.get("plan_market_type", "") for p in plans}))
            label = plans[0].get("plan_name", "") if plans else ""
            for fobj in struct.get("in_network_files", []) or []:
                desc = fobj.get("description", "")
                if network_re and not network_re.search(desc):
                    continue
                if exclude_re and exclude_re.search(desc):
                    continue
                rows.append(["", "", label, market, "", "in_network", desc,
                             fobj.get("location", ""), url])
            aa = struct.get("allowed_amount_file")
            for fobj in (aa if isinstance(aa, list) else ([aa] if aa else [])):
                rows.append(["", "", label, market, "", "allowed_amounts",
                             fobj.get("description", ""), fobj.get("location", ""), url])
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description="TiC discovery stage")
    ap.add_argument("--config", required=True)
    ap.add_argument("--route", default="aso", choices=["aso", "fully_insured"])
    ap.add_argument("--eins", default="", help="comma-separated EIN subset")
    ap.add_argument("--state", default="", help="override state filter, e.g. TX")
    ap.add_argument("--max-employers", type=int, default=None)
    ap.add_argument("--network-filter", default="",
                    help="regex; KEEP only in_network files whose description matches")
    ap.add_argument("--tx-only", action="store_true",
                    help="keep only BCBSTX home-plan (Texas) networks; drops out-of-state Blue Card files")
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)

    cfg = tc.load_payer_config(args.config)
    route = cfg["routes"][args.route]
    sess = tc.session(cfg.get("user_agent", tc.DEFAULT_UA))

    eins = [e.strip() for e in args.eins.split(",") if e.strip()] or None
    state = [args.state] if args.state else None
    net_re = re.compile(args.network_filter, re.I) if args.network_filter else None
    excl_re = NON_TX_PREFIX if args.tx_only else None

    if args.route == "fully_insured":
        rows = discover_fi(sess, route, network_re=net_re, exclude_re=excl_re)
    else:
        rows = discover_aso(sess, route, eins=eins, state_filter=state,
                            max_employers=args.max_employers, network_re=net_re,
                            exclude_re=excl_re)
    # stamp the payer id onto rows
    for r in rows:
        r[0] = cfg["payer_id"]

    header = ["payer", "ein", "employer_name", "plan_market_type", "schema_version",
              "file_type", "description", "location_url", "toc_url"]
    out = args.out or f"data/staging/{cfg['payer_id']}_inventory.csv"
    import os
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)

    n_in = sum(1 for r in rows if r[5] == "in_network")
    n_aa = sum(1 for r in rows if r[5] == "allowed_amounts")
    uniq_in = len({r[7] for r in rows if r[5] == "in_network"})
    tc.log(f"\nWROTE {out}: {len(rows)} rows "
           f"({n_in} in_network refs -> {uniq_in} unique URLs, {n_aa} allowed_amounts)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
