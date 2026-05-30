#!/usr/bin/env python3
"""STAGE 0a — fetch the NPPES monthly Full Replacement file and unzip the main CSV.

Finds the current month's zip on the CMS NPPES download page, streams it to disk,
and extracts just the big npidata_pfile_*.csv (skipping the *_FileHeader.csv).
Prints the extracted CSV path to STDOUT (progress goes to STDERR) so it can be
chained:  CSV=$(python3 00a_fetch_nppes.py --dest scratch/nppes)

Source page: https://download.cms.gov/nppes/NPI_Files.html
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import zipfile

import requests

PAGE = "https://download.cms.gov/nppes/NPI_Files.html"
BASE = "https://download.cms.gov/nppes/"
UA = {"User-Agent": "Mozilla/5.0"}


def log(m):
    print(m, file=sys.stderr, flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", required=True, help="scratch dir for the zip + extracted csv")
    ap.add_argument("--url", default="", help="override zip URL (else auto-detect)")
    args = ap.parse_args(argv)
    os.makedirs(args.dest, exist_ok=True)

    url = args.url
    if not url:
        html = requests.get(PAGE, headers=UA, timeout=60).text
        cands = [c for c in re.findall(r'(NPPES_Data_Dissemination_[A-Za-z]+_\d{4}(?:_V2)?\.zip)', html)
                 if "Weekly" not in c and "Deactivation" not in c]
        if not cands:
            sys.exit("could not find NPPES monthly zip on the download page")
        url = BASE + sorted(set(cands))[0]
    log(f"NPPES zip: {url}")

    zpath = os.path.join(args.dest, os.path.basename(url))
    if not os.path.exists(zpath):
        with requests.get(url, headers=UA, stream=True, timeout=1200) as r:
            r.raise_for_status()
            tot = 0
            with open(zpath, "wb") as fh:
                for blk in r.iter_content(1 << 20):
                    fh.write(blk); tot += len(blk)
            log(f"downloaded {tot/1e9:.2f} GB -> {zpath}")
    else:
        log(f"zip already present: {zpath}")

    with zipfile.ZipFile(zpath) as z:
        members = [m for m in z.namelist()
                   if re.search(r"npidata_pfile.*\.csv$", m, re.I) and "FileHeader" not in m]
        if not members:
            sys.exit("npidata_pfile csv not found inside the zip")
        member = max(members, key=lambda m: z.getinfo(m).file_size)
        out_csv = os.path.join(args.dest, os.path.basename(member))
        if not os.path.exists(out_csv) or os.path.getsize(out_csv) != z.getinfo(member).file_size:
            log(f"extracting {member} ({z.getinfo(member).file_size/1e9:.1f} GB) ...")
            with z.open(member) as src, open(out_csv, "wb") as dst:
                while True:
                    chunk = src.read(1 << 22)
                    if not chunk:
                        break
                    dst.write(chunk)
        log(f"csv ready: {out_csv}")

    print(out_csv)  # STDOUT = the one thing callers want
    return 0


if __name__ == "__main__":
    sys.exit(main())
