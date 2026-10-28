# Tailscale 串流（Moonlight/Sunshine）卡顿诊断 — 流量路径 + 吞吐 + DERP 横跳（2026-08 实测）

## 触发场景
MTU 已降到 1100 但串流还是卡（"好了一点点"），或用户说"以前 1080p60 流畅，现在只能 720p30"。
**别停在 MTU 上** — 继续诊断：连的是哪台设备、实际吞吐多少、路径是否在 direct↔DERP 之间横跳。

## 1. 先确认串流流量真正经过哪台设备（关键！）
服务器上 `tailscale ping` 显示 DERP ≠ 用户实际串流路径。服务器可能只是控制面节点，
真正承载串流的是用户 PC/手机。查路由器 conntrack 找真实数据流：

```bash
ssh -p 2222 root@ROUTER "cat /proc/net/nf_conntrack | grep '<peer_public_ip>' | grep -v UNREPLIED"
# 例: src=203.0.113.1 dst=203.0.113.1 sport=6441 dport=41641 [ASSURED]
#     src=192.0.2.10 ... ← .123(<PASSWORD> PC) 才是串流设备，不是服务器 .213！
# 若只看到服务器IP(.213)的少量包 → 服务器只是控制面连接，串流在别的设备
```
**在错误的设备上改 MTU 等于没改。** 先定位设备：`cat /tmp/dhcp.leases | grep <IP>` 拿主机名。

## 2. conntrack 两次采样算实时吞吐（路由器上，不用 tcpdump）
```bash
ssh -p 2222 root@ROUTER "
cat /proc/net/nf_conntrack | grep '203.0.113.1' | grep -v UNREPLIED
sleep 3
cat /proc/net/nf_conntrack | grep '203.0.113.1' | grep -v UNREPLIED"
# 下行差值 bytes / 3s ≈ 实际串流带宽
# 2026-08 实测: 只有 2.5Mbps 下行 → Moonlight 1080p60 要 10-20Mbps → 差 4-8 倍 = 必然卡
# 上行小(几十KB/s) 正常 = 控制输入
```

## 3. tcpdump 抓 WAN 口看包模式（路由器有 tcpdump，无 timeout 命令）
```bash
ssh -p 2222 root@ROUTER "tcpdump -i pppoe-wan -nn -c 200 'udp and host <peer_ip> and len>1000'"
# 大包(1104B=WireGuard加密后的串流帧)成簇到达(同一时间戳4-8个) = 缓冲/积压后爆发
# 平滑流应该均匀分布；成簇 + 偶发断档 = UDP 丢包/乱序 → "时而清晰流畅、时而卡顿模糊"
# 对照: 抓包显示直连数据存在(ASSURED) ≠ 路径健康 — 还要看包到达模式
```

## 4. 反复横跳 (direct↔DERP) 本身也是卡因
`tailscale ping --c 1` 单发循环 10 次（`-c 10` 只显示一条，不可靠；偶发 timeout = 隧道抖动）。
direct 21ms 和 DERP(tok) 263-374ms 交替出现 = 打洞不稳定，路径频繁切换 → 串流掉帧。
此时 MTU 修的是丢包，DERP 绕路修不了（是 NAT/打洞问题）。
优先排查：对端是否开代理/VPN（破坏 UDP 打洞）；`tailscale netcheck` 看 PortMapping 是否为空。

## 5. Clash 侧确认（排除法）
- `uci get openclash.config.enable_udp_proxy` = 0（UDP 不代理）→ 基本排除 Clash 劫持 UDP
- 自定义规则文件 `/etc/openclash/custom/openclash_custom_rules.list` 应有:
  `PROCESS-NAME,tailscaled,DIRECT` / `DST-PORT,41641,DIRECT` / `IP-CIDR,100.64.0.1/10,DIRECT`
  （注意 `.bak` 文件里有 ≠ 当前生效文件里有 — 直接 cat 当前文件确认）
- 服务器 tailscaled 启动脚本要 unset 全部代理变量（`start-tailscaled.sh` 模式），否则控制面走
  Clash → 打洞协调被干扰

## 结论框架（按证据给结论，别乱甩锅）
- 大包丢 + 直连 → MTU（见 `tailscale-mtu-large-packet-loss.md`）
- 直连 ↔ DERP 横跳 → 打洞/NAT/对端代理
- 吞吐 2.5Mbps vs 需求 10-20Mbps → 带宽不够（跨运营商链路或 DERP 中继限速）
- 包成簇到达 → UDP 丢包/乱序
