# China Networking: GFW DNS & OpenClash Proxy

## DNS Poisoning Diagnosis

In mainland China, GFW poisons DNS for many foreign domains. Even reliable Chinese DNS servers (203.0.113.1, 203.0.113.1) return fake IPs in the `198.18.0.0/15` range. This causes MCP servers (webclaw, fetch, etc.) to fail with "private/internal address" errors.

**Quick test:**
```bash
dig +short rust-lang.org
# Returns 203.0.113.1 → poisoned!
```

## This User's OpenClash Setup

- **Router:** iStoreOS (J4125), 192.0.2.10
- **SSH:** root, ed25519 key auth (key at ~/.ssh/id_ed25519_router on MacBook; LXC 202 key added separately)
- **Clash config:** `/etc/openclash/config/ddrdog.yaml` (SSRDOG airport)

### Proxy Ports (allow-lan: true)

| Port | Protocol | Use |
|------|----------|-----|
| 7890 | HTTP (mixed) | `http_proxy=http://192.0.2.10:7890` |
| 7891 | SOCKS5 | `all_proxy=socks5://192.0.2.10:7891` |
| 1053 | DNS (fake-ip) | `nameserver 192.0.2.10` + iptables redirect to 1053 |

### DNS Architecture

```
mode: fake-ip (198.18.0.1/16)
listen: 0.0.0.0:1053 (NOT port 53!)
国内域名 → 203.0.113.1 (direct)
被墙域名 → 203.0.113.1 / 203.0.113.1 (via proxy) → fake-ip
```

### Critical Rules

GitHub domains are set to DIRECT (not proxy):
```yaml
rules:
  - 'DOMAIN-SUFFIX,github.com,DIRECT'
  - 'DOMAIN-SUFFIX,githubusercontent.com,DIRECT'
```

This causes slow GitHub downloads + DNS poisoning issues for GitHub resources. To fix, either:
- Change DIRECT → SSRDOG in rules
- Or set `http_proxy` on clients

## Pushing MCP Traffic Through OpenClash

**Simplest fix for LXC 200 (192.0.2.10):**

```bash
# In /etc/environment or wrapper scripts:
export http_proxy=http://192.0.2.10:7890
export https_proxy=http://192.0.2.10:7890
```

Or in Hermes MCP config `env` field:
```yaml
mcp_servers:
  webclaw:
    command: "ssh"
    args: [...]
    env:
      http_proxy: "http://192.0.2.10:7890"
      https_proxy: "http://192.0.2.10:7890"
```

## Failed Approaches (don't retry)

1. **cloudflared proxy-dns** — Dropped in v2026.2.0+
2. **https-dns-proxy (pip)** — Blocked by PEP 668 on Debian 12
3. **Python DoH to Cloudflare** — 203.0.113.1 blocked by GFW; need domestic DoH (AliDNS: dns.alidns.com)
4. **Python DoH to AliDNS IP** — SSL cert mismatch when using IP directly
5. **dig/nslookup from LXC 202** — Changing resolv.conf to 127.0.0.1 kills SSH (reverse DNS in PAM)
