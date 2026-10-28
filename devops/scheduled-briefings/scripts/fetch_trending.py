#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fetch GitHub Trending (daily) repos via curl + regex.

Validated 2026-08 on github.com/trending. Usage:
    python3 fetch_trending.py [daily|weekly|monthly]   (default: daily)

Prints one line per repo:
    owner/repo | lang | stars_today | description

Requires only curl + python3 stdlib. Uses `--noproxy '*'` so it works even
when HTTPS_PROXY points at a dead proxy (urllib/requests do NOT bypass it).

Key parsing pitfall (cost an iteration in the field): each <article> block
contains a `sponsors/<login>` button link BEFORE the repo <h2> anchor, so
grabbing the first href in the block returns "sponsors/lyogavin" instead of
"lyogavin/airllm". Always take the repo link from the <h2> anchor and filter
out "sponsors/" prefixes.
"""
import re
import subprocess
import sys

SINCE = sys.argv[1] if len(sys.argv) > 1 else "daily"
URL = f"https://github.com/trending?since={SINCE}"


def curl(url: str) -> str:
    r = subprocess.run(
        ["curl", "-s", "--noproxy", "*", "-A", "Mozilla/5.0 (daily-brief)", url],
        capture_output=True, text=True, timeout=30,
    )
    return r.stdout


def main() -> int:
    html = curl(URL)
    articles = re.findall(r'<article class="Box-row">(.*?)</article>', html, re.S)
    if not articles:
        print(f"WARN: no articles parsed (html len={len(html)}). "
              "Trending HTML structure may have drifted — inspect it before changing strategy.")
        return 1

    for a in articles:
        m = re.search(r'<h2[^>]*>\s*<a[^>]*href="/([^"]+)"', a)
        if not m:
            continue
        repo = m.group(1).strip()
        if repo.startswith("sponsors/"):  # sponsor button precedes the h2 repo link
            continue
        md = re.search(r'<p[^>]*class="col-9[^"]*"[^>]*>\s*(.*?)\s*</p>', a, re.S)
        desc = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", md.group(1))).strip() if md else ""
        langs = re.findall(r'itemprop="programmingLanguage">([^<]+)<', a)
        stars = re.search(r'([\d,.]+k?)\s+stars', a)
        print(f"{repo} | {langs[0] if langs else ''} | "
              f"{stars.group(1) if stars else '?'} stars | {desc[:160]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
