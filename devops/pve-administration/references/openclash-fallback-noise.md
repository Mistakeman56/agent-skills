# OpenClash 兜底规则造成的“噪音连接”（the user's home）

## 现象：连接列表里一大堆无名连接
`MATCH → SSRDOG(日本)` 是兜底。**任何没被规则的流量都会被丢去日本**，在连接列表里表现为一堆 `Match / SSRDOG Japan` 的条目。

## 已定位的噪音源（别重复查）
| 目标 | 频次 | 源头 | 性质 |
|---|---|---|---|
| `www.zoom.com` | ~1098/9h（~30s 一次） | **锐捷 AP .117(一楼) / .174(三楼)** | 疑似 AP 连通性自愈探测；无害但刷屏。**不要改直连** —— Zoom 在国内被墙，改 DIRECT 可能让 AP 探测失败 |
| `api.ip.sb` + `api.ipify.org` | 每 30 分钟 | PC .123 | 某程序查自己公网 IP；走代理会看到日本 IP |
| `203.0.113.1` / `203.0.113.1` / `203.0.113.1`（Hetzner 德国） | `:80` 每 5 分钟；`:3478` 持续 | PC .123 | **Tailscale**（法兰克福 DERP relay + STUN 节点，Hetzner 托管）；PC 上确有 `tailscaled.exe`。无害，**别再当悬案查** |
| `array401/402.prod.do.dsp.mp.microsoft.com`、`settings-win.data.microsoft.com`、`v10/v20/self/mobile.events.data.microsoft.com`、`edge.microsoft.com` | 共 ~130 | PC | 微软遥测，可加直连 |
| `some.url` | 39 | — | 占位符 URL（某脚本没配完），非真实域名 |

## 端口 → 归属 快速判据（先按端口定性，再决定值不值得挖）
- `:3478` = **STUN**（NAT 穿透探测）→ Tailscale / WebRTC，**不是恶意连接**
- 德国 Hetzner（`167.235.x` / `49.12.x` / `49.13.x`）+ `:80` / `:443` = **Tailscale DERP relay（法兰克福）**；见到先往 Tailscale 上想
- `:41641` = **Tailscale 直连**（默认 WireGuard 端口）
- `:7826` / `:8082`，或对端 PTR 含 `adsl` = **PCDN 数据通道** → 见 `pcdn-blocking-and-fakeip-bypass.md`
- 客户端连自己公网 IP 的高位端口（`203.0.113.1:5xxxx`）= **Tailscale 打洞成功的直连**，不是异常

## ★ 关键：自家 DDNS 不受影响
`~/.hermes/scripts/ddns-sync.py` 取 IP 的方式是 **SSH 到路由器执行 `ifconfig pppoe-wan`** → 拿到真实 WAN IP，**完全绕开代理**。所以“某程序走代理看到日本 IP”不会污染 DNS。

## 直连白名单（SRC-IP-CIDR，在 `openclash_custom_rules.list`）
```
SRC-IP-CIDR,192.0.2.10/32,DIRECT   # 绿联 NAS
SRC-IP-CIDR,192.0.2.10/32,DIRECT
```
注意：**Hermes CT(.213) / PVE(.134) / PC(.123) / AP 都不在白名单**，它们的未匹配流量同样会被丢去日本。

## 端口地图（2026-10 实测，`/etc/openclash/9.1.yaml`）
```
mixed-port: 7893    port: 7890(HTTP)    socks-port: 7891
redir-port: 7892    tproxy-port: 7895   Clash DNS: 7874
fake-ip-range: 198.18.0.1/16
```

## 为什么“改成 fake-ip 了连接里还是写 Redir”
**两个不同层面，不矛盾：**
- `Redir` = **入站方式**（nftables REDIRECT 到 redir-port）
- `fake-ip` = **DNS 层行为**（回 198.18.x.x）

完整链路（已实测验证）：
```
① nft: dport 53 → redirect to :53        （DNS 劫持）
② Clash DNS(7874) 回假 IP 198.18.x.x
③ nft: ip daddr 198.18.0.0/16 → redirect to :7892   ← 假 IP 流量因此进 Clash
④ Clash 从 redir-port 收到 → 连接类型 = Redir
⑤ 用假 IP 反查映射表 → 还原域名（所以列表显示域名而非 IP）
```
- TCP → REDIRECT(7892) → 显示 `Redir`；UDP → TPROXY(7895) → 显示 `TProxy`
- **“连接列表能显示域名”本身就是 fake-ip 在生效的铁证**（redir-host 模式只能看到 IP，除非 SNI 嗅探）
