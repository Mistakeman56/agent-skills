# OpenClash × Tailscale 直连打洞修复

## 问题症状
Tailscale 设备之间无法建立直连（direct connection），全部流量走 DERP 中继：
```
$ tailscale ping <peer>
pong from <peer> via DERP(hkg) in 275ms
pong from <peer> via DERP(hkg) in 1.25s
direct connection not established
```

而关闭 OpenClash 后可以个位数延迟直连。

## 根因分析

OpenClash 透明代理有多层劫持（mangle + DNAT），分别影响 Tailscale 的不同协议。**DNAT 层是最隐蔽的根因，容易被忽略：**

### 1. TCP REDIR (7892) — 劫持控制平面
`nftables chain openclash`: 所有非本地 TCP → `redirect to :7892`

Tailscale 的控制平面通信（api.tailscale.com:443、DERP 注册、打洞协商）是 TCP，全部被吸入 Clash。
- 虽然 Clash 规则有 `PROCESS-NAME,tailscaled,DIRECT`，但**REDIR 模式（PREROUTING 阶段）下 PROCESS-NAME 规则不生效**——Clash 不知道原始进程名。
- DOMAIN-SUFFIX 规则依赖 SNI 嗅探成功，嗅探失败则盲匹配。

### 2. UDP TPROXY (7895) — 威胁打洞流量
`nftables chain openclash_mangle` + `openclash_mangle_output`:
- 入站 UDP（PREROUTING）：所有局域网内 UDP → `jump openclash_mangle`
- 出站 UDP（OUTPUT）：软路由自身 UDP → `jump openclash_mangle_output`
- 虽然最后只有 `daddr 198.18.0.0/16` 才进 TPROXY（Fake-IP 范围），但链中的匹配开销和规则遍历仍有不确定性。

### 3. DNS 劫持 (53 → localhost) — 破坏 DERP/STUN 发现
OpenClash Fake-IP DNS 劫持所有 53 端口查询。Tailscale 的 netcheck 明确报告：
```
System DNS config not ideal. /etc/resolv.conf overwritten.
```
虽然 `fake-ip-filter` 包含 `*.tailscale.com`，但 DERP 服务器的 IP 是启动时批量解析并缓存的。如果缓存的 IP 被 Fake-IP 污染，后续打洞协商就会使用错误的地址。

### 4. 软路由自身流量被双重影响
软路由（192.0.2.10）同时是 OpenClash 主机和 Tailscale 节点，其自身出站 UDP 走 `openclash_mangle_output` 链。已有的避让规则（`ip saddr 192.0.2.10 udp sport 41641 return`）只覆盖了特定内网设备，**不覆盖软路由自身的 Tailscale 进程**。

### 5. 🔴 DNAT 层劫持 WAN 入站 41641（最隐蔽的根因）

**问题描述：** iStoreOS 防火墙的 `dstnat_wan` 链可能有一条 DNAT 规则，将所有 WAN 入站 UDP 41641（Tailscale WireGuard）和 41643 流量重定向到另一个内网设备：

```
# 查看（iStoreOS nftables）
nft list chain inet fw4 dstnat_wan

# 问题规则示例（`!fw4: tailscale` 注释）
meta nfproto ipv4 udp dport 41641 dnat ip to 192.0.2.10:41641
meta nfproto ipv4 udp dport 41643 dnat ip to 192.0.2.10:41643
```

**影响：** 外部发到软路由公网 IP:41641 的打洞包在 **PREROUTING DNAT** 阶段就被截胡转发到 192.0.2.10，软路由本机的 `tailscaled`（监听 `0.0.0.0:41641`）收不到打洞请求 → 入站方向永远无法直连。这就是为什么从软路由 ping 外网设备可能通（出站不受影响），但反向 ping 不通（入站被 DNAT 截胡）。

**检测方法：**
```bash
# 验证 WAN 入站 41641 流向了哪里
nft list chain inet fw4 dstnat_wan | grep 41641

# 看 conntrack 确认 DNAT 生效
cat /proc/net/nf_conntrack | grep 'dport=41641'

# 查出被 DNAT 的目标设备
arp -n | grep <target_ip>
```

**验证 DNAT 存在的方法（从外往内看）：**
```bash
# 在软路由上检查 DNAT 表
nft list chain inet fw4 dstnat 2>/dev/null          # 一级链
nft list chain inet fw4 dstnat_wan 2>/dev/null       # WAN 入站
nft list chain inet fw4 dstnat_lan 2>/dev/null       # LAN 反射

# 看 conntrack 中 41641 的连接
cat /proc/net/nf_conntrack | grep '41641' | head -5
```

**修复方法（在 dstnat_wan 链最前面插入豁免）：**
```bash
nft 'insert rule inet fw4 dstnat_wan udp dport 41641 return'
nft 'insert rule inet fw4 dstnat_wan udp dport 41643 return'
```

**为什么这个容易被忽略：**
- mangle 表检查了但没有问题
- OpenClash 日志显示 TCP 正常（`tailscaled → ... match ProcessName(tailscaled) using DIRECT`）
- 从软路由 ping 外部设备能通（出站方向，走 OUTPUT 链）
- 只有**从外部到软路由的入站方向**才触发 DNAT 问题
- 之前的 conntrack 检查看到的是单方向流量，没有意识到是 DNAT 截胡

## 修复方案

### nftables 精确端口豁免（已验证有效）

在 OpenClash 的三条链最前面插入 Tailscale 端口直接 return，同时修复 DNAT 层的劫持：

```bash
# === 第一层：mangle 表绕过（UDP 不被 TPROXY）===

# 入站 UDP — 接收来自 WAN 的 Tailscale 打洞请求（WireGuard + STUN）
nft 'insert rule inet fw4 openclash_mangle udp dport 41641 return'
nft 'insert rule inet fw4 openclash_mangle udp dport 3478 return'

# 出站 UDP — 软路由自身 Tailscale 发起的流量
nft 'insert rule inet fw4 openclash_mangle_output udp sport 41641 return'
nft 'insert rule inet fw4 openclash_mangle_output udp dport 41641 return'
nft 'insert rule inet fw4 openclash_mangle_output udp dport 3478 return'

# TCP — Tailscale fallback control plane
nft 'insert rule inet fw4 openclash tcp dport 41641 return'

# === 第二层：DNAT 表绕过（WAN 入站 41641/41643 不被 DNAT 到其他设备）===

nft 'insert rule inet fw4 dstnat_wan udp dport 41641 return'
nft 'insert rule inet fw4 dstnat_wan udp dport 41643 return'
```

### 持久化

写入 `/etc/openclash/custom/openclash_custom_firewall_rules.sh`：

```sh
#!/bin/sh
. /usr/share/openclash/log.sh
. /lib/functions.sh

LOG_OUT "Tip: Adding Tailscale bypass rules..."

nft 'insert rule inet fw4 openclash_mangle udp dport 41641 return' 2>/dev/null
nft 'insert rule inet fw4 openclash_mangle udp dport 3478 return' 2>/dev/null
nft 'insert rule inet fw4 openclash_mangle_output udp sport 41641 return' 2>/dev/null
nft 'insert rule inet fw4 openclash_mangle_output udp dport 41641 return' 2>/dev/null
nft 'insert rule inet fw4 openclash_mangle_output udp dport 3478 return' 2>/dev/null
nft 'insert rule inet fw4 openclash tcp dport 41641 return' 2>/dev/null
nft 'insert rule inet fw4 dstnat_wan udp dport 41641 return' 2>/dev/null
nft 'insert rule inet fw4 dstnat_wan udp dport 41643 return' 2>/dev/null

LOG_OUT "Tailscale bypass rules added successfully"
exit 0
```

**注意：**
- `2>/dev/null` 防止重复插入报错（规则已存在时 nft 会报错，但不影响功能）
- OpenClash 每次启动/重启时会自动执行此脚本，规则在 OpenClash 的 nftables 规则创建完成后插入
- 脚本使用 `insert rule`（最前面插入），确保 Tailscale 豁免优先于其他 Clash 规则

## 替代/互补方案（如上述不够彻底）

### 方案 B: OpenClash 访问控制 → 本机不代理
OpenClash LuCI → 全局设置 → 访问控制 → 本机代理改为「不代理」。
**代价：** 软路由自身所有流量不再走代理。

### 方案 C: 关闭 Fake-IP DNS 模式
OpenClash LuCI → DNS 设置 → 改为 Redir-Host 模式。
**代价：** DNS 可能被污染，部分国内网站 CDN 调度异常。

### 方案 D: dnsmasq 固定 Tailscale 域名
在 `/etc/dnsmasq.conf` 或 OpenClash 「指定域名不经过 DNS 劫持」：
```
server=/tailscale.com/203.0.113.1
server=/ts.net/203.0.113.1
```

## 验证方法

```bash
# 在软路由上
tailscale ping <peer_ip>

# 成功标志：输出中出现 "via X.X.X.X:41641"（直连IP），而非 "via DERP(...)"（中继）
# 例如：
# pong from macbook-air via 203.0.113.1:41641 in 92ms  ← 直连成功
# pong from macbook-air via DERP(hkg) in 1.25s            ← 走中继（失败）
```

## 关键原理备忘

| Tailscale 端口 | 协议 | 用途 |
|---|---|---|
| 41641 | UDP | WireGuard 数据面（主要打洞端口） |
| 41641 | TCP | WireGuard TCP fallback |
| 3478 | UDP | STUN (NAT 类型探测) |
| 443 | TCP | 控制平面 (api.tailscale.com, DERP 注册) |

**为什么 PROCESS-NAME 规则在 REDIR/TPROXY 下无效：**
- REDIR 工作在 PREROUTING 阶段，此时连接还在内核网络栈，Clash 看到的只有 IP+端口，无法获知原始进程名
- TPROXY 同理
- PROCESS-NAME 规则仅在 **TUN 模式**（Clash 创建虚拟网卡并成为默认网关）下有效，因为流量经过 Clash 用户态 TUN 设备时可以获取进程信息
