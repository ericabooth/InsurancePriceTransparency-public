#!/usr/bin/env python3
"""STAGE 4 — ORCHESTRATE.

Ties the pipeline together for one payer/segment run:
  inventory CSV (from stage 1)  ->  DEDUPE in_network URLs  ->  for each unique file:
  download (stream)  ->  run stage-2 extract  ->  append to combined outputs.

The de-dup is the key scale win: BCBSTX references the same shared national rate
files from thousands of employers, so a TX-scoped inventory of hundreds of rows
collapses to a few dozen UNIQUE files actually worth downloading.

Example (real)
  python3 scripts/04_run.py --inventory data/staging/bcbstx_fi_tx_inventory.csv \
      --codes config/target_codes.csv --providers-filter config/npi_tx_xwalk.csv \
      --out-dir data/staging/bcbstx_fi --keep-raw

Example (offline test against a local file path in the inventory)
  python3 scripts/04_run.py --inventory /tmp/test_inv.csv --codes config/target_codes.csv \
      --out-dir /tmp/run_out
"""
from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys

import tic_common as tc

HERE = os.path.dirname(os.path.abspath(__file__))
EXTRACT = os.path.join(HERE, "02_extract.py")


def unique_innetwork_urls(inventory_path):
    seen, urls = set(), []
    with open(inventory_path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("file_type") != "in_network":
                continue
            u = row.get("location_url", "").strip()
            if u and u not in seen:
                seen.add(u)
                urls.append(u)
    return urls


def append_csv(src, dst, write_header):
    """Append src rows to dst, skipping src's header unless write_header."""
    with open(src, newline="", encoding="utf-8") as fin, \
         open(dst, "a", newline="", encoding="utf-8") as fout:
        for i, line in enumerate(fin):
            if i == 0 and not write_header:
                continue
            fout.write(line)


def main(argv=None):
    ap = argparse.ArgumentParser(description="TiC pipeline orchestrator")
    ap.add_argument("--inventory", required=True)
    ap.add_argument("--codes", required=True)
    ap.add_argument("--providers-filter", default="")
    ap.add_argument("--out-dir", default="data/staging/run")
    ap.add_argument("--config", default="config/payers/bcbstx.json")
    ap.add_argument("--limit", type=int, default=None, help="cap unique files (for sampling/testing)")
    ap.add_argument("--keep-raw", action="store_true", help="keep downloaded .json.gz (default: delete after extract)")
    args = ap.parse_args(argv)

    cfg = tc.load_payer_config(args.config) if os.path.exists(args.config) else {}
    sess = tc.session(cfg.get("user_agent", tc.DEFAULT_UA))

    os.makedirs(args.out_dir, exist_ok=True)
    raw_dir = os.path.join(args.out_dir, "raw")
    os.makedirs(raw_dir, exist_ok=True)
    rates_out = os.path.join(args.out_dir, "rates_long.csv")
    prov_out = os.path.join(args.out_dir, "providers.csv")
    for p in (rates_out, prov_out):
        if os.path.exists(p):
            os.remove(p)

    urls = unique_innetwork_urls(args.inventory)
    tc.log(f"unique in_network files to process: {len(urls)}")
    if args.limit and len(urls) > args.limit:
        tc.log(f"!! --limit {args.limit}: processing only {args.limit} of {len(urls)} "
               f"unique files (SAMPLING, not full coverage)")
        urls = urls[:args.limit]

    first = True
    for i, url in enumerate(urls, 1):
        tc.log(f"[{i}/{len(urls)}] {tc.filename_from_url(url)}")
        # local path passthrough for offline testing; otherwise stream-download
        if url.startswith("http"):
            local = os.path.join(raw_dir, tc.filename_from_url(url))
            try:
                tc.download_to_disk(sess, url, local)
            except Exception as e:  # noqa: BLE001
                tc.log(f"   !! download failed ({e}); skipping")
                continue
        else:
            local = url  # treat as a local file path

        tmp_rates = os.path.join(args.out_dir, "_tmp_rates.csv")
        tmp_prov = os.path.join(args.out_dir, "_tmp_prov.csv")
        cmd = [sys.executable, EXTRACT, "--in", local, "--codes", args.codes,
               "--out-rates", tmp_rates, "--out-providers", tmp_prov]
        if args.providers_filter:
            cmd += ["--providers-filter", args.providers_filter]
        r = subprocess.run(cmd, capture_output=True, text=True)
        sys.stderr.write(r.stderr)
        if r.returncode != 0:
            tc.log(f"   !! extract failed; skipping")
            continue

        append_csv(tmp_rates, rates_out, write_header=first)
        append_csv(tmp_prov, prov_out, write_header=first)
        first = False
        os.remove(tmp_rates)
        os.remove(tmp_prov)
        if url.startswith("http") and not args.keep_raw:
            os.remove(local)  # reclaim disk; re-download next run (URLs expire anyway)

    nr = sum(1 for _ in open(rates_out)) - 1 if os.path.exists(rates_out) else 0
    tc.log(f"\nDONE. combined rates rows: {nr:,}\n  {rates_out}\n  {prov_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
