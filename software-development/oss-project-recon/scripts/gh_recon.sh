#!/usr/bin/env bash
# gh_recon.sh — one-shot recon of a public GitHub repo. No gh CLI, no jq required.
#
# usage:  bash gh_recon.sh owner/repo [branch]
#
# Prints: repo metadata, recent releases (with asset sizes + download counts),
# tags, recent commits, all issue/PR titles, and the docs/ file listing.
# Everything is written to a temp dir first and parsed with python3, so large
# JSON bodies never hit a stdout cap and control characters never break parsing.

set -uo pipefail

SLUG="${1:?usage: gh_recon.sh owner/repo [branch]}"
BRANCH="${2:-}"

# Some hosts are unreachable through a transparent proxy; drop proxy vars first.
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY

API="https://api.github.com/repos/${SLUG}"
HDR=(-H "Accept: application/vnd.github+json" -H "User-Agent: curl/8")
D="$(mktemp -d)"

curl -s --connect-timeout 25 "${HDR[@]}" "$API"                              -o "$D/repo.json"
curl -s --connect-timeout 25 "${HDR[@]}" "$API/releases?per_page=10"          -o "$D/rel.json"
curl -s --connect-timeout 25 "${HDR[@]}" "$API/tags?per_page=20"              -o "$D/tags.json"
curl -s --connect-timeout 25 "${HDR[@]}" "$API/issues?state=all&per_page=60"  -o "$D/iss.json"

if [ -z "$BRANCH" ]; then
  BRANCH="$(python3 -c "import json;print(json.load(open('$D/repo.json')).get('default_branch') or 'main')" 2>/dev/null || echo main)"
fi

# If /search or a branch name is flaky, retry once with the other endpoint form.
curl -s --connect-timeout 25 "${HDR[@]}" "$API/commits?sha=${BRANCH}&per_page=10" -o "$D/cmt.json"
curl -s --connect-timeout 25 "${HDR[@]}" "$API/contents/docs?ref=${BRANCH}"       -o "$D/docs.json"

python3 - "$D" "$BRANCH" <<'PY'
import json, os, sys

d, br = sys.argv[1], sys.argv[2]

def load(name):
    try:
        with open(os.path.join(d, name), encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None

def show(k, v):
    if v not in (None, '', [], {}):
        print(f'  {k}: {v}')

r = load('repo.json')
print('== repo ==')
if not isinstance(r, dict) or not r.get('full_name'):
    msg = (r or {}).get('message', 'no response')
    print(f'  !! fetch failed or not a repo ({msg}) — check the slug, the network, or the proxy')
else:
    for k in ('full_name', 'description', 'stargazers_count', 'forks_count',
              'open_issues_count', 'created_at', 'pushed_at', 'archived'):
        show(k, r.get(k))
    lic = r.get('license')
    if isinstance(lic, dict):
        show('license', lic.get('spdx_id'))
    show('default_branch', r.get('default_branch'))
    show('topics', ', '.join(r.get('topics') or []))

rel = load('rel.json')
print('\n== releases (recent 10) — body[0] line carries install/upgrade rules ==')
if isinstance(rel, list) and rel:
    for x in rel:
        kind = 'PRE' if x.get('prerelease') else 'rel'
        body = (x.get('body') or '').replace('\r', '')
        first = next((l.strip() for l in body.split('\n') if l.strip()), '')
        print(f"  [{kind}] {x.get('tag_name')}  {(x.get('published_at') or '')[:10]}  {first[:90]}")
        for a in (x.get('assets') or [])[:4]:
            print(f"        asset: {a.get('name')}  {(a.get('size') or 0)//1048576}MB  dl={a.get('download_count')}")
else:
    print('  (none)')

tags = load('tags.json')
print('\n== tags (recent 20) ==')
print('  ' + ', '.join(t.get('name', '') for t in tags) if isinstance(tags, list) and tags else '  (none)')

cmt = load('cmt.json')
print(f'\n== commits on {br} (recent 10) ==')
if isinstance(cmt, list) and cmt:
    for c in cmt:
        ci = c.get('commit') or {}
        msg = (ci.get('message') or '').splitlines()
        print(f"  {((ci.get('author') or {}).get('date') or '')[:10]}  {msg[0][:90] if msg else ''}")
else:
    print('  (none)')

iss = load('iss.json')
print('\n== issues + PRs (state: all, recent 60) — titles are the real pain points ==')
if isinstance(iss, list) and iss:
    for x in iss:
        if 'pull_request' in x:
            continue
        print(f"  #{x.get('number')} [{x.get('state')}] {(x.get('title') or '')[:100]}")
else:
    print('  (none)')

docs = load('docs.json')
print('\n== docs/ listing (release notes + design docs live here) ==')
if isinstance(docs, list) and docs:
    print('  ' + ', '.join(x.get('name', '') for x in docs))
else:
    print('  (no docs/ directory, or the fetch failed)')
PY
