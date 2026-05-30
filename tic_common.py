"""Shared helpers for the Transparency-in-Coverage (TiC) extraction pipeline.

Kept dependency-light on purpose: requests + stdlib. The heavy streaming parse
lives in 02_extract.py (ijson). Everything here is payer-agnostic so adding a new
payer is a config change, not a code change.
"""
from __future__ import annotations

import gzip
import io
import json
import os
import sys
import urllib.parse
from typing import Any, Iterator

import requests

DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def load_payer_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def session(user_agent: str = DEFAULT_UA) -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": user_agent, "Accept": "*/*"})
    return s


def get_json(sess: requests.Session, url: str, timeout: int = 120) -> Any:
    """Fetch a (possibly gzip-encoded) JSON document fully into memory.

    Use ONLY for small docs: the si-filelist master index and per-employer ToC
    files. Never use this on in-network rate files (they are far too large) —
    use download_to_disk + the ijson streamer instead.
    """
    r = sess.get(url, timeout=timeout)
    r.raise_for_status()
    return r.json()


def download_to_disk(sess: requests.Session, url: str, dest: str,
                     chunk: int = 1 << 20) -> str:
    """Stream a (large, possibly pre-signed) file to disk without buffering it
    in memory. Returns the destination path. We only ever call this on the
    specific in-network/OON files chosen during discovery, never the whole posting.
    """
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    with sess.get(url, stream=True, timeout=600) as r:
        r.raise_for_status()
        total = 0
        with open(dest, "wb") as fh:
            for blk in r.iter_content(chunk_size=chunk):
                if blk:
                    fh.write(blk)
                    total += len(blk)
    log(f"  downloaded {total/1e6:.1f} MB -> {dest}")
    return dest


def open_maybe_gzip(path: str) -> io.BufferedReader:
    """Open a local file for binary reading, transparently decompressing .gz.

    ijson reads from this stream one event at a time, so peak memory stays at a
    single record regardless of the (uncompressed) file size.
    """
    if path.endswith(".gz"):
        return gzip.open(path, "rb")
    return open(path, "rb")


def filename_from_url(url: str) -> str:
    p = urllib.parse.urlparse(url)
    return os.path.basename(p.path) or "download.bin"
