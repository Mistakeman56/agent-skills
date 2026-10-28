# 全家 IPv6 打通（2026-10-07 实战，已验证）

**症状**：PC 有全球地址 `2408:822f:...` + `::/0` 路由，但 `ping -6` 外网 100% 丢包；浏览器也从不用 v6。

## 两个真根因（要分层查，别只看一层）

### 1) 路由器 IPv6 转发是关的 —— 有地址但出不去

```bash
ssh -p2222 root@192.0.2.10 "sysctl net.ipv6.conf.all.forwarding"
# 症状时返回 net.ipv6.conf.all.forwarding = 0
```

**定位手段（决定性证据）**：路由器上同时抓两端
```bash
sh -c 'tcpdump -i pppoe-wan -n icmp6 -c 40 > /tmp/wan.log 2>&1 &'
sh -c 'tcpdump -i br-lan  -n icmp6 -c 40 > /tmp/lan.log 2>&1 &'
# 另开一个 ssh 让 PC: ping -6 -n 6 <外网v6>
killall tcpdump; cat /tmp/wan.log /tmp/lan.log
# lan.log 里有 echo request，wan.log 0 packets → 路由器本地丢，不是上游问题
```
⚠️ 路由器 BusyBox **没有 `timeout`** 命令（`sh: timeout: not found`）→ 用 `tcpdump -c N` + 事后 `killall tcpdump`。

**修复（已做，持久化也做了）**
```bash
sysctl -w net.ipv6.conf.all.forwarding=1
# 持久化：/etc/rc.local 里、必须在 exit 0 之前加
sed -i "/^exit 0/i sysctl -w net.ipv6.conf.all.forwarding=1 >/dev/null 2>&1" /etc/rc.local
```
- 开机其实由 `/etc/init.d/sysctl`(S11) 读 `/etc/sysctl.d/10-default.conf`(=1) 兜底；rc.local 是二重保险。
- **谁把它弄成 0 的**：OpenClash 脚本里**没有任何 sysctl 调用**（grep 证实），最可能是用户在 LuCI 手动关过 IPv6 那次留下的（一次性残留，不是常驻进程在改）。30 秒采样两次都稳定在 1。

### 2) Clash 顶层 `ipv6: false` —— DNS 永远不回 AAAA

```bash
# 诊断：两层 DNS 对比（AAAA 挂了 → ANSWER: 0）
dig @192.0.2.10 www.baidu.com AAAA +short          # 空
dig @192.0.2.10 -p 7874 www.baidu.com AAAA        # status NOERROR, ANSWER: 0 ← 元凶
dig @192.0.2.10 www.baidu.com A +short             # 正常 → 只有 AAAA 被吃
# 对照：ISP DNS 能给 AAAA
nslookup www.baidu.com 203.0.113.1                    # A + AAAA 都有
```
运行配置是 `-f /etc/openclash/9.1.yaml`（由 `/etc/openclash/config/9.1.yaml` 生成）。
- **`dns:` 段里 `ipv6: true`（UCI `openclash.config.ipv6_dns='1'` 已开）没用** —— 起决定作用的是**顶层 `ipv6:`**。

**修复（已做）**
```bash
cp /etc/openclash/9.1.yaml /root/9.1.yaml.before-ipv6-fix.bak
cp -a /etc/openclash/config /root/openclash-config-bak-ipv6
sed -i "7s/ipv6: false/ipv6: true/" /etc/openclash/9.1.yaml          # 运行配置
sed -i "s/ipv6: false/ipv6: true/g" /etc/openclash/config/*.yaml      # 所有配置副本，防止重启用回 false
killall clash    # openclash_watchdog.sh 会在 ~10s 内用原参数拉起：/etc/openclash/clash -d /etc/openclash -f /etc/openclash/9.1.yaml
```
**不要用 `/etc/init.d/openclash restart`**：那会重刷 nftables 规则（用户的红线）。只 kill clash 进程，看门狗拉起，防火墙一条不动。

## 修好后的正确形态（验证用）

| 检查 | 期望 |
|---|---|
| `dig @192.0.2.10 www.baidu.com AAAA` | 有 `2408:871a:...` |
| `dig @192.0.2.10 www.google.com AAAA` | **空**（fake-ip 域名不发 AAAA → 国外不会绕过代理走 v6，不会 v6 泄漏） |
| PC `curl.exe -6 https://www.bilibili.com/` | code=200，`remote_ip=2408:...`，ttfb ~0.12s |
| PC `curl.exe https://www.google.com/generate_204` | code=204，`remote_ip=198.18.0.x`（仍走代理），0.16–0.31s |
| PC `ping -6 -n 4 2400:3200::1` | 0% 丢包 37ms |
| `ip -6 neigh show \| grep 2408` | 家里多台设备都有全球地址（SLAAC 自动发） |

实测：B站/百度/小红书都真实跑在 v6 上，国外站仍走代理 —— 正好是理想形态。

## 不要碰的两件事

1. **`openclash.config.ipv6_enable='0'`（IPV6代理）保持 0**。它 =1 会让 OpenClash 给 IPv6 加 tproxy/重定向规则 → **改 nftables**，是红线。当前形态（国内 v6 直连、国外 v4 走代理）不需要它。
2. **`/etc/rc.local` 里 `exit 0` 排在 `nft -f /etc/nftables.conf` 之前** → 那行 nft 恢复**从来没执行过**（重启后 devmon 表会丢，与 devmon 笔记的 pitfall 对得上）。要修得把 nft 那行挪到 exit 0 之前——那属于改防火墙加载时机，**必须先问用户**。

## 其他事实

- PD 租约很短（`ifstatus wan6` 的 prefix `preferred` ≈ 44 分钟），但**会自动续**（隔 40 分钟再看值会回升，不会归零）。别把它误判成「PD 要过期了」。
- 路由器自己出 v6 一直是通的：`ping -6 2400:3200::1` 35ms、`curl -6 https://www.baidu.com` 200 → 所以问题一定在 LAN 转发或 DNS 这两层。
- 前面「光猫死机」的推断是**错的**：用户澄清光猫从未死机（他主动关过、还优化过散热），PPPoE 重拨是用户操作/ISP 侧，别再提。
