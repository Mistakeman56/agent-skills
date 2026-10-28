---
name: cn-blocked-api-access
description: "Use when a China network cannot reach a host or API."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [China, GFW, proxy, mihomo, Clash, OpenClash, DNS-poisoning, geo-block]
---

# Reaching a blocked host from a China LAN

Use when a fetch/API call fails in a way that is not a WAF: the hostname resolves to a
nonsense IP, the TLS handshake resets, or the service refuses the region. Archives and
reader services cannot help — a live API has no snapshot to recover.

Worked case: all four `*.polymarket.com` API hosts from an LXC behind an iStoreOS router
running OpenClash → local mihomo on `127.0.0.1:7899` exiting in Hong Kong, router untouched,
systemd-autostarted. Polymarket also geoblocks Japan, so the region must be chosen
per-service, not once.

## 1. Diagnose before changing anything

**First decide whether it is only your path.** Your own fetch tools exit from a different
network than the user's browser, so "loads for me, refused for them" means the site is alive
and *their* egress IP is being blocked — no DNS, SNI or local proxy change can help. Resolve
the fetch tool's exit IP (its URL filter rejects `ifconfig.me`, `ipinfo.io` and
`httpbin.org/ip` as "private or internal network address"; `https://myip.ipip.net` and
`https://cip.cc` pass and return plain text) and compare it with the user's.

```bash
getent hosts api.example.com                      # unrelated well-known IPs = DNS poisoning
curl -sv --max-time 15 https://api.example.com/ok 2>&1 | grep -iE "trying|connect|ssl|http/|error"
```

| Evidence | Meaning |
|---|---|
| A record is a Facebook/Dropbox/etc. range | DNS poisoning |
| TCP connects, `SSL_ERROR_SYSCALL` at handshake | SNI-based reset |
| Same IP: your SNI → 000, `www.cloudflare.com` SNI → 200 | SNI filter confirmed, IP clean |
| CONNECT tunnel establishes (`200 Connection established`) then TLS dies | routing/SNI, not credentials |
| `Connection refused` in <100 ms on every port while ICMP still answers with 0% loss | destination firewall REJECTing your source IP — rules out DNS, SNI and your LAN in one stroke |

Separate SNI filtering from IP blocking with one test — same IP, two SNIs:

```bash
curl -s -o /dev/null -w "%{http_code}\n" --resolve api.example.com:443:203.0.113.1 https://api.example.com/
curl -s -o /dev/null -w "%{http_code}\n" --resolve www.cloudflare.com:443:203.0.113.1 https://www.cloudflare.com/
```

Real A records come from an **off-shore** DoH resolver reached *through a working proxy*
(`https://dns.google/resolve?name=<host>&type=A` with `accept: application/dns-json`).
Domestic public DoH (203.0.113.1, doh.pub) returns the same poisoned answers for blocked
hosts — it is not a way around the poisoning. Adding the true IP to `/etc/hosts` does not
help either while the SNI filter is in play; the reset happens after a clean connect.

### Prove it at the packet layer before concluding

`curl` reports "Connection refused" but cannot say who sent the RST. Capture on the WAN
while probing, both inside one script so the readings are same-second (router busybox `sh`
has no `timeout`; background tcpdump and kill it by PID):

```bash
cat > /tmp/probe.sh <<'EOF'
tcpdump -ni any -c 40 "host 203.0.113.1 and tcp" > /tmp/pk.txt 2>&1 &
TP=$!; sleep 1
curl -s -o /dev/null -m 5 --noproxy '*' https://www.example.com/ ; sleep 1
kill $TP; cat /tmp/pk.txt
EOF
ssh -p 2222 root@<router> 'sh -s' < /tmp/probe.sh
```

| Capture | Verdict |
|---|---|
| SYN out, RST back from the destination IP **before any TLS bytes** | server-side IP rejection; no hostname was sent, so SNI/DNS edits are pointless |
| SYN out, RST back **after the ClientHello** | SNI/Host filtering on path — the two-SNI `--resolve` test above separates this |
| SYN out, no reply at all | upstream drop or blackholed route — loop the probe, because absence is the signal |
| SYN never leaves the WAN interface | local firewall or your own proxy config |

The `any` device's promiscuous-mode WARNING is harmless; packets still capture. A blank
capture means the probe fell outside the capture window — background tcpdump, `sleep 1`,
then probe.

When the capture shows the destination rejecting you, say so plainly: the site is alive
(prove it by fetching the live page from your own egress), their egress IP is refused, and no
local change will help. The one test the user can run that changes only the egress IP is a
mobile-hotspot check.

## 2. Find out where the traffic actually goes

A router proxy whose final rule is `MATCH → DIRECT` sends every domain outside its rule
sets out **unproxied** — that is why "switch to another node / another region" changes
nothing, and why a node health test against the target still looks fine. Read the rules
read-only through the control API instead of guessing:

```bash
# running config path: ps w | grep -i clash
SECRET=$(ssh <router> "grep -E '^secret' /etc/openclash/<cfg>.yaml | cut -d' ' -f2")
ssh <router> "curl -s -H 'Authorization: Bearer $SECRET' http://127.0.0.1:9090/rules"     # final Match rule → DIRECT?
ssh <router> "curl -s -H 'Authorization: Bearer $SECRET' http://127.0.0.1:9090/proxies"   # groups, current node
```

`GET /proxies/<name>/delay?url=<target>` probes reachability *through* a named node
without editing config — use it to find a usable region. Confirm the region you actually
exit with an IP-echo service **through the proxy**; the config says nothing about it.

## 3. Build a local egress (no router/firewall changes)

Run a second, local proxy whose only rule is `MATCH → <off-shore group>`, using nodes the
user already pays for. `scripts/local_proxy_setup.py` generates that config from the
router's existing OpenClash yaml (read-only, one `cat` over SSH, credentials never printed,
config chmod 600).

```bash
TAG=$(curl -sL -o /dev/null -w '%{url_effective}' https://github.com/MetaCubeX/mihomo/releases/latest | sed 's#.*/tag/##')
curl -sL "https://github.com/MetaCubeX/mihomo/releases/expanded_assets/$TAG"     # pick mihomo-linux-amd64-*.gz
curl -sL -o /tmp/mihomo.gz "https://gh-proxy.com/https://github.com/MetaCubeX/mihomo/releases/download/$TAG/<asset>"
gunzip -c /tmp/mihomo.gz > /usr/local/bin/mihomo && chmod +x /usr/local/bin/mihomo

python3 scripts/local_proxy_setup.py Hong      # region keyword = ENGLISH city name
/usr/local/bin/mihomo -t -d ~/.hermes/mihomo -f ~/.hermes/mihomo/config.yaml   # config test only
```

Then a systemd unit (`Restart=always`, `ExecStartPre=-python3 .../local_proxy_setup.py Hong`
— the `-` lets a node-refresh failure fall back to the config already on disk). Verify:

```bash
systemctl is-active <unit>
curl -s -x http://127.0.0.1:7899 https://ipinfo.io/json                 # expected country
curl -s -x http://127.0.0.1:7899 "<real endpoint>" -o /dev/null -w '%{http_code}\n'
```

Verify against a **real data endpoint**, not the host's health path: a 404 on `/ok` while
`/markets?limit=1` returns a body is a success, and reading the 404 as failure sends you
back down the ladder. For scripting, `export https_proxy=socks5h://127.0.0.1:7899
http_proxy=socks5h://127.0.0.1:7899` is enough and works for urllib/requests too.

## Pitfalls

- **`web_extract` answering `Blocked: URL targets a private or internal network address`
  for a public URL is a DNS symptom, not a broken tool** — the name resolved to a private/
  bogus range (poisoning or resolver hijack) and the fetch guard rejected it. Check
  `getent hosts <host>`, retry with `curl -sL` direct (the system resolver may answer
  differently), and only then fall back to the local proxy below.
- **Never judge intermittency from probes taken minutes apart.** Samples split across runs
  contradicted each other (30/30 connect, then 0/30) and cost a detour; run the TCP probe
  (`nc`) and the TLS probe (`curl`) inside one script so both readings are same-second, and
  let the packet capture break any tie.
- **Match node names on the English city, not the Chinese name.** Names are usually written
  with escaped flag codepoints (`"\U0001F1ED\U0001F1F0 Hong Kong丨01"`), so a `香港` filter
  matches nothing, the generator emits an empty proxy list, and the unit still starts on the
  stale config — a silent failure.
- **Never `pkill -f <name-of-script>`**: the pattern matches the shell whose own command line
  contains it, so the command kills itself (exit −15, no output). Use `pgrep -af "[s]cript.py"`.
- **The terminal tool refuses `nohup`/`setsid`/`disown`** — start long-lived processes with
  `background=true`, then readiness-check the port in a separate call.
- **Routers often have no python3** (iStoreOS/OpenWrt busybox): dump JSON to the local host
  over SSH and parse locally. The same image usually has no `timeout` either — background the
  command and `kill` its PID instead.
- **Don't trust the port numbers in the config.** The running yaml's `mixed-port` and the
  ports actually listening can differ — check `netstat -lntp` on the router. Expect the HTTP
  proxy port to demand Basic auth (`407 ... Proxy Authentication Required`) when the router's
  OpenClash has authentication enabled; those credentials live in
  `uci show openclash.@authentication[0]`, not in the yaml.
- **Never echo node passwords or proxy credentials** into command output or the transcript:
  read them inside a script in the same process that uses them.
- **Large transfers behind a transparent proxy stall silently** — the process stays alive, the byte count freezes for minutes, and no error is ever raised. Diagnose with a two-sample size read, not with liveness: `a=size; sleep 60; b=size` — frozen `b` is the failure, a live PID is not. Three consequences:
  - **Force short, self-terminating connections and resume** until a byte target is met: `while not complete: curl -L -C - --connect-timeout 15 --max-time 90 --speed-limit 61440 --speed-time 20 -sS -o FILE URL`. `--speed-time 20` makes curl abort on 20s below 60 KB/s so the loop reconnects; `-C -` resumes so no bytes are lost. A long single connection degrades after minutes (measured 1.45 MB/s sustained vs 20 MB/s through the reconnect loop on the same path).
  - **Multi-threading the same file is not the fix** — 8 ranged connections gained only +10%, because the limit is the path, not the connection.
  - **Never write a Python `urllib` downloader for this.** Through the same proxy `urllib` ran at 20 KB/s while `curl` ran at 7 MB/s on the identical URL; the stdlib client negotiates the path far worse. Use `curl`, from a script or a shell loop.
- **Get the exact byte count with a HEAD request before looping.** A completion test written against an *estimated* size that overshoots by a few KB never fires — the loop spins hundreds of rounds reporting 100% and the next file in the queue never starts. Parse `Content-Length` from `curl -sSIL` (follow redirects, take the last one).
- **Dead ends, don't spend the session on them:** TLS ClientHello fragmentation (local split
  or out-of-order first segment — modern middleboxes reassemble TCP) and anonymous public
  fetch relays (key-gated or down). Your own egress is the reliable route.
