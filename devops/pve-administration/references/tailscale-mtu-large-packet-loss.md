# Tailscale "ping正常但连接卡" = 大包丢包 → MTU 问题（2026-08 实测）

## Symptom
User reports: Tailscale connection to a friend (跨运营商, e.g. 大连联通 ↔ 沈阳移动) feels laggy /
数据传输卡, but latency looks normal (21ms, direct). "以前很流畅，最近很卡".

## Critical insight: latency normal ≠ connection healthy
Small packets (default `tailscale ping` / ICMP) can pass fine while **large packets drop**.
Tailscale uses WireGuard (encrypted, header overhead); if the underlying cross-carrier link has a
lower effective MTU than 1280 (Tailscale default), large packets get silently dropped — chat/ping
fine, file transfer/gaming/video stutters.

## Diagnosis (exact commands)

```bash
# 1. Check connection path — direct vs DERP relay
tailscale status | grep <peer>
#    direct 203.0.113.1:6441 = P2P direct
#    via DERP(tok/hkg/...) = relay (also causes lag, different root cause)

# 2. THE KEY TEST: large-packet ping over the tailnet
#    -s 1400 ≈ WireGuard payload size with typical MTU 1280
timeout 8 ping -c 6 -s 1400 <peer_tailscale_ip>
#    25-50% loss at 1400 = MTU/fragmentation issue
#    compare: small ping (default 64B) shows 0% loss → confirmed

# 3. Confirm it's the tailnet, not the underlying network:
#    try lowering tailscale0 MTU and re-test
ip link set dev tailscale0 mtu 1200; sleep 2
timeout 8 ping -c 6 -s 1200 <peer_tailscale_ip>   # 0% loss → MTU was the issue
ip link set dev tailscale0 mtu 1100; sleep 2
timeout 8 ping -c 6 -s 1100 <peer_tailscale_ip>   # 0% + stable 22ms = sweet spot
ip link set dev tailscale0 mtu 1280               # restore

# 4. Optional: check magicsock logs for MTU negotiation
journalctl -u tailscaled | grep -iE 'mtu|disco'
#    "now using <ip>:<port> mtu=1360" then "mtu=1428" jumping = unstable link MTU
```

## Results (measured 2026-08)
| tailscale0 MTU | large-packet loss | latency |
|---|---|---|
| 1280 (default) | 50-100% ❌ | unstable |
| 1200 | 0% ✅ | avg 58ms, some jitter |
| **1100** | **0% ✅** | **avg 22ms, stable** |

## Root cause context
- Cross-carrier links (移动↔联通, or 电信↔移动) frequently have effective MTU < 1500,
  and WireGuard overhead (80+ bytes) pushes 1280-MTU packets over the limit.
- Symptom is intermittent because MTU can vary by routing path / time of day (ISPs adjust).
- **Not Clash/proxy's fault** in the verified case — UDP proxy was off, 100.64.0.1/10 had DIRECT
  rule, and the traffic was already direct (21ms).

## Fix
**Both ends** must lower the Tailscale adapter MTU (the lower one wins on the path):

```bash
# Linux (persistent — add to tailscaled start script or a systemd ExecStartPre):
ip link set dev tailscale0 mtu 1100

# Windows (admin CMD, persistent):
netsh interface ipv4 set subinterface "Tailscale" mtu=1100 store=persistent
```

Forcing DERP relay (Tokyo/HK) is an alternative when the direct path is permanently bad — DERP
servers have optimized networks — but the MTU fix keeps the direct 20ms path.

## Pitfalls
- `tailscale ping --size` does NOT exist — use plain `ping -s` to the tailscale IP.
- Regular `ping` to the peer's **public IP** (e.g. 203.0.113.1) may 100% loss because their
  firewall blocks ICMP — that's normal, don't treat it as the issue.
- DERP vs direct can flip over time (打洞成功时直连21ms，失败时绕东京DERP 285-870ms)。若 `tailscale ping`
  显示 direct 但大包丢，优先 MTU；若显示 DERP，优先 NAT/打洞问题（见 pve-administration Tailscale 段）。
