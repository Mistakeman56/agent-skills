---
name: pve-administration
description: "Proxmox VE & homelab infrastructure administration: VM/LXC lifecycle, storage management, Clash/OpenClash proxy & DNS, GFW workarounds, Tailscale NAT bypass, NAS management (Jellyfin, music libraries), Docker proxy, firewall change control, router SSH defense, legacy OS deployment, image conversion, N5095 mini PC setup, Windows remote SSH patterns, Xiaomi Miloco smart home deployment, and troubleshooting from within an LXC container."
version: 1.0.0
author: Hermes Agent
platforms: [linux]
tags: [pve, proxmox, virtualization, vmware-migration, kvm]
---

## Triggers

- PVE host operations (VM/LXC create, start, stop, configure)
- 自建 **WireGuard** 替代 Tailscale、exit node 取舍、家宽出口基线（真公网 IPv4 / 全锥 NAT / path MTU 1492 / 无国内 DERP / TCP 被 Clash 劫持）；**iOS 客户端**用代理 App 内置 WG 节点 + 规则分流（单 VPN 互斥、策略名大小写、`tun-excluded-routes` 坑）→ 见 `references/selfhost-vpn-wireguard.md` 第 12 节
- 容器/VM **磁盘扩容**（根分区 96% 满、`vgs` 只剩 12G 但薄池还有 200G）→ 见 `references/disk-expansion.md`
- iStoreOS **应用过滤**（按 App + 时间段封禁、`ubus appfilter`、特征库自定义、分类正常却拦不住；**「抖音/B站/小红书按点全黑、百度和路由器本机却全通」反查真凶**）→ 见 `references/istoreos-app-filter.md`，抓包判据见 `references/network-slow-diagnosis.md` 的「动手前三问」与 oaf 段
- PVE **省电与自启**（RAPL 测功耗、`intel_idle.max_cstate`、CT onboot 白名单、WOL/通电自启、定时开关机收益评估、电源事件取证）→ 见 `references/power-autostart.md`
- OpenClash 插件/内核升级，以及「LuCI 显示已开启但代理不能用」→ 见 `references/openclash-proxy-upgrade.md`
- 千兆宽带、网卡/断/慢/间歇掉线 → `references/link-vs-app-throughput.md` `references/home-network-outage-forensics.md`
- **游戏瞬时卡顿/画面冻结/延迟读数不显示/对局掉线重连**（「就一瞬间卡」「延迟没显现」「一直掉线无数次」）→ 见 `references/game-stutter-latency-sampling.md`：1 秒粒度多路采样 + 三端时间对齐读相关性；**「一直掉线/间歇丢包」**→ 先布网关/公网/业务目标三路哨兵（同断=本机打嗝）→ 见 `references/network-slow-diagnosis.md`「哨兵先行法」
- 「关了 OpenClash 网还是卡/国内站波动」+「fake-ip 还是 redir-host」→ 见 `references/openclash-leftover-audit.md`
- 公网入口可达性排查（域名打不开/子域名却正常/端口连不上/裸域名不带端口/443 被运营商封/IPv6 入口）→ 见 `references/public-reachability.md`
- NAS administration (UGREEN SSH, Jellyfin, music libraries, **MoviePilot 整理/刮削、媒体库 inode 核验、MP 登录排障、多下载器转移做种/保种链路、转移归因与标签（谁转的/为什么没打标）**, **配置隐患体检见 `references/nas-health-audit.md`：SMART/smartd、硬盘休眠、UPS、容器信号、对外端口核对**, **下载/做种链路路径统一、`No data found` 分诊、「校验中→变成下载」重新做种分诊与原种找回、收到 .torrent 挂已有数据重做种（add→verify→start）、IYUU 转移规则与远程脚本传递见 `references/media-pipeline-paths.md`**)
- 宽带/链路吞吐排查（网卡协商正常但下载跑不满、Steam 只有几百兆、WAN 实测速率、怀疑运营商/链路瓶颈）→ 见 `references/broadband-throughput-triage.md`，采样脚本 `scripts/wan-throughput-sample.sh`
- 内网设备清点与 DHCP 静态绑定命名（「找出某品牌 AC/AP 的内网 IP」「让这些 IP 保持不变并在软路由里标记」）→ 见 `references/lan-inventory-and-dhcp-reservations.md`
- OpenClash 维护与升级（「开着但代理不好用」、开机自启未注册、407 代理认证、插件/内核版本升级与回滚）→ 见 `references/openclash-upgrade-and-autostart.md`
- 换/更新订阅链接（「拉个新订阅」「协议升级换链」「规则啥的都要保留」）→ 见 `references/openclash-subscription-update.md`
- 切节点/切国家与多地同条件测速（「全都用 X 节点」「切过去试试网速」、Clash API 401、store-selected 覆盖 now）→ 见 `references/openclash-node-switching.md`
- Legacy OS deployment (Win2K, XP, XPenology)
- Network issues behind GFW (DNS failures, proxy misconfiguration, TLS errors)
- Clash/OpenClash debugging (fake-IP, slow network, config mismatch)
- fake-ip「完美」/ 谷歌油管打不开 / iStore测速恒1M → `references/openclash-fakeip-perfect.md`
- Tailscale setup in LXC containers
- Docker proxy configuration
- Router SSH brute-force defense
- 局域网设备清点、MAC/OUI 厂商识别、角色判定、IP 固定与 DHCP 静态绑定/内网名 → 见 `references/lan-inventory-dhcp.md`
- Windows remote management (SSH, SMB, PowerShell)

**修故障的硬要求（the user's own words：一劳永逸）**：根因 + 全链路一次改到位，**不接受拿定时自检/轮询告警当修复方案**（那是补丁不是修复）；改动前先做时间戳备份并说明回滚方式，改完实测验收再汇报，不复述中间过程。

## Domain-Specific Guides

| Guide | When to use |
|-------|------------|
| [references/win2000-pve-lab.md](references/win2000-pve-lab.md) | Win2000 VM setup on PVE for network security lab — pitfalls and approach |
| [references/windows-remote-assist.md](references/windows-remote-assist.md) | Guide Windows users through OpenSSH setup for remote assistance via Tailscale, gaming latency diagnostics, PowerShell encoding |
| [references/palworld-server-deployment.md](references/palworld-server-deployment.md) | Palworld dedicated server on PVE LXC — requirements, installation, memory planning, Tailscale connectivity |
| [references/switch-hardware-recommendations.md](references/switch-hardware-recommendations.md) | Network switch hardware recommendations — 48-port 100M/1G models, pricing, search keywords for Xianyu |
| [references/router-malware-incident-response.md](references/router-malware-incident-response.md) | 路由器挖矿入侵排查清单 + CodeServer漏洞加固原则 + 全角/半角叹号密码坑 |
| [references/mcp-server-deployment-ct200.md](references/mcp-server-deployment-ct200.md) | 在 CT <ID>(mcp-server LXC) 部署第三方 Python MCP 服务器：OpenClash 代理 clone、pip 清华源装依赖、DrissionPage 无头 Chrome 补丁、mcp-compressor+SSH 注册、携程反爬打不破的结论 |
| [references/istoreos-coding-agents.md](references/istoreos-coding-agents.md) | 在 iStoreOS 路由器（J4125/8G/231G SATA）上装 AI 编程 agent：Claude Code（opkg node20 + npm 装到 SATA）与 Kimi Code（要 node≥22.19 → Docker node:24-alpine）、包装脚本模板、认证方式、卸载回滚、musl/glibc 坑 |
| [references/lucky-ddns-public-exposure.md](references/lucky-ddns-public-exposure.md) | 动态公网 IP 全链路：真假公网 IPv4 判定、Lucky DDNS 取值脚本（含内网地址保护）、反代前端/后端字段方向与自指循环诊断、DNAT 端口劫持、80/443 被封 + SSL DNS-01、来源判定测试页、Lucky HTTP API |
| [references/openclash-version-upgrade.md](references/openclash-version-upgrade.md) | OpenClash 插件 ipk + Mihomo 内核升级配方：备份三件套、GitHub 走代理下载与资产名匹配、先测新内核再覆盖、装 ipk 后 enable 被重置、只认 204 验收、回滚 |
| [references/istoreos-app-filter.md](references/istoreos-app-filter.md) | iStoreOS 应用过滤 OpenAppFilter：ubus 开关/时间段/选 App（数组否则 oafd segfault）、特征库自定义与重启加载、验证三件套，以及「分类正常却拦不住」的根因（OpenClash 全量 TCP redirect 抢走转发路径）与四个给用户的选项 |

---- Firewall change control (fw3/fw4/nftables)
- Network device monitoring (iStoreOS nftables counters, traffic stats, online status)

## PVE Administration

Manage Proxmox VE hosts and VMs from within an LXC container (no direct hypervisor access). Covers VM creation, image conversion, legacy OS deployment, Tailscale setup in LXC, and common pitfalls.

## Accessing PVE from LXC

**⚠️ CRITICAL: Save credentials to memory IMMEDIATELY when the user provides them.** The user has repeatedly expressed frustration about having to re-share passwords. When you receive credential information (host IP, username, password), call `memory(action='add', target='memory')` before doing anything else with it. This includes:
- PVE host credentials
- Router/switch credentials  
- NAS credentials
- Any service login

The memory entry should include: IP, username, password, and what service it's for.

**⚠️ PITFALL: 密码含叹号的全角/半角坑（2026-07 实测）。** 设备密码带 `!` 时，全角`！`和半角`!`混用会导致 SSH/LuCI 登录反复失败，排查半天找不到原因。用户最终删掉叹号才解决。遇到"密码明明对但登录失败"且密码含叹号：先让用户确认全角/半角，或建议改用不含易混字符的密码（避免 `!`、`O/0`、`l/1`、全角空格）。

```bash
# Example: save immediately on receipt
memory(action='add', target='memory', content='PVE 192.0.2.10 root/<PASSWORD>')
# THEN proceed with operations
```

The PVE host is typically on the same LAN/subnet as the container. Use `sshpass` for password authentication:

```bash
# Install sshpass if missing
apt-get install -y sshpass

# SSH with password
sshpass -p 'PASSWORD' ssh root@PVE_IP "pveversion"

# SCP files
sshpass -p 'PASSWORD' scp /local/file root@PVE_IP:/remote/path/
```

**⚠️ Security:** The password is visible in process list briefly. For repeated use, set up SSH key authentication.

### Finding the PVE Host

```bash
# Check default gateway (often the router, not PVE)
ip route | grep default

# Ping common PVE addresses
for ip in 192.0.2.{1..10}; do
  ping -c1 -W1 $ip 2>/dev/null | grep -q "bytes from" && echo "$ip ✅"
done

# Check if a host responds on PVE port
curl -sk https://192.0.2.X:8006 2>&1 | head -3
```

### Accessing LXC Containers Through PVE Host (When Direct SSH Fails)

When a user says "SSH into 192.0.2.X" but `sshpass` authentication fails (Permission denied), the target might be a PVE LXC container. Use the PVE host as a jump box:

**Step 1: Identify the VM/CT on PVE**
```bash
sshpass -p 'PVE_PASS' ssh root@PVE_HOST "pct list; echo '---'; qm list 2>/dev/null | head -20"
# Find the VMID matching the target IP
```

**Step 2: Execute commands inside the LXC**
```bash
# Use lxc-attach for a single command
sshpass -p 'PVE_PASS' ssh root@PVE_HOST 'lxc-attach -n <VMID> -- bash -c '\\''echo "Inside LXC"; hostnamectl'\\'' 2>&1'

# Use pct enter for interactive shell (avoid in automation — it requires a TTY)
sshpass -p 'PVE_PASS' ssh -t root@PVE_HOST "pct enter <VMID>" 2>&1
```

**Step 3: For Docker containers inside the LXC**
```bash
sshpass -p 'PVE_PASS' ssh root@PVE_HOST 'lxc-attach -n <VMID> -- bash -c '\\''docker ps 2>/dev/null'\\'' 2>&1'
# Or with more complex commands:
sshpass -p 'PVE_PASS' ssh root@PVE_HOST 'lxc-attach -n <VMID> -- bash -c '\\''\necho "=== Docker containers ==="\ndocker ps --format "table {{.Names}}\\t{{.Image}}\\t{{.Status}}\\t{{.Ports}}"\necho "=== HA version ==="\ndocker exec <container_name> cat /config/.HA_VERSION 2>/dev/null\necho "=== Key config ==="\ndocker exec <container_name> cat /config/configuration.yaml 2>/dev/null\n'\\'' 2>&1'
```

### Credential Recovery (When User Doesn't Know Container Password)

When the user asks for an LXC container's login and doesn't know the credentials, set a known password through the PVE host:

```bash
# Set root password via PVE (works even if SSH is broken)
sshpass -p 'PVE_PASS' ssh root@PVE_HOST "pct exec <VMID> -- bash -c 'echo root:NEWPASSWORD | chpasswd'"

# Verify it works
sshpass -p 'NEWPASSWORD' ssh root@CONTAINER_IP "whoami && hostname"
```

**Key points:**
- `pct exec` runs commands inside the container as root — no existing password needed
- After setting, also verify SSH is enabled (`PermitRootLogin yes`, `PasswordAuthentication yes` in `/etc/ssh/sshd_config`)
- The container IP may differ from what's in memory — always confirm with `pct exec <VMID> -- ip addr show eth0 | grep inet`
- Save the credentials to memory immediately after confirming they work

**Why direct SSH might fail:**
- The LXC container may not have SSH installed or running
- root password may differ from the PVE host password
- The SSH config may only accept key-based auth
- The container was created without OpenSSH server (common for single-purpose LXCs like homeassistant)

**Don't do:** Keep trying different passwords on the LXC's SSH. If `pct list` shows it's a container, use `lxc-attach` through the PVE host instead.

## ⚠️ 关机前必须检查onboot + startup order

当用户要关闭PVE宿主机（如开VT-d、换硬件、维护）时，**先检查所有容器的onboot设置和启动顺序**。否则重启后容器没自启，或者启动顺序不对导致依赖服务先于提供者启动。

### Step 1: 检查onboot

```bash
sshpass -p 'PASS' ssh root@PVE_HOST "
for ct in \\$(pct list | awk 'NR>1{print \\$1}'); do
  echo -n \\\"CT\\$ct: \\\"
  pct config \\$ct 2>/dev/null | grep onboot || echo 'not set'
done
"
# 发现没开的，批量开：
sshpass -p 'PASS' ssh root@PVE_HOST 'for ct in 100 200 201 202; do pct set $ct --onboot 1; done'
```

### Step 2: 设置启动顺序（startup order）

容器按 `order` 值从小到大启动。**有依赖关系的容器必须按依赖链排顺序**（如 hermes-agent 依赖网络和 MCP 服务，应该最后启动）。

```bash
sshpass -p 'PASS' ssh root@PVE_HOST "
pct set 100 --startup order=1   # 基础服务先
pct set 200 --startup order=2   # mcp-server
pct set 201 --startup order=3   # homeassistant
pct set 202 --startup order=4   # hermes-agent（最后）
"
```

验证：
```bash
for ct in 100 200 201 202; do
  echo -n "CT$ct: "
  pct config $ct 2>/dev/null | grep -E 'onboot|startup' | tr '\n' ' '
  echo
done
```

### ⚠️ PITFALL: "CT is locked (mounted)" 无法 pct set

如果容器处于 `mounted` 状态（如备份/恢复后），`pct set --startup` 会报 `CT is locked (mounted)`。**绕过方法：直接编辑配置文件**

```bash
sshpass -p 'PASS' ssh root@PVE_HOST "
# 直接追加 startup 到配置文件（容器运行时也能改）
echo 'startup: order=4' >> /etc/pve/lxc/202.conf
grep startup /etc/pve/lxc/202.conf
"
```

**注意：** 这个方法绕过了 pct 的锁检查，但 PVE 会在下次加载配置时生效。不需要重启容器。

### Step 3: 验证服务自启动（hermes-agent 特有）

```bash
sshpass -p 'PASS' ssh root@PVE_HOST "
pct exec 202 -- systemctl status hermes-gateway 2>&1 | head -5
pct exec 202 -- systemctl show hermes-gateway | grep -E 'Restart=|After='
"
# 期望：Restart=always, After 包含 network-online.target
```

**典型场景：** 用户说"关机开VT-d" → 先查onboot → CT100没开 → 帮开上 → 设startup order → 再关机。

## LXC Container Lifecycle

### Starting a Stopped Container

When a user says "帮我开我的XX服务器" and the container is in `stopped` state:

```bash
# 1. List all containers to find the right one
sshpass -p 'PVE_PASS' ssh root@PVE_HOST "pct list"

# 2. Check the stopped container's config to understand what it runs
sshpass -p 'PVE_PASS' ssh root@PVE_HOST "pct config <VMID>"

# 3. Start it (pct start, NOT qm start)
sshpass -p 'PVE_PASS' ssh root@PVE_HOST "pct start <VMID>"

# 4. Wait a few seconds then verify status
sshpass -p 'PVE_PASS' ssh root@PVE_HOST "pct status <VMID>"
```

**Important:** LXC containers use `pct start`/`pct stop`, not `qm start`/`qm stop` (those are for KVM VMs).

### Finding a Container's IP After Start

```bash
# After starting, get the IP
sshpass -p 'PVE_PASS' ssh root@PVE_HOST "pct exec <VMID> -- ip addr show eth0 | grep 'inet ' | head -1"
```

## Tailscale Setup in Unprivileged LXC Containers

When you need Tailscale running inside an LXC container (for Tailscale SSH, subnet routing, or joining the user's tailnet):

### Prerequisites

LXC containers need `/dev/net/tun` device. Check first:
```bash
ls -la /dev/net/tun
# Should show: crw-rw-rw- 1 nobody nogroup 10, 200
```

If missing, configure at PVE host level:

```bash
# Option 1: Via pct set (requires STOPPED container — "CT is locked (mounted)" error means it's running)
pct stop <VMID>
pct set <VMID> -dev0 /dev/net/tun,pass
pct start <VMID>

# Option 2: Via config file edit (requires restart — less disruptive than full stop/start if server is running)
echo 'lxc.mount.entry: /dev/net/tun dev/net/tun none bind,create=file' >> /etc/pve/lxc/<VMID>.conf
pct restart <VMID>
```

**⚠️ Pitfall:** `pct set 202 -dev0 /dev/net/tun,pass` will fail with `400 Parameter verification failed. invalid format` if the container is **locked** (e.g. "mounted" state). The format error is misleading — the real issue is the lock. Use Option 2 or `pct stop` first.

### Installation Methods

**Option A: Apt Install (Recommended — works if apt is fast enough)**
```bash
apt-get update && apt-get install -y tailscale
```

**Option B: Binary Copy (when apt is too slow via proxy)**
When the PVE host network to Tailscale package repo is slow but another container already has Tailscale:
```bash
# 1. Find tailscale/tailscaled binaries on existing container
sshpass -p 'PVE_PASS' ssh root@PVE_HOST "pct exec <SOURCE_VMID> -- bash -c 'which tailscale; which tailscaled'"
# → typically /bin/tailscale (30MB), /sbin/tailscaled (40MB)

# 2. Copy via dd through PVE host (pct push/pop don't work for /sbin/ files)
# tailscale binary:
sshpass -p 'PVE_PASS' ssh root@PVE_HOST "pct exec <SOURCE_VMID> -- bash -c 'cat /bin/tailscale'" \
  | dd of=/usr/bin/tailscale bs=1M

# tailscaled binary:
sshpass -p 'PVE_PASS' ssh root@PVE_HOST "pct exec <SOURCE_VMID> -- bash -c 'cat /sbin/tailscaled'" \
  | dd of=/usr/sbin/tailscaled bs=1M

chmod +x /usr/bin/tailscale /usr/sbin/tailscaled
```

**Note on version mismatch:** The copied binary may be older than the latest release. That's fine — Tailscale is backward-compatible on the same tailnet. Just verify `tailscale version` after install.

### Starting tailscaled (no systemd available, no shell `&`)

LXC containers typically don't have systemd. Start as a Hermes background process (NOT with `&` — Hermes won't track shell-level background jobs):

```bash
# Clean up any stale socket/process
pkill -f tailscaled 2>/dev/null
sleep 1
rm -f /var/run/tailscale/tailscaled.sock 2>/dev/null

# DO: terminal(background=true, command='/usr/sbin/tailscaled --state=... --socket=...')
# DON'T: /usr/sbin/tailscaled ... &  (Hermes won't track shell backgrounding)
```

**⚠️ Pitfall:** `tailscale up` prints the auth URL but may timeout before user reads it. Tell the user the URL explicitly in your response, and keep the `tailscale up` command running with a generous timeout (30s+), or re-run it if the user needs more time.

### ⚠️ PITFALL: Proxy environment variables break tailscaled startup

LXC containers on iStoreOS networks inherit proxy env vars (CLASH_PROXY, HTTP_PROXY, HTTPS_PROXY, ALL_PROXY) from shell profiles (e.g. `/root/.bashrc`). These cause `tailscaled` to try connecting to Tailscale control plane **through the Clash proxy** — which either refuses the connection or returns errors.

**Symptoms:**
- `tailscale status` shows: `fetch control key: Get "...": proxyconnect tcp: dial tcp 192.0.2.10:7890: connect: connection refused`
- Or: `unexpected state: NoState` / `logged out`

**Root cause:** `tailscaled` reads proxy env vars from the process environment. The proxy at `192.0.2.10:7890` may require auth or may not forward Tailscale's WireGuard traffic correctly.

**Fix — unset ALL proxy vars before starting tailscaled:**
```bash
# Kill existing tailscaled
pkill tailscaled 2>/dev/null
sleep 1

# Start with clean environment (no proxy vars)
env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY \
    -u ALL_PROXY -u all_proxy -u CLASH_PROXY \
    tailscaled --state=/var/lib/tailscale/tailscaled.state &

# Verify (also need clean env for tailscale client)
env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY \
    -u ALL_PROXY tailscale status
```

**⚠️ PITFALL: `/usr/bin/tailscaled` can be a broken 64-byte wrapper!**

On some Debian installs, `/usr/bin/tailscaled` is a tiny shell wrapper that tries to `dd` from `/bin/tailscaled` (which doesn't exist). The real binary is at `/usr/sbin/tailscaled` (~40MB ELF). If `systemctl` reports `status=203/EXEC` or `status=127`, check:
```bash
ls -la /usr/bin/tailscaled   # 64 bytes = broken wrapper
ls -la /usr/sbin/tailscaled  # ~40MB = real binary
cat /usr/bin/tailscaled      # shows: dd: failed to open '/bin/tailscaled'
```
Fix: use `/usr/sbin/tailscaled` in any startup script or systemd unit.

**Persistent fix — systemd service with proxy-clearing wrapper:**

For containers with systemd (like CT <ID> hermes-agent), create a wrapper script + systemd service:

```bash
# 1. Create wrapper script that clears proxy env
cat > /usr/local/bin/start-tailscaled.sh << 'SCRIPT'
#!/bin/bash
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy CLASH_PROXY
exec /usr/sbin/tailscaled --state=/var/lib/tailscale/tailscaled.state --socks5-server=
SCRIPT
chmod +x /usr/local/bin/start-tailscaled.sh

# 2. Create systemd service
cat > /etc/systemd/system/tailscaled.service << 'EOF'
[Unit]
Description=Tailscale Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/start-tailscaled.sh
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# 3. Enable and start
systemctl daemon-reload
systemctl enable --now tailscaled
```

The wrapper script's `exec` replaces the shell with tailscaled, inheriting the cleaned environment. Verify with `systemctl status tailscaled` — confirm the binary path in the process line.

**Note:** Not all LXC containers have systemd. CT <ID> (hermes-agent) and CT100 (MC server) do. But many minimal Debian/Ubuntu LXC templates use SysVinit or no init. Check first: `ls /run/systemd/system` inside the container.

**Why Tailscale needs direct connections:** Tailscale uses WireGuard (UDP) for data and HTTPS to `controlplane.tailscale.com` for coordination. Routing through Clash proxy breaks both — Clash doesn't forward WireGuard UDP, and the HTTPS connection may get auth errors or timeouts.

### ⚠️ PITFALL: Tailscale NAT traversal depends on peer's network — campus/symmetric NAT can't be punched

Not all Tailscale peers can establish direct connections. Direct WireGuard connections require at least one side to have a routable UDP path (cone NAT or public IP). **Campus networks, corporate networks, and many Chinese ISPs use symmetric NAT**, which makes hole-punching impossible.

**Diagnosis — use `tailscale ping`, NOT regular `ping`:**
```bash
# Regular ICMP ping may show high latency (290ms+) even when WireGuard is direct (20ms)
# ALWAYS use tailscale ping to check actual WireGuard path:
tailscale ping -c 3 <peer_hostname>

# Good (direct):
# pong from mydevice (100.64.0.1) via 203.0.113.1:23588 in 20ms

# Bad (DERP relay):
# pong from mydevice (100.64.0.1) via DERP(hkg) in 290ms
# direct connection not established
```

**Key facts:**
- DERP relay adds 100-300ms+ latency — acceptable for chat, painful for gaming
- Direct connections can be **temporary** — a peer that's direct now may drop to DERP after network changes (DHCP renewal, NAT table timeout, ISP rebinding)
- The `netcheck` output shows UDP capability and nearest DERP — if `PortMapping: empty`, the node can't receive inbound connections
- **There is no fix for symmetric NAT** — the only workaround is DERP relay or the user changing their network

**When to check:**
- Before telling a friend "connect to Tailscale IP:25565" for gaming
- When user reports "Tailscale latency was good yesterday but now it's slow"
- When comparing CT100 (can't reach mydevice directly) vs CT <ID> (can) — both on same LAN, but path to peer depends on peer's NAT type

### Verification

```bash
tailscale status
# Should show the new node with its 100.x.x.x IP
```

## LXC Container Lifecycle

### Starting a Stopped Container

For game servers (Minecraft etc.) or any Java-based server, do a **systematic post-start check** to confirm the server is actually ready, not just the container:

```bash
# 1. Check if Java is running
sshpass -p 'PVE_PASS' ssh root@PVE_HOST "pct exec <VMID> -- ps aux | grep java | grep -v grep"

# 2. Find the server directory (from /proc/<PID>/cwd)
sshpass -p 'PVE_PASS' ssh root@PVE_HOST "pct exec <VMID> -- readlink /proc/<PID>/cwd"

# 3. Verify specific port is listening
sshpass -p 'PVE_PASS' ssh root@PVE_HOST "pct exec <VMID> -- ss -tlnp | grep <PORT>"

# 4. Check the log for "Done!" / "Ready!" marker (Minecraft-specific)
sshpass -p 'PVE_PASS' ssh root@PVE_HOST "pct exec <VMID> -- grep 'Done' <server_dir>/logs/latest.log"

# 5. From LXC, do an external port check
nc -zv <CONTAINER_IP> <PORT>
```

**Why this matters:** A container's `pct status` might say "running" before the application inside is ready. Java game servers can take 3-60 seconds to start depending on mod count. Don't tell the user it's ready until you see the "Done" log marker AND the port is responsive.

### Executing Commands Inside a Running Container

```bash
# Single command
sshpass -p 'PVE_PASS' ssh root@PVE_HOST 'pct exec <VMID> -- bash -c '\\''hostnamectl; docker ps'\\'' 2>&1'

# Check running processes
sshpass -p 'PVE_PASS' ssh root@PVE_HOST 'pct exec <VMID> -- ps aux | grep java'
```

## VM Management

### Create a VM

```bash
# List existing VMs/CTs
qm list
pct list

# Find available VM ID
for id in $(seq 100 400); do
  qm status $id 2>/dev/null || { echo $id; break; }
done

# Create VM with legacy OS compatibility (Win2K/XP era)
qm create <VMID> \
  --name <name> \
  --memory 1024 \
  --cores 2 \
  --cpu qemu64 \          # NOT 'host' when KVM unavailable
  --machine pc-i440fx-9.0 \  # NOT q35 for old OS
  --bios seabios \
  --net0 e1000,bridge=vmbr0 \
  --vga cirrus \
  --ostype l26 \
  --agent 0 \
  --ide2 none,media=cdrom \
  --boot order=ide0 \
  --onboot 0
```

### Import and Attach Disk

```bash
# Import disk image
qm importdisk <VMID> /path/to/disk.qcow2 local-lvm

# Remove unused disk reference
qm set <VMID> --delete unused0

# Attach as IDE (legacy OS without VirtIO drivers)
qm set <VMID> --ide0 local-lvm:vm-<VMID>-disk-0

# Or SCSI (for OS with SCSI drivers)
qm set <VMID> --scsihw lsi --scsi0 local-lvm:vm-<VMID>-disk-0
```

## VMware VMDK → PVE Conversion

### The Controller Problem

VMware VMs use BusLogic SCSI controller by default for Win2K guests. **PVE does NOT support BusLogic.** This causes `INACCESSIBLE_BOOT_DEVICE` (0x0000007B) BSOD on boot.

**PVE-supported SCSI controllers:**
| Controller | Win2K Support | Notes |
|------------|--------------|-------|
| `lsi` (LSI Logic) | ⚠️ Partial | May detect disk but BSOD due to missing driver |
| `lsi53c810` | ⚠️ | Even less likely to work |
| `megasas` | ❌ | Too new |
| `pvscsi` | ❌ | VMware paravirtual, needs VMware Tools |
| IDE (no SCSI) | ⚠️ Partial | Boot signature mismatch |

**Best approach for migrated VMware VMs:** Don't convert the VMDK. Instead, do a **fresh install from ISO** using the correct controller for the guest OS. This is the user's stated preference — converted VMDKs from VMware almost always have controller driver mismatches (BusLogic → LSI) that cause INACCESSIBLE_BOOT_DEVICE BSOD, and fixing them via Recovery Console is more work than a clean install.

**⚠️ PITFALL: Registry edits won't fix the SCSI→IDE mismatch.** Even if you mount the disk offline and:
1. Set `vmscsi` Start=4, `BusLogic` Start=4 (disabled)
2. Confirm `atapi` Start=0, `IntelIde` Start=0 (enabled)
3. Verify boot.ini uses `multi(0)disk(0)rdisk(0)partition(1)` (IDE path)

...the BSOD still occurs. The boot I/O path is set at the kernel/HAL level during Windows installation and cannot be changed by just flipping driver Start values. The ntoskrnl.exe initialization fails to mount the boot volume because the I/O path expects the original SCSI controller. Safe Mode also fails (same BSOD). **There is no registry-level fix — only a fresh install works.**

**⚠️ PITFALL: Phantom SCSI services.** VMware VMs often have `symc810` and `symc8xx` services in the registry with Start=0 (enabled) but NO corresponding `.sys` driver files on disk. When Windows tries to load these during boot, it cascades into additional failures. Always check `WINNT\system32\Drivers\` for the actual `.sys` files before assuming drivers are present.

### VMDK → qcow2 Conversion

```bash
# Convert on PVE host
qemu-img convert -f vmdk -O qcow2 /path/to/disk.vmdk /path/to/output.qcow2

# Check result
qemu-img info /path/to/output.qcow2
```

## Handling No KVM (TCG Emulation)

Check if KVM is available:

```bash
cat /proc/cpuinfo | grep -E 'vmx|svm' | head -3
systemd-detect-virt
```

If no VMX/SVM flags:

```bash
# Disable KVM in VM config
qm set <VMID> --kvm 0

# Use qemu64 CPU (host CPU model requires KVM)
qm set <VMID> --cpu qemu64

# ⚠️ TCG emulation is VERY slow — Win2K boot takes 5-10+ minutes
# CPU will peg at 95-100% during TCG emulation
```

## Downloading ISOs from Behind GFW

### Site Reachability

| Source | Accessible? | Notes |
|--------|:----------:|-------|
| archive.org | ❌ DNS毒化+TLS阻断 | 完全不可达，Clash也无法绕 |
| **winworldpc.com** | ✅ CDN可达 | 主站需代理，但CDN(dl-alt1.winworldpc.com)可直连。下载仅30-50KB/s（美/加服务器），358MB需~2.5h |
| mega.nz | ❌ TLS阻断 | SSL connection terminated |
| github.com | ⚠️ 有时慢 | 时好时坏，Clash加速后可下载 |
| **cldisk.com** | ✅ | 国内网盘，用户曾用于分享400MB文件 |
| **Baidu Netdisk** | ✅ | 最常见国内分享方式 |
| 123云盘 / 阿里云盘 | ✅ | 可让用户先传再给直链 |
| TUNA / USTC 镜像站 | ✅ | 国内教育网镜像，优先搜索 |

## IOMMU/VFIO 配置（PCI 直通准备）

当用户需要直通设备（NVMe、SATA控制器、GPU）给VM时，需要在PVE宿主机启用IOMMU并加载VFIO模块。

### 前置条件：BIOS中开启VT-d

不同BIOS中VT-d的名称可能不同：
- **Intel VT-d** / **Intel VT for Directed I/O** / **IOMMU** / **PCIe Passthrough**

**⚠️ 注意区分：VMX/VT-x ≠ VT-d。** VMX是跑虚拟机用的（一直开着），VT-d是设备直通用的。用户可能把VMX当成VT-d开了——实际上VMX早就开了（虚拟机一直在跑就说明这个没问题）。

### 步骤1：验证BIOS已开启VT-d

```bash
sshpass -p 'PASS' ssh root@PVE_HOST "
echo '=== DMAR table (VT-d硬件存在) ==='
dmesg | grep -i 'DMAR' | head -5
echo '=== IOMMU分组 (设备隔离) ==='
for d in /sys/kernel/iommu_groups/*/devices/*; do
  n=\$(basename \$(dirname \$(dirname \$d)))
  echo \"Group \$n: \$(lspci -nns \$(basename \$d))\"
done 2>/dev/null | sort -t: -k1 -n
"
```

- 有DMAR表 + 设备分到IOMMU组 → BIOS已开VT-d ✅
- 无DMAR表 → 回BIOS开VT-d
- 有DMAR表但`/dev/iommu`不存在 → 内核参数没加（下一步修复）

### 步骤2：GRUB加内核参数

```bash
sshpass -p 'PASS' ssh root@PVE_HOST "
# 备份
cp /etc/default/grub /etc/default/grub.bak.\$(date +%Y%m%d)

# 添加IOMMU参数（追加到quiet后面）
sed -i 's/quiet/quiet intel_iommu=on iommu=on/' /etc/default/grub

# 更新grub
update-grub

# 验证
grep GRUB_CMDLINE_LINUX_DEFAULT /etc/default/grub
# 应显示: GRUB_CMDLINE_LINUX_DEFAULT=\"quiet intel_iommu=on iommu=on intel_idle.max_cstate=1\"
"
```

### 步骤3：加载VFIO模块并持久化

```bash
sshpass -p 'PASS' ssh root@PVE_HOST "
# 加载模块
modprobe vfio
modprobe vfio_iommu_type1
modprobe vfio_pci

# 持久化（开机自动加载）
cat > /etc/modules-load.d/vfio.conf << 'EOF'
vfio
vfio_iommu_type1
vfio_pci
EOF

# 验证
lsmod | grep vfio
# 应显示: vfio, vfio_iommu_type1, vfio_pci, vfio_pci_core, iommufd, irqbypass
"
```

**⚠️ PITFALL：`vfio_virqfd` 在 kernel 6.17+ 已合并到 `vfio_pci_core`！** 不要加载 `modprobe vfio_virqfd`，会报 `FATAL: Module vfio_virqfd not found`。`/etc/modules-load.d/vfio.conf` 中也不需要这行。

### 步骤4：重启PVE生效

```bash
# 重启宿主机
sshpass -p 'PASS' ssh root@PVE_HOST "reboot"

# 重启后验证IOMMU启用
sshpass -p 'PASS' ssh root@PVE_HOST "
echo '=== 内核参数 ==='
cat /proc/cmdline | tr ' ' '\n' | grep iommu
echo '=== VFIO模块 ==='
lsmod | grep vfio
echo '=== IOMMU分组 ==='
ls /sys/kernel/iommu_groups/ | wc -l
"
```

### 步骤5：直通设备给VM

```bash
# 查看要直通设备的 PCI ID
lspci -nn | grep -i 'nvme\|sata\|ethernet'

# 示例：直通NVMe SSD给VM303
qm set 303 -hostpci0 0000:01:00.0,pcie=1

# 示例：直通SATA控制器（⚠️谨慎，会影响宿主机磁盘访问）
qm set 303 -hostpci0 0000:00:17.0,pcie=1
```

## ⚠️ PITFALL: VME ≠ VMX (VT-x 误判陷阱)

When you check if the CPU supports virtualization, do NOT rely solely on `vme` flag in `lscpu` or `/proc/cpuinfo` — it's NOT VT-x.

For game server verification (Minecraft etc.), see `references/minecraft-server-verification.md` — covers finder pattern via Java PID cwd, port check, "Done!" log marker, mod count, and Tailscale friend connectivity.

**⚠️ PITFALL: Container crashes the PVE host — check host logs, not just container logs**

When a container (especially MC server with large JVM heap) causes the entire PVE host to become unresponsive, **do NOT only check the container's logs**. The container's logs may only show normal startup or AllTheLeaks warnings — they won't show the host-level impact.

**Correct cross-level debugging workflow:**
1. Check container logs (MC `latest.log`, `debug.log`)
2. **Check PVE host journal** for memory pressure, service timeouts, proxy crashes
3. **Check `last reboot`** for crash history (look for "crash" status)
4. **Check archived journals** (`.journal~` files in `/var/log/journal/*/`) for pre-crash evidence
5. Compare container memory allocation vs JVM heap vs host RAM

See `references/container-causes-host-crash.md` for the full symptom cascade, post-mortem technique, and memory budgeting rules.

**⚠️ PITFALL: pct exec 挂起时先区分两种场景，不要盲目重启容器**

当 `pct exec` 命令超时时，有两种不同的故障模式，诊断和恢复方式不同：

**场景 A：完全阻塞（echo 也超时）** — 通常是 PVE 任务锁卡住
```bash
# 1. 检查锁文件
fuser /run/lock/lxc/pve-config-310.lock
# 有 PID → 任务卡住了

# 2. 恢复：杀掉卡死任务 + 清理锁文件
kill -9 <PID>
rm -f /run/lock/lxc/pve-config-310.lock

# 3. 验证
pct exec 310 -- echo OK
```

**场景 B：部分降级（echo 正常但 ss/ps/uptime 挂起）** — 容器内部状态异常，可能是 ONNX 模型加载或 I/O 阻塞
```bash
# 1. 确认是部分降级（echo 能返回，系统查询挂起）
pct exec 310 -- echo OK      # ✅ 返回
pct exec 310 -- ss -tlnp      # ❌ 挂起

# 2. 清理残留的阻塞进程
ps aux | grep 'pct exec.*310' | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null

# 3. 强制停止 + 重启容器
rm -f /run/lock/lxc/pve-config-310.lock  # 清锁（以防万一）
pct stop 310
sleep 2
pct start 310
sleep 3

# 4. 验证恢复
pct exec 310 -- ss -tlnp | grep 1810

# 5. 重启后 supervisord 不自动启动，需手动拉起
pct exec 310 -- nohup /usr/local/bin/supervisord -c /root/.openclaw/miloco/supervisord.conf > /dev/null 2>&1 &
sleep 15  # 等 ONNX 模型加载
pct exec 310 -- curl -s --max-time 3 http://127.0.0.1:1810/ | head -1  # 返回 HTML = 正常
```

**⚠️ 千万不要在锁卡住时执行 `pct stop`/`pct reboot`** — 这些操作也需要获取同一个锁，会继续挂起。必须先 `kill -9` + `rm -f` 释放锁。

**场景 C：容器内部 hang 但无 PVE 锁（2026-07-04 发现）** — 最简单的情况
`pct status` 正常返回 "running"，所有 `pct exec` 命令超时，但 `pct reboot` 能正常执行（因为 PVE 锁没被占用）。这是容器内部 init 或进程阻塞，不是 PVE 任务锁问题。

```bash
# 诊断：pct status 正常 + pct exec 全超时 + 无锁文件占用
pct status 310                     # → running ✅
pct exec 310 -- echo OK            # → 超时 ❌
fuser /run/lock/lxc/pve-config-310.lock  # → 无输出（无锁占用）

# 恢复：直接 pct reboot（不需要先杀锁）
pct reboot 310
# 等 15-20 秒
pct exec 310 -- echo OK            # → 恢复 ✅
```

**与场景 A 的区别：** 场景 A 有锁占用（`fuser` 有输出），必须先杀锁再 reboot。场景 C 无锁占用，直接 reboot 即可。

### 诊断技巧：`lxc-attach` 比 `pct exec` 更适合定位 hang 原因

当 `pct exec` 全部超时时，`pct exec` 本身的超时包装器会掩盖根因。改用 **`lxc-attach`** 可以获得更细粒度的诊断：

```bash
# pct exec 超时不代表容器完全不可用 — 试 lxc-attach
sshpass -p 'PASS' ssh root@PVE_HOST 'lxc-attach -n 310 -- echo hello'
# → "hello" ✅ = 容器 init 在运行，shell builtin 可用

sshpass -p 'PASS' ssh root@PVE_HOST 'lxc-attach -n 310 -- uptime'
# → 超时 ❌ = 外部二进制无法执行

sshpass -p 'PASS' ssh root@PVE_HOST 'lxc-attach -n 310 -- ls /usr/local/bin/'
# → 超时 ❌ = 根文件系统 I/O 阻塞
```

**诊断矩阵（`lxc-attach` 结果 → 故障类型）：**

| echo (builtin) | uptime / ls (binary) | miloco-cli | 诊断 |
|:-:|:-:|:-:|------|
| ✅ | ❌ | ❌ | **文件系统 I/O 挂死** — 根分区读写卡住，容器 init 还活着 |
| ✅ | ✅ | ❌ | **miloco-cli 或其依赖损坏/缺失** — 容器本身正常 |
| ❌ | ❌ | ❌ | **容器完全 hang**（场景 A/C）— 需要 reboot |

**为什么 `pct exec` 会全部超时但 `lxc-attach` 能部分工作：** `pct exec` 通过 PVE 的 task 系统执行，有自己的超时和锁机制；`lxc-attach` 是直接调用 LXC 的 `lxc_attach` API，不经过 PVE task 层。文件系统挂死时，`pct exec` 的 task 超时先触发，掩盖了 shell builtin 其实能工作的事实。

**场景 D：文件系统 I/O 挂死（2026-07-14 发现）** — 最常见的 "部分 hang"
`pct status` → "running"，`pct exec` 全超时，但 `lxc-attach -- echo hello` 能返回。根因是容器根分区（ZFS/overlay）I/O 阻塞，常见于 ONNX 模型大量磁盘读写后 ZFS 缓存压力。

```bash
# 诊断
lxc-attach -n 310 -- echo hello      # ✅ shell builtin
lxc-attach -n 310 -- uptime          # ❌ 外部二进制超时
lxc-attach -n 310 -- ls /usr/local/bin/  # ❌ 文件系统读取超时

# 恢复：直接 pct reboot（与场景 C 相同）
pct reboot 310
# 等 15-20 秒
pct exec 310 -- echo OK              # → 恢复 ✅
```

**⚠️ 不要在文件系统挂死时尝试 `pct stop`** — `stop` 需要向容器发送 SIGTERM，如果容器的 I/O 队列已满，信号无法投递，`pct stop` 也会超时。`pct reboot` 走的是 LXC 的强制重启路径，不依赖容器内部响应。

**⚠️ 健康检查不要用 `ss`，用 `curl`** — `ss` 读取 `/proc/net/tcp`，在部分降级时会挂起。`curl` 走网络栈，端口未监听时立即返回连接拒绝。详见 `references/miloco-perception-script-pitfalls.md`。

**⚠️ PITFALL: JVM heap size vs container memory — host crash cascade**

When a container's JVM heap is too close to the container's memory limit, the combined heap + non-heap + OS overhead can exceed the container allocation, causing PVE host-wide memory pressure. This crashes ALL services on the host (pveproxy, pvestatd, firewall), not just the MC server.

**Memory budgeting rule:** Container RAM ≥ JVM heap × 1.6 (leave 60% of heap size for OS, non-heap, and buffers).

| Container RAM | Safe JVM Heap | Risk |
|---|---|---|
| 10GB | 5G (`-Xmx5G -Xms5G`) | ✅ Safe — 5GB for JVM, 5GB for OS |
| 10GB | 8G (`-Xmx8G -Xms8G`) | ❌ CRASH — only 2GB left for OS |
| 8GB | 5G | ✅ Safe |
| 8GB | 6G | ⚠️ Marginal |

**Diagnostic tool: AllTheLeaks mod** — If the MC server has the AllTheLeaks mod installed, it reports memory leak data every 10 minutes:
```
[AllTheLeaks/]: B: 1107MB / C: 2760MB / Diff: +1653MB
```
- **B** = baseline (initial heap after startup)
- **C** = current used
- **Diff** = leaked above baseline
- If Diff keeps growing steadily (10MB/10min) → memory leak present
- If Diff is stable → normal behavior

**Symptom cascade when container starves host:**
1. `systemd-journald: Under memory pressure, flushing caches` (kernel reclaiming)
2. `pvestatd: got timeout` / `loop take too long` (PVE daemons blocked)
3. `pve-firewall: update time (168 seconds)` (firewall rules timeout)
4. `pveproxy: Can't call method on undefined value` (web UI crashes)
5. SSH connections timeout → host appears "dead"

**Post-mortem: Check archived journals** — After reboot, the pre-crash logs are in `/var/log/journal/*/system@*.journal~` files. Use `journalctl --file=` to read them.

**⚠️ PITFALL: MC service with screen wrapper — systemctl doesn't control the actual server**

Many MC servers in LXC use `mc.service` → `mc-monitor.sh` → `screen -dmS mc ./run.sh`. This means:
- `systemctl stop mc.service` does NOT stop the MC server (only the wrapper script)
- The Java/screen process keeps running after systemctl stop
- To actually stop: send `stop` via screen (`screen -S mc -X stuff 'stop\n'`), then disable the service
- To start: `systemctl start mc.service` launches the wrapper which starts screen+Java

当你检查 CPU 是否支持虚拟化时，**不要仅凭 `lscpu` 或 `/proc/cpuinfo` 中的 `vme` 标志就断定 VT-x 开启**。

`vme` (Virtual Mode Extensions) 是从 80386 时代就有的老古董功能，**几乎所有 x86 CPU 都有这个标志**。而 `vmx` (Intel VT-x) 才是硬件虚拟化。

**两者在 lscpu 输出中看起来非常像：**
```
Flags:               fpu vme de pse tsc msr pae mce cx8 apic sep mtrr
                       ↑ 这个不是VT-x！！！
```

**正确验证步骤：**

```bash
# 1. 明确检查 VMX 标志（不是 VME）
lscpu | grep -i virtualization
# 期望输出: "Virtualization:                  VT-x"
# 如果为空或不显示 → VT-x 未开

# 2. 检查 /proc/cpuinfo 中是否有 vmx（不是 vme）
grep -o 'vmx' /proc/cpuinfo | head -3
# 有输出 → VT-x 可用；无输出 → 未开启

# 3. 最关键：检查 dmesg 的 BIOS 层面消息
dmesg | grep -iE 'vmx|kvm'
# 如果看到 "VMX (outside TXT) disabled by BIOS" → BIOS 层面禁用了
# 即使 CPU 支持，BIOS 也可能没开或热重启没生效

# 4. 彻底检查
grep --color=always -E 'v.mx' /proc/cpuinfo | head -1
# 高亮显示 vmx（绿色）vs vme（普通），一目了然
```

**已知问题：**
- 有些主板（特别是 ITX 板子如 D4L）热重启（reboot）不使能 VT-x，必须**完全关机拔电源等 30 秒再开机**
- `vme` 和 `vmx` 在 `/proc/cpuinfo` flags 列表中相邻出现，扫一眼极容易看串
- 即使 BIOS 界面显示 "Enabled"，冷启动才真正生效

### 从中国下载 ISO 的策略

核心原则：
1. **优先问用户**有没有国内网盘链接或校内源
2. **始终测试直连和代理**——有些CDN直连更快（如winworldpc的dl-alt1），有些必须走代理（如Google）
3. **winworldpc.com** CDN可用但慢——用 `background` 模式后台挂载，通知用户预计耗时
4. **不要在无法下载的站点上反复重试**（如 archive.org 被墙后无论直连+代理都不可达），浪费 token
5. **用Bright Data搜索替代源**——被墙站点的ISO可以通过`search_engine`找到iboysoft.com等索引页，再判断直链是否可达
   ```bash
   # 示例：搜索Win2K ISO，寻找索引页
   # 使用search_engine找到iboysoft.com等聚合页
   # 聚合页上通常直接给出archive.org等下载链接
   # →判断链接可达性后决定下载策略
   ```

### 通过 BrightData 找链接

对于被墙站点（如 archive.org），Bright Data 的 `search_engine` 可以用 Google 搜索链接：
```bash
# 搜索 ISO 下载链接（通过 BrightData）
会返回 iboysoft.com 等索引页→再从索引页拿直链
```

找到直链后，判断可达性再下载——下载不了就找用户帮忙。

## Win2K 无人值守安装（无控制台场景）

当用户只能通过微信聊天交互（没有 PVE Web UI 或 VNC 控制台）时，用 **winnt.sif 虚拟软盘** 实现全自动安装。

详细步骤见：
- `references/win2k-unattended-install.md` — 原理、winnt.sif 配置、产品密钥表
- `scripts/build_win2k_floppy.py` — Python 脚本一键生成 FAT12 软盘镜像

用法示例：
```bash
# 生成 Hacker 和 Server 的软盘镜像
python3 scripts/build_win2k_floppy.py HACKER-W2K 192.0.2.10
python3 scripts/build_win2k_floppy.py SERVER-W2K 192.0.2.10

# 上传到 PVE
sshpass -p 'PASS' scp win2k-hacker-w2k-floppy.img root@PVE_IP:/root/

# 在 VM 配置中附加软盘（PVE 的 qm set 不支持 --fdc，需手动编辑 conf）
echo "args: -drive if=floppy,file=/root/floppy.img,index=0,format=raw" >> /etc/pve/qemu-server/<VMID>.conf

# 启动 — Win2K 会自动读取 winnt.sif 进行全自动安装
qm start <VMID>
```

## TCG 仿真时间预估（无 KVM 时）

BIOS 中关闭 VT-x 时只能用 TCG 软件模拟，安装速度极慢。告知用户以便设定期望：

| 阶段 | TCG 预估时间 | 备注 |
|------|-------------|------|
| 文本模式安装 | 5-10 min | 分区、格式化、开始复制文件 |
| 文件复制 | 15-25 min | CPU 95-100% |
| 首次重启 | 3-5 min | 进入 GUI 模式 |
| GUI 安装 | 10-15 min | 应答文件处理、网络设置 |
| **总计** | **~30-60 min** | 取决于宿主机 CPU |
| KVM 对比 | ~5-8 min | 硬件加速时 |

## 教育实验室部署（从课程 PDF 分析→VM 部署）

见 `references/edu-lab-course-analysis.md`。核心流程：
1. 用 `ocr-and-documents` (pypdf2) 提取课程 PDF 文字
2. 识别网络拓扑（子网、角色、IP）
3. 确定 OS 需求（不要默认选 Server 版——检查工具兼容性，Pro 通常够用）
4. 映射到 PVE 网络等价物
5. 创建 VM + 部署工具

已知坑：教育实验室常用 VMware VMNet1（仅主机），在 PVE 中用纯桥接（无物理端口）加手动 IP 实现；Win2K 老系统需要 pc-i440fx + qemu64 + TCG 或 IDE/LSI SCSI。

## Linux 桌面版推荐（轻量办公场景）

当用户问"Linux哪个版本好"、"图形界面好"、"能办公/微信/Office/VSCode"时，见 `references/linux-desktop-recommendation.md`。

包含：Deepin 23.1 vs 25对比、N5095流畅度、PVE虚拟机配置建议。

- **Never run `systemctl restart hermes-gateway` from within the gateway** — see hermes-agent skill's troubleshooting section
- **SSH keys are better than sshpass** — set up once: `ssh-copy-id root@PVE_IP`
- **Win2K needs IDE or LSI SCSI** — VirtIO not supported natively
- **TCG emulation is SLOW** — avoid for interactive use; only for automated experiments
- **Legacy Windows requires `pc-i440fx` machine type** — q35 doesn't boot Win2K
- **Always check storage space** before importing large disks: `pvesm status`
- **QEMU screendump via QMP** is the only way to "see" VM display without VNC — see `references/qemu-qmp-debug.md`

## XPenology (黑群晖) on PVE

Install Synology DSM as a PVE VM for casual NAS experience testing.

### Prerequisites Check (CRITICAL)

Before attempting installation, verify KVM is available on the PVE host:

```bash
sshpass -p 'PASS' ssh root@PVE_HOST "egrep -c '(vmx|svm)' /proc/cpuinfo; lsmod | grep kvm_intel; systemd-detect-virt"
```

- **If `egrep` returns 0** → PVE host is itself a VM without nested virtualization. QEMU VMs cannot start. You MUST enable nested VT-x on the parent hypervisor first, or abandon the VM approach.
- **Common scenario:** User's PVE at 192.0.2.10 is a VM on another machine. The CPU shows "Genuine Intel(R) 0000" (virtual CPU). `vmx` flag is absent. LXC containers work fine but KVM VMs fail with "KVM virtualisation configured, but not available."
- **Fix on parent hypervisor:** ESXi → VM settings → CPU → "Expose hardware assisted virtualization to guest"; Proxmox → args: `-cpu host`; VirtualBox → `VBoxManage modifyvm "VM" --nested-hw-virt on`

### One-Click Installation (When KVM Available)

RR project provides a PVE one-click script. If GitHub is slow from China, download the image on the Hermes agent server first, then SCP:

```bash
# 1. Download on hermes (has proxy/CDN access)
curl -fsSL -o /tmp/rr-26.4.0.img.zip \
  'https://github.com/RROrg/rr/releases/download/26.4.0/rr-26.4.0.img.zip'

# 2. SCP to PVE
sshpass -p 'PASS' scp /tmp/rr-26.4.0.img.zip root@PVE_HOST:/tmp/

# 3. Download the script on PVE
sshpass -p 'PASS' ssh root@PVE_HOST \
  "curl -fsSL https://github.com/RROrg/rr/raw/refs/heads/main/scripts/pve.sh -o /tmp/rr_pve.sh"

# 4. Run with local image (avoids PVE's slow GitHub access)
sshpass -p 'PASS' ssh root@PVE_HOST \
  "bash /tmp/rr_pve.sh --onboot 0 --storage local-lvm --bltype sata --img /tmp/rr-26.4.0.img.zip"
```

### VM Configuration (Post-Script or Manual)

The script creates a VM with optimal settings. Key config requirements:
- **CPU type:** `host` (mandatory — DSM checks CPU features)
- **BIOS:** OVMF/UEFI (mandatory for DSM 7.x)
- **Machine:** q35
- **Network:** virtio or e1000
- **SCSI:** virtio-scsi-single

### ⚠️ PITFALL: 磁盘镜像可能是ZIP而非可启动镜像

RR PVE脚本 `--img` 参数传入的 `.img.zip` 文件可能被**直接dd到磁盘**而不是解压后写入。结果磁盘开头是 `PK`（ZIP文件头），里面包含 `rr.img`（3.6GB），但磁盘只有984M装不下。

**诊断：**
```bash
hexdump -C /dev/pve/vm-<VMID>-disk-1 2>/dev/null | head -3
# 如果看到 "PK" 开头 + "rr.img" 文件名 → ZIP被直接dd了
```

**修复：**
```bash
# 1. 停止VM
qm stop <VMID>

# 2. 扩容磁盘到至少5GB（rr.img约3.6GB）
qm resize <VMID> sata0 5G  # 或 scsi0

# 3. 提取真正的rr.img
dd if=/dev/pve/vm-<VMID>-disk-1 of=/tmp/rr_raw.zip bs=1M count=1024
python3 -c "
import zipfile
with open('/tmp/rr_raw.zip','rb') as f:
    data=f.read()
idx=data.rfind(b'PK\x05\x06')  # ZIP EOCD
with open('/tmp/rr_trimmed.zip','wb') as out: out.write(data[:idx+22])
"
unzip /tmp/rr_trimmed.zip -d /tmp/rr_extracted/
ls -lh /tmp/rr_extracted/rr.img  # 应约3.6GB

# 4. 正确写入磁盘
dd if=/tmp/rr_extracted/rr.img of=/dev/pve/vm-<VMID>-disk-1 bs=4M status=progress

# 5. 验证启动扇区（应为 eb 63 90 = FAT boot sector，不是 PK）
hexdump -C /dev/pve/vm-<VMID>-disk-1 2>/dev/null | head -1

# 6. 确保boot order指向正确磁盘
qm set <VMID> --boot order=sata0
qm start <VMID>
```

### ⚠️ PITFALL: VM boot order为空导致UEFI菜单但无法启动

**场景：** VM能启动进入UEFI BIOS菜单（显示QEMU HARDDISK选项），但选择磁盘后没有反应/黑屏。

**根因：** `qm config` 输出中 `boot:` 字段为空（没有 `order=` 设置）。UEFI知道有磁盘但不知道该从哪个启动。

**诊断：**
```bash
qm config <VMID> | grep boot
# 如果只显示 "boot:" 没有 "order=" → boot order未设置
```

**修复：**
```bash
qm set <VMID> --boot order=sata0    # 或 scsi0,ide0 等
qm stop <VMID> && qm start <VMID>
```

**注意：** `qm set --boot` 可能不报错但实际没写入（尤其是容器处于mounted状态时）。验证：`qm config <VMID> | grep boot` 确认 `order=` 存在。

**验证启动：** Guest Agent启动后显示 `Buildroot` OS（RR引导系统），端口7681开放（ttyd Web终端）。

### Post-Boot Setup

RR系统用 `dialog` TUI（蓝色菜单界面），不是Web表单。通过SSH或端口7681的ttyd Web终端操作。

1. SSH进RR（`root/rr`）或打开 `http://<VM_IP>:7681/`，输入 `/opt/rr/menu.sh`
2. **Choose a model** → 选 **DS920+**（4盘位，兼容性好，社区支持多）或 SA6400
3. **选DSM版本** → **7.2.2**（最新稳定版）
4. 确认PAT下载URL和MD5（MD5全0 = 跳过校验，直接OK）
5. RR会自动下载PAT、编译引导、重启
6. 重启后DSM会自动安装（可能需要在RR菜单里手动触发安装）
7. 访问 `http://<VM_IP>:5000/` 完成DSM初始设置（设备名、管理员账户）
8. ⚠️ **设置更新为手动** — 永远不要自动更新DSM

**⚠️ DHCP问题**：如果PVE网桥没有DHCP服务器，VM可能拿不到IP。解决：`qm set <VMID> --ipconfig0 ip=192.0.2.X/24,gw=192.0.2.10` 配静态IP。但注意RR/DSM可能覆盖这个设置（用自己的DHCP客户端），实际IP以 `qm guest cmd <VMID> network-get-interfaces` 为准。

### Recommended Models (二手 NAS, Not VM)

If user wants to buy physical hardware instead — see `references/xpenology-pve-install.md` for detailed comparison table.
- **Avoid DS716** (¥600) — Atom C2538, stuck on DSM 7.1, too weak
- **Avoid DS916+** (¥700-800) — N3710, still stuck on DSM 7.1
- **Avoid DS223j** (¥1300 new) — ARM, 1GB RAM, no Docker, 70% experience
- **Best value:** DS918+/DS920+ (¥1000-1200 used) — Intel J3455/J4125, DSM 7.2, 4-bay, Docker, expandable RAM
- **If budget allows:** DS224+ (¥2000 new) — Intel J4125, 2GB expandable to 32GB, full DSM experience

## ⚠️ PITFALL: 新建 LXC 容器 DNS 解析失败（IPv6 幻象）

新建 Debian/Ubuntu LXC 容器时，通过 vmbr0 桥接的 DHCP 会拿到 **IPv6 DNS 服务器地址**（如 `fda2:d566:e0cd::1`），但 PVE 宿主机实际上可能**没有公网 IPv6**。结果：DNS 配了 IPv6 地址但无法连通，apt/pip 全部超时卡死。

**诊断：**
```bash
pct exec <VMID> -- cat /etc/resolv.conf
# 如果 nameserver 是 fe80:: 或 fda2: 开头 → IPv6 DNS 幻象
pct exec <VMID> -- ip -6 addr show | grep 'inet6' | grep -v 'fe80\|::1'
# 无输出 → 没有可用的 IPv6 全局地址 → DNS 必然不通
```

**修复（立即生效）：**
```bash
pct exec <VMID> -- bash -c 'echo nameserver 203.0.113.1 > /etc/resolv.conf && echo nameserver 203.0.113.1 >> /etc/resolv.conf'
```

**永久修复（容器内）：** 在 `/etc/network/interfaces` 中为 eth0 添加 `dns-nameservers 203.0.113.1 203.0.113.1`，避免 DHCP 重新覆盖。

**⚠️ 副作用：** DNS 通了不代表所有站点可达。容器走 iStoreOS 路由时，国际站点可能被防火墙拦截（ICMP Destination Port Unreachable），但 HTTP/HTTPS 通常正常。

## uv 包管理器在中国的安装问题

`uv`（Astral出品的Python包管理器）的官方安装脚本从 `releases.astral.sh` 下载二进制，在中国经常**极慢或卡死**。

**解决方案：用pip从清华源安装uv**

```bash
# 在LXC容器内
pip3 install --break-system-packages uv -i https://pypi.tuna.tsinghua.edu.cn/simple
uv --version  # 验证
```

安装后，如果项目的install.sh脚本仍在尝试下载uv（因为它检测PATH里没有uv），有两个绕过方式：
1. 把uv复制到脚本搜索的路径：`cp ~/.local/bin/uv /usr/local/bin/uv`
2. 直接用uv运行install.py：`cd /path/to/repo/scripts && uv run install.py`

**⚠️ PITFALL: uv二进制是动态链接的ELF，需要ld-linux调用**

如果 `uv --version` 报 `No such file or directory` 但文件确实存在，可能是动态链接器路径问题。用完整路径调用：
```bash
/lib64/ld-linux-x86-64.so.2 /usr/local/bin/uv --version
```
或者创建wrapper脚本。

## 国内 LXC 容器换源加速（apt + pip）

中国网络环境下，默认的 Debian 官方源和 PyPI 国际源下载速度极慢（<100KB/s）。**务必换国内镜像：**

```bash
# 换 apt 阿里云源
pct exec <VMID> -- bash -c 'cat > /etc/apt/sources.list << EOF
deb https://mirrors.aliyun.com/debian/ bookworm main contrib non-free non-free-firmware
deb https://mirrors.aliyun.com/debian/ bookworm-updates main contrib non-free non-free-firmware
deb https://mirrors.aliyun.com/debian-security bookworm-security main contrib non-free non-free-firmware
EOF
apt update'

# 换 pip 镜像源（安装时指定）
# 清华源通常比阿里云更快（实测对比）
pct exec <VMID> -- pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
# 阿里云源备选
pct exec <VMID> -- pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
```

**实测对比：** 默认源 ~50KB/s，阿里云源 ~29MB/s，清华源 ~30MB/s+。差距 600 倍。

### ⚠️ PITFALL: OpenClash 代理对 pip 返回 407

iStoreOS 的 OpenClash 透明代理对 pip 的 HTTPS 请求返回 `407 Proxy Authentication Required`。即使容器有 `https_proxy` 环境变量，pip 也无法通过 Clash 代理下载。**不要配代理给 pip，直接用国内镜像。**

### ⚠️ PITFALL: pip install 卡住时的手动安装模式

当 `pip install` 因依赖解析或下载卡住超过 30 秒时，杀掉进程，改用手动模式：

```bash
# 1. 杀掉卡住的 pip 进程
kill -9 $(pgrep -f 'pip.*install') 2>/dev/null

# 2. 如果有 .whl 文件已下载，用 --no-deps 先装主包
pip install --break-system-packages --no-deps /path/to/main_package.whl

# 3. 单独装依赖（用国内镜像，速度快）
pip install --break-system-packages -i https://pypi.tuna.tsinghua.edu.cn/simple \
  dep1 dep2 dep3 ...

# 4. 逐步补全缺失依赖（pip 会报 "requires X which is not installed"）
pip install --break-system-packages -i https://pypi.tuna.tsinghua.edu.cn/simple \
  missing_dep1 missing_dep2
```

**适用场景：** install.sh 脚本卡在 uv 下载、pip 依赖解析超时、网络不稳定的 LXC 容器。关键原则：**不要等，杀掉，手动跑每一步**。

## Deploying HTTP Services Inside LXC Containers

When you need to run a PHP/Python web service inside a PVE LXC container (e.g., IPTV proxy, API relay, Flask app), follow this pattern:

**⚡ User preference: DO EVERYTHING IN ONE SHOT.** Don't install, then ask for config, then ask for API key, then configure. Pre-configure everything you can (dependencies, mirrors, services, bind addresses) in the first pass, then only ask for credentials you genuinely don't have. The user gets frustrated by multi-round deployments ("你就不能把所有安装的东西都弄好").

**⚡ Two deployment-comms rules the user has stated outright:**

1. **Never substitute a component silently.** When a part can't be used as planned (wrong key format, unsupported quantization, incompatible architecture) and you put something else in its place, say so **in the same message** — what was planned, why it changed, what replaced it. Letting the user discover the substitution afterwards reads as deception and costs far more trust than the substitution itself. The same applies to any "good enough" stand-in: label it as a stand-in at the moment you choose it, never later.
2. **Deliver once, then hand off.** Finish the whole job, self-check it, give one complete report — and stop. Do not keep generating, re-testing, or polishing after handing over; the user wants to be the one to accept the work ("我测试就行你不用"). Verify, report, yield.
3. **When he says the result is still wrong, go find community success cases.** Stop re-deriving parameters from your own reasoning — pull tutorials, working configs, and forum-tested recipes instead (「你去社区找找成功案例吧」). Sourced recipes carry more weight with him than synthesized ones, and an external angle breaks the loop faster than another one of your own guesses.

### ⚠️ 铁律：建容器后第一件事 = 配代理环境

**不要等下载卡了才想起来配代理。** 创建 LXC 容器后，执行任何安装之前，先把代理环境写进容器：

```bash
# 1. 写入 /etc/environment（所有进程继承）
pct exec <VMID> -- bash -c '
cat >> /etc/environment << EOF
http_proxy=http://192.0.2.10:7890
https_proxy=http://192.0.2.10:7890
no_proxy=localhost,127.0.0.1,192.0.2.10/16,192.0.2.10/8
EOF
source /etc/environment
'

# 2. 配 apt 代理
pct exec <VMID> -- bash -c '
mkdir -p /etc/apt/apt.conf.d
cat > /etc/apt/apt.conf.d/99proxy << EOF
Acquire::http::Proxy "http://192.0.2.10:7890";
Acquire::https::Proxy "http://192.0.2.10:7890";
EOF
'

# 3. 验证代理通不通
pct exec <VMID> -- curl -s -o /dev/null -w "%{http_code}" --proxy http://192.0.2.10:7890 https://www.baidu.com
# 返回 200 = 代理可用
```

**如果代理返回 407（认证失败）**，改用国内镜像作为替代方案：
- apt: 阿里云镜像 `mirrors.aliyun.com`
- pip: 清华镜像 `pypi.tuna.tsinghua.edu.cn`（实测 0.4 秒/包，比代理更快）

**核心原则：** 咱家有代理就是为了用的。容器建好就该能科学上网，不是裸连外网等超时。

### Flask/Gunicorn Deployment Pattern

Full lifecycle for Python web apps (Flask, FastAPI, etc.):

```bash
# 1. Create container (example: VMID 300, Debian 12)
pct create 300 local:vztmpl/debian-12-standard_*.tar.zst \
  --hostname myapp --cores 2 --memory 512 --swap 256 \
  --rootfs local-lvm:4 --net0 name=eth0,bridge=vmbr0,ip=dhcp,ip6=dhcp,type=veth --onboot 1

# 2. Fix DNS (if needed) +换源 + install deps
pct exec 300 -- bash -c '
echo "nameserver 203.0.113.1" > /etc/resolv.conf
echo "nameserver 203.0.113.1" >> /etc/resolv.conf
cat > /etc/apt/sources.list << EOF
deb https://mirrors.aliyun.com/debian/ bookworm main contrib non-free non-free-firmware
deb https://mirrors.aliyun.com/debian/ bookworm-updates main contrib non-free non-free-firmware
EOF
apt update && apt install -y python3 python3-pip python3-venv git
'

# 3. Clone + venv + pip install
pct exec 300 -- bash -c '
mkdir -p /opt/myapp && cd /opt/myapp
git clone https://github.com/user/repo.git . && git checkout develop
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
'

# 4. Configure .env (generate SECRET_KEY)
pct exec 300 -- bash -c 'cd /opt/myapp && SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))") && cat > .env << EOF
SECRET_KEY=$SECRET
FLASK_DEBUG=false
EOF'

# 5. systemd service (from repo's deploy/ or create manually)
pct exec 300 -- bash -c '
cat > /etc/systemd/system/myapp.service << EOF
[Unit]
Description=My Flask App
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/myapp
Environment="PATH=/opt/myapp/.venv/bin"
ExecStart=/opt/myapp/.venv/bin/gunicorn -c gunicorn.conf.py app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload && systemctl enable --now myapp
'

# 6. Verify
pct exec 300 -- systemctl status myapp --no-pager | head -5
pct exec 300 -- ss -tlnp | grep gunicorn  # should show 0.0.0.0:PORT
```

**⚠️ PITFALL: gunicorn.conf.py bind address.** Default is `bind = "127.0.0.1:5000"` which only allows localhost access. For external access (reverse proxy, direct), change to `bind = "0.0.0.0:5001"` or `[::]:5001`.

**⚠️ PITFALL: Lucky reverse proxy has TWO separate steps.** Users often only configure DDNS and wonder why it doesn't work:
1. **动态域名 (DDNS)** — maps domain → public IP (A record for IPv4, AAAA for IPv6)
2. **Web服务 (Reverse Proxy)** — forwards incoming requests on that domain to the internal service (e.g., `192.0.2.10:5001`)

Both must be configured in Lucky. DDNS alone doesn't forward traffic.

**⚠️ PITFALL: 反代的前端/后端填反会形成自指循环。** 前端地址 = **匹配的域名**（不带 `http://`）；
后端地址 = **内网服务**（带协议头，如 `http://192.0.2.10:18080`）。填反后 Lucky 会去请求那个域名
→ 解析回自家公网 IP → 落到另一个服务，**返回 200 但页面是别人家的**。判据：
`curl -H "Host: <域名>" http://127.0.0.1:<端口>/ | grep 目标服务特征串`，没命中就是没转到目标。

**⚠️ PITFALL: 目标端口可能已被 DNAT 劫持，Lucky 反代从外部永远不可达。**
`nft list ruleset | grep "dport <PORT>"` 有 `dnat ... to` 就说明该端口被端口转发独占（prerouting 在路由决策前重定向，
连打到路由器本机的包也被送走）。**换一个高位端口**，不要去改那条 DNAT。

**⚠️ Lucky 的「防火墙自动放行」会自己写 nftables accept 规则** —— 动防火墙前先
`nft list ruleset | grep "tcp dport <PORT> accept"` 查一下，已有就不要重复加（守"不碰 OpenClash/nftables 自建表"）。

**⚠️ 家宽 80/443 入站普遍被运营商封。** 告诉用户访问地址必须**带端口**（"域名打不开"先查他有没有带端口）；
HTTPS 证书只能走 **DNS-01 验证**（TXT 记录，不碰 80/443），需要 DNS 服务商 API 密钥。

完整链路（真假公网 IP 判定、DDNS 取值脚本与内网地址保护、自指循环诊断、链路验证测试页设计、Lucky HTTP API）见
`references/lucky-ddns-public-exposure.md`。

### Updating a Deployed App (git pull pattern)

When the user pushes code to GitHub and wants the container updated:

```bash
pct exec <VMID> -- bash -c '
cd /opt/myapp && git pull
source .venv/bin/activate
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
systemctl restart myapp
'
# Verify
pct exec <VMID> -- systemctl status myapp --no-pager | head -5
```

Always check if requirements.txt changed — if not, skip the pip install to save time.

四步部署流程（装依赖 / `pct push` 传文件 / systemd service / 服务管理）与 `pct push`、`pct exec` 的坑见
`references/lxc-app-deployment.md`。部署时一并检查下面这几条（绑 127.0.0.1、PHP 单线程、容器代理变量）。

**⚠️ PITFALL: gunicorn/uvicorn/uvicorn 默认绑定 127.0.0.1。** Flask/Django/Miloco 部署时，服务默认只监听 localhost，容器内部能访问但外部完全不通。**部署时一次性把 host/port/所有依赖都配好，不要分多轮交互。** 部署后务必检查：
```bash
pct exec <VMID> -- ss -tlnp | grep gunicorn
# 如果显示 127.0.0.1 → 改为 0.0.0.0
pct exec <VMID> -- sed -i 's/bind = .*/bind = "0.0.0.0:5001"/' /opt/app/gunicorn.conf.py
pct exec <VMID> -- systemctl restart <service>
```

**⚠️ PITFALL: PHP built-in server is single-threaded.** It's fine for <10 concurrent requests but will bottleneck under heavy load. For production use, deploy behind nginx or use a multi-process PHP-FPM setup.

### Network Debugging in Proxied LXC Containers

CT <ID> (and other containers on the user's network) inherit Clash proxy environment variables from iStoreOS:

```
HTTPS_PROXY=http://Clash:***@192.0.2.10:7890
NO_PROXY=localhost,127.0.0.1,192.0.2.10/16,192.0.2.10/8,.local
```

**Symptoms:** `curl https://some-domain` routes through Clash proxy and may fail with SSL_ERROR_SYSCALL or timeout, even though the domain is reachable directly.

**Diagnosis:**
```bash
# Check if proxy is intercepting:
pct exec <VMID> -- env | grep -i proxy

# Test direct connection bypassing proxy:
pct exec <VMID> -- curl -s --noproxy '*' https://some-domain -o /dev/null -w "%{http_code}"

# Test through proxy explicitly:
pct exec <VMID> -- curl -s -x $HTTPS_PROXY https://some-domain -o /dev/null -w "%{http_code}"
```

**Common fix:** If a domain resolves to `198.18.x.x` (Clash fake-ip) and direct connection fails, the domain may be blocked or the proxy exit node can't reach it. Verify the domain is actually accessible by checking DNS from an external resolver (`dig +short domain @203.0.113.1`) — if Google DNS returns a real IP but curl gets 198.18.x.x, Clash TUN is intercepting DNS.

## Xiaomi Miloco 2.0 部署（智能家居 AI）

在 LXC 容器中部署小米 Miloco 2.0（全屋智能 AI 管理面板）。安装、**升级**步骤与已知坑见 `references/miloco-deployment.md`（升级走官方 install.sh 两阶段，装完必须手动起 supervisord）。

**关键要点：**
- install.sh **极慢必须绕过**——它从 astral.sh 下载 uv，在中国基本不通
- 用清华源 pip 安装 uv + 手动装 .whl + 清华源补依赖
- 默认绑定 127.0.0.1，必须改 config.json 的 `host` 为 `0.0.0.0` 才能外部访问
- config.json 在 `/root/.openclaw/miloco/config.json`，是 JSON 格式（不是 YAML）
- OpenClash 代理对 pip 返回 407，**不要用代理，直接用国内镜像**

### ⚠️ PITFALL: Miloco 后端 ONNX 模型内存占用巨大，1GB 容器不够

Miloco 感知引擎启动时加载多个 ONNX 模型（`det_4C.onnx`、`human_body_reid_v2.onnx`、`bge-small-zh-v1.5-int8.onnx`）在 CPU 上推理。这些模型 + Uvicorn 服务器 + 摄像头流处理，总内存占用远超 1GB。

**症状：** `supervisord.log` 中 miloco-backend 每隔 1-8 分钟被 SIGKILL（OOM kill），反复重启循环。`miloco-cli perceive logs` 命令超时（后端 API 不可用）。

**已知安全配置：** CT <ID> 内存至少 **2048MB** 才能稳定运行完整感知引擎。1024MB 会触发反复 OOM kill。

```bash
# 诊断（通过 PVE 宿主机）
sshpass -p 'PASS' ssh root@PVE_HOST "pct exec 310 -- tail -20 /root/.openclaw/miloco/log/supervisord.log"
# 看到连续 "terminated by SIGKILL; not expected" → OOM

# 修复
sshpass -p 'PASS' ssh root@PVE_HOST "pct set 310 --memory 2048"
sshpass -p 'PASS' ssh root@PVE_HOST "pct reboot 310"
```

### ⚠️ Webhook 接收器必须正确回复 Miloco 协议

Miloco 推送事件后会轮询 `get_trace` 查询 turn 执行结果。**如果 webhook 接收器不返回正确的 `{code:0, data:{runId, status:"ok"}}` 格式，Miloco 会每3秒疯狂重试 `get_trace`，日志被刷爆。**

正确实现要点：
1. `agent` action → 保存事件 + 返回 `{code:0, data:{runId: "hermes_xxx", status:"ok"}}`
2. `get_trace` action → 查询 runId 状态 + 返回同样格式
3. 两种 action 都必须返回 `code: 0`

### 设备控制→音箱 TTS 映射（按楼层）

摄像头在哪个楼层 → 用哪个楼层的音箱播报：
- 三楼书房监控 → 蓝色智能音箱 (979939218)
- 二楼主卧 → 橙色智能音箱 (979931026)
- 一楼客厅 → Xiaomi 智能音箱 Pro (981192128)

TTS 命令：`miloco-cli device action <DID> <action.X.X> 要说的话`
**⚠️ 直接传文本值，不带 `text-content:string=` 前缀！** 音箱会念出前缀。

**⚠️ 晚上10点后禁止音箱 TTS（家人睡觉）。**

**⚠️ 音箱麦克风不能用于语音输入。** Miloco 感知引擎只认摄像头麦克风，不认小爱音箱麦克风。

**已知 bug：Miloco 读开关状态而非灯实际状态（2026-06-26）。** 开关 on≠灯 on。规则引擎应检查 light 设备的 on 属性，非 switch 的 on@开关。

**规则自动化：** Miloco 内置规则引擎，可基于感知事件自动控制设备（如"有人→开灯"）。创建顺序：先 `task create` → 再 `rule create --task-id ... --condition ... --action ...`。完整语法和已部署规则见 `references/miloco-deployment.md`。

**音箱 TTS 按楼层路由（铁律）：** 不同型号音箱的 play-text action IID 不同。事件来自哪层楼就用哪层楼的音箱播报，否则用户听不到（用户常在三楼书房）。

当前音箱映射：
| 楼层 | 音箱名 | DID | action IID |
|------|--------|-----|------------|
| 三楼书房 | 蓝色智能音箱 | 979939218 | action.5.3 |
| 客厅 | Xiaomi 智能音箱 Pro | 981192128 | action.7.3 |
| 二楼主卧 | 橙色智能音箱 | 979931026 | action.7.3 |

⚠️ **新增音箱时必须先 `device spec <DID>` 确认 action IID**，不同型号不一样。

**TTS 命令引号格式（关键坑，已反复验证）：**
```bash
# ✅ 正确：整个 SSH 命令用单引号包裹，直接传文本值
sshpass -p '<PASSWORD>' ssh -o StrictHostKeyChecking=no root@192.0.2.10 \
  'pct exec 310 -- /usr/local/bin/miloco-cli device action 979939218 action.5.3 你好'

# ❌ 错误：text-content:string= 前缀会被音箱念出来
sshpass -p '...' ssh root@... "pct exec 310 -- ... action.5.3 text-content:string=你好"
```

**Python subprocess 中的写法（已验证可用）：**
```python
cmd = (
    f"sshpass -p '{SSH_PASS}' ssh -o StrictHostKeyChecking=no root@{PVE_HOST} "
    f"'pct exec {CTID} -- {MILoco_CLI} device action {did} {action} "
    f"{text}'"
)
# 关键：整个 pct exec 命令用单引号包裹，text 值直接拼接，不加前缀
```

**TTS 文本要求：** 只说有用信息，不加前缀/标签。用户明确要求纯净输出。
- ✅ "检测到你回来了"
- ❌ "text-content:string=检测到你回来了"
- ❌ "[通知] 检测到你回来了"

**⚠️ 晚上10点后禁止音箱 TTS（家人睡觉）。**

完整设备列表、Webhook 协议、架构说明见 `references/miloco-deployment.md`。

### Miloco Runtime Operations (Consolidated from miloco skill)

Runtime device control reference — TTS speaker commands, webhook receiver architecture, perception engine, and CLI command patterns. These are the operational details for a running Miloco instance (deployment covered above).

**Key references:**
- `references/miloco-tts-speaker-control.md` — Speaker action IIDs by model, TTS parameter format, floor-based routing, quiet hours
- `references/miloco-webhook-receiver.md` — Webhook receiver v5 architecture, Flask app on CT <ID>, event routing, deduplication, quiet hours
- `references/miloco-deployment.md` — Full deployment guide, config files, install pitfalls

**CLI command quick reference:**
```bash
# List devices
pct exec 310 -- miloco-cli device list
# Get device properties
pct exec 310 -- miloco-cli device props <DID>
# Check device spec (actions, properties, IIDs)
pct exec 310 -- miloco-cli device spec <DID>
# Control a property
pct exec 310 -- miloco-cli device control <DID> <spec_name> <value>
# Call an action (TTS, etc.)
pct exec 310 -- miloco-cli device action <DID> <action_iid> <params...>
# Perception: list perception-capable devices
pct exec 310 -- miloco-cli perceive devices
# Perception: view recent logs (⚠️ --jsonl required in scripts to avoid hanging!)
pct exec 310 -- miloco-cli perceive logs --jsonl --limit 20
# Perception: logs from a specific time range (debugging only, bypasses cursor)
pct exec 310 -- miloco-cli perceive logs --since 1h --limit 10
pct exec 310 -- miloco-cli perceive logs --since 24h --limit 5
# Time units: h (hours), m (minutes), s (seconds), d (days), combinations like 2h30m
```

**⚠️ PITFALL: `perceive logs` without `--jsonl` hangs or returns stale data.** Without `--jsonl`, the CLI uses SSE long-polling — it hangs when new events are being produced, but may "succeed" with stale data when the engine is down. For cron jobs, subprocess calls, or any automation, ALWAYS use `--jsonl --limit N`. See `references/miloco-perception-script-pitfalls.md` for details.

**⚠️ PITFALL: Monitoring scripts must handle backend-not-ready after restart.** When Miloco backend just restarted (OOM, manual restart, container reboot), `miloco-cli` returns `{"error": "cannot connect to Miloco backend"}` for a few seconds. Scripts should: (1) use `--jsonl` to avoid hang, (2) not suppress stderr with `2>/dev/null`, (3) add retry logic with delay. See `references/miloco-perception-script-pitfalls.md` for complete patterns and timeout recommendations.

**⚠️ PITFALL: `ensure_backend()` must NOT use `ss -tln | grep :1810` health check.** The `ss` command reads `/proc/net/tcp` which hangs in nested SSH + pct exec when the container is partially degraded. Use `miloco-cli service status` instead — it returns structured JSON (`{"running": true/false, ...}`) and is far more reliable. See `references/miloco-perception-script-pitfalls.md` → "ensure_backend() 最佳方案" for the recommended pattern.

## OpenClash API 诊断（延迟/流量/节点测试）

当用户报告"代理能用但很慢"时，通过 Clash REST API 诊断（⚠️ **mihomo alpha 内核可能对所有端点恒回 401**，secret 对也 401；恒 401 就别耗在认证上，诊断与**切组**一律改走配置文件 —— 见 `references/openclash-node-switching.md`）：

```bash
# iStoreOS SSH端口2222，API secret在config.yaml里
SECRET=$(grep "secret:" /etc/openclash/config/*.yaml | awk '{print $2}')
API="http://127.0.0.1:9090"

# 1. 查看当前选中节点
curl -s "$API/proxies/Proxy" -H "Authorization: Bearer $SECRET"

# 2. 查看各地区组的自动选择
curl -s "$API/proxies/Auto" -H "Authorization: Bearer $SECRET" | grep '"now"'

# 3. 节点延迟测试（URL encode中文组名）
curl -s "$API/group/Auto/delay?timeout=8000&url=http%3A%2F%2Fwww.gstatic.com%2Fgenerate_204" \
  -H "Authorization: Bearer $SECRET"
# 输出: {"Hong Kong":70,"Japan":80,"United States":70,...}

# 4. 流量统计（bytes/s）
curl -s "$API/traffic" -H "Authorization: Bearer $SECRET" --max-time 3

# 5. 活跃连接数
curl -s "$API/connections" -H "Authorization: Bearer $SECRET" | grep -o '"download"' | wc -l

# 6. 测试代理实际吞吐量
curl -x http://127.0.0.1:7890 -o /dev/null -w "Speed: %{speed_download} bytes/s\n" \
  --max-time 15 "http://speedtest.tele2.net/10MB.zip"
```

**诊断逻辑：**
- 延迟正常(70-100ms)但下载慢 → 节点限速/套餐流量用尽（检查`32.98 GB | 150 GB`这类显示）
- 延迟高(>300ms) → 节点拥挤，切换地区组
- 下载0 bytes/s + HTTP 407 → 代理需要认证（检查proxy username/password）
- 连接数异常高(>500) → 可能有设备在大量下载

**⚠️ PITFALL: 日志显示"using [Node]"不代表节点真的通！** Clash日志只记录流量匹配了哪个规则和代理组，不记录连接是否成功。要确认节点是否真正可用，**必须查Clash API的health check结果**，而不是看日志：

```bash
# 查各代理组的alive和delay状态
curl -s "$API/proxies" -H "Authorization: Bearer $SECRET" | \
  python3 -c "
import sys,json
d=json.load(sys.stdin)
for k,v in d.get('proxies',{}).items():
    if v.get('type') in ('Selector','Fallback'):
        alive=v.get('alive',True)
        delay=v.get('extra',{}).get('http://cp.cloudflare.com/generate_204',{}).get('history',[{}])[-1].get('delay',0)
        now=v.get('now','')
        print(f'{k}: alive={alive}, delay={delay}ms, now={now}')
"
# 关键指标：
# alive=false + delay=0 → 节点组完全不可用（所有子节点都挂了）
# alive=true + delay=0 → 节点组有可用节点但未测试
# alive=true + delay>0 → 节点组正常工作
```

**⚠️ PITFALL: 代理节点挂了会导致游戏/应用间歇性卡顿！** 当Clash的代理组fallback到DIRECT时，某些应用的外部认证请求（如Google OAuth、Riot Games认证）仍被匹配到代理规则→尝试走挂掉的节点→超时重连→间歇性卡顿。

症状：用户报告"打游戏延迟一阵一阵的"，日志显示流量在走代理但实际节点不通。

诊断流程：
1. 查Clash API `alive`状态 → 确认节点组是否全部 dead
2. 查日志中出问题的域名（如 `oauthaccountmanager.googleapis.com`）匹配了哪个代理组
3. 修复：在YAML配置中把该代理组的默认节点改为DIRECT

```bash
# 修复：把Google组默认改为DIRECT（紧急绕过）
sed -i 's/name: Google, type: select, proxies: \[SSRDOG,/name: Google, type: select, proxies: [DIRECT, SSRDOG,/g' /etc/openclash/config/<config>.yaml
/etc/init.d/openclash restart
```

**⚠️ PITFALL: BusyBox grep不支持 `-oP`！** iStoreOS的grep是精简版，没有Perl正则。用 `grep "pattern" | awk '{print $2}'` 替代。

## OpenClash 服务不起来 / 版本升级

`status` 和 LuCI 显示会互相骗人，按读数分三种：

| 读数 | 根因 | 处置 |
|------|------|------|
| `status=inactive` 但 `uci get openclash.config.enable=1` | `/etc/init.d/openclash` 没 `enable`，重启后进程压根没拉起来（LuCI 的"已开启"只反映 UCI 值，不反映进程） | `/etc/init.d/openclash enable && /etc/init.d/openclash start` |
| 日志 `OpenClash Now Disabled, Need Start From Luci Page, Exit...` | **插件升级把 `openclash.config.enable` 重置成 0** | `uci set openclash.config.enable='1'; uci commit openclash` 再 start |
| `curl -x 127.0.0.1:7890` 返回 `407` | `openclash.@authentication[0].enabled=1`，客户端没带账密 —— 应用侧表现就是"代理不好用" | 关认证（`enabled='0'`）或让客户端带账密 |

升级配方（备份三件套 → 走代理下载 → 先测新内核能跑再覆盖 → 装 ipk → 查开关 → 实测 204 → 回滚路径）见 `references/openclash-version-upgrade.md`。

- **`status` 是 running 不代表代理可用** —— 只认 `curl -x http://127.0.0.1:7890 .../generate_204` 返回 204。
- **装完 ipk 必须回头查 `enable`** —— 升级会重置开关，跳过这步就是"升完打不开"，而 LuCI 仍显示已开启。
- **插件版本**读 `/usr/lib/opkg/info/luci-app-openclash.control` 的 `Version`，**内核版本**读 `cat /etc/openclash/core/clash_meta_version` 或 `clash -v`；比对 GitHub release 时跳过 `prerelease`。

### ICMP正常 ≠ 游戏不卡（UDP丢包排查）

用户报告"ping正常但游戏丢包"时，关键区分：**LOL等游戏用UDP传输数据，ping用ICMP——两者走不同路径，ICMP正常不代表UDP正常。**

快速排查流程（按优先级）：

```bash
# 1. 查路由器UDP错误（最关键）
cat /proc/net/snmp | grep Udp
# 关注: InErrors, RcvbufErrors, SndbufErrors — 全0才正常
# NoPorts > 0 = 有UDP包到了但没匹配端口（可能是P2P/STUN探测）

# 2. 查conntrack中目标设备的UNREPLIED连接
cat /proc/net/nf_conntrack | grep "PC_IP.*UNREPLIED" | head -5
# UNREPLIED = 发了包没收到回复
# 关键：看哪些服务器IP是UNREPLIED，哪些是ASSURED

# 3. 从路由器traceroute到游戏服务器（看路径在哪断）
traceroute -n -m 15 -w 2 -U -p GAME_PORT GAME_SERVER_IP
# 如果到某跳之后全超时 → 路由问题（运营商或服务器端）

# 4. 从路由器tcpdump抓WAN口回包（最直接的证据）
tcpdump -i pppoe-wan -c 20 -nn "udp and host GAME_SERVER_IP" &
sleep 5; kill %1
# 如果只有OUTGOING包（src=WAN_IP）没有INCOMING包 → 服务器没回包

# 5. 查Windows端CPU（高CPU会导致应用层丢包）
sshpass -p 'PASS' ssh USER@PC_IP "cmd /c powershell -c (Get-Counter '\Processor(_Total)\% Processor Time').CounterSamples.CookedValue"
# >80% 说明CPU瓶颈

# 6. 查LOL crash handler数量（多=客户端不稳定）
sshpass -p 'PASS' ssh USER@PC_IP "cmd /c tasklist /FI \"IMAGENAME eq League*\""
# 多个LeagueCrashHandler64.exe = 客户端反复崩溃
```

**判断逻辑：**
- ICMP正常 + UDP丢包 + 路由器UDP零错误 → **服务器端问题**（腾讯负载高）
- ICMP正常 + UDP丢包 + 路由器NoPorts高 → **P2P/STUN探测被丢弃**（不影响游戏）
- ICMP正常 + UDP丢包 + conntrack UNREPLIED + tcpdump无回包 → **服务器不可达**（运营商路由断或服务器宕）
- ICMP正常 + UDP丢包 + conntrack UNREPLIED + tcpdump有回包但PC没收到 → **NAT/防火墙问题**（路由器没转发回包）
- ICMP正常 + UDP正常 + 游戏卡 → **应用层问题**（客户端bug、服务器逻辑）

**⚠️ Tailscale端口与游戏流量冲突（2026-07发现）**

**当游戏和Tailscale共用UDP端口（如41641）时，路由器iptables可能截获游戏回包。**

问题链：
1. 路由器上 `tailscaled` 监听 `0.0.0.0:41641`（所有接口，含WAN）
2. `ts-input` iptables链：`ACCEPT udp dpt:41641`（无条件接受所有41641端口UDP）
3. 游戏客户端也用源端口41641发包
4. 路由器NAT：`PC:41641 → WAN:41643`
5. 服务器回包到 `WAN:41643` → 正常conntrack反向NAT → 应该能到PC
6. 但如果服务器回包到 `WAN:41641` → 到达路由器INPUT → `ts-input`接受 → tailscaled吃掉 → PC收不到

**诊断：**
```bash
# 查tailscaled是否监听0.0.0.0:41641
netstat -ulnp | grep 41641

# 查ts-input规则命中数（高=大量流量被接受）
iptables -t filter -L ts-input -v -n | grep 41641

# 查游戏连接是否UNREPLIED
cat /proc/net/nf_conntrack | grep "src=PC_IP" | grep UNREPLIED | grep udp
```

**修复方案：**
1. 在游戏设置中改端口（如果支持）
2. 给游戏流量加iptables RETURN规则，在ts-input之前截获
3. 限制tailscaled只监听Tailscale接口而非0.0.0.0

**用户偏好：别分析太久，先查再报。** 游戏卡的时候用户等不了长分析。先跑上面的快速检查，30秒内给结论。

**用户偏好：Action-first排查，不是日志分析。** 当用户说"又卡了""又丢包了"，不要花时间分析日志含义——直接跑诊断命令，把结果摆在桌上。用户要的是"你帮我查了什么→结论是什么→怎么修"，不是"让我看看日志...嗯这个看起来..."。如果问题偶发，立刻开后台持续监控（ping -t记录到文件），别等下次复现再查。

**用户偏好：从变化的东西找问题，不要甩锅。** 用户明确要求"从自己身上找原因"。不要一上来就说"运营商QoS""服务器挂了""驱动太老"——先排查本地网络、路由器规则、NAT映射、conntrack状态。只有本地全排查完了才能考虑外部因素。特别是"之前打了几百把没问题，就今天有问题"——说明问题出在某个变化上，要问"今天变了什么"然后针对性排查。

**用户划出"不用查"的层就不要再探测它**（例：桥接光猫 = 它不参与转发，查它必无收获）。在被划掉的层上花调用既查不出东西，也读作没听指令 —— 把该层写进"已排除"结论，然后在用户认可的层内继续往下查。

## Network Download Speed Troubleshooting

When user reports download speed is much lower than expected (e.g., "软路由测速1700M but PC only downloads at 100M"):

### Step 0: 先用并发测出线路的真实带宽（在判断任何一层之前）

单线程下载量不出你的线路 —— 在多千兆的线路上，一条 TCP 流往往 200~400 Mbps 就到顶（窗口/BDP 限制 + 单服务器限速），跟链路健康与否无关。用错尺子会把好网络测成坏网络，然后把排查引向错误的层。

```bash
# 在路由器上跑（避开 PC 侧噪声）：8 条并发流，累加 speed_download（bytes/s）
seq 8 | xargs -P8 -I{} curl -s -o /dev/null -m 20 -x http://127.0.0.1:7890 \
  -w '%{speed_download}\n' https://mirrors.aliyun.com/ubuntu/ls-lR.gz | \
  awk '{s+=$1} END {printf "aggregate: %.0f Mbps\n", s*8/1000000}'
```

**判据：并发总量 ≈ 套餐速率 → 网卡、交换机、路由器 CPU、整形、DNS、代理全部一次性排除**，瓶颈只可能在"单连接"或"应用侧"；并发总量也低 → 才继续走下面的清单。

### Step 0b: 整形计数器不是证据，必须 A/B

`qdisc cake ... overlimits` 上千万看着就像限速，但 cake 对每次延后入队都计数，在忙碌链路上本来就是天文数字。关掉再测一次才能点名：

```bash
# 同一个测速，开/关各测一轮（LuCI SQM 页面或 /etc/init.d/sqm stop）
# 比值 ≈ 1.0 → 整形无辜
```

比值接近 1 就恢复原状什么都不改 —— A/B 证明不是问题的配置项，改动它只是制造下一个变量。

### Diagnostic Checklist (check in order)

1. **Link speed verification** — Confirm NIC negotiated at expected speed:
```powershell
# Windows PowerShell
Get-NetAdapter | Select-Object Name, Status, LinkSpeed
```
- If link speed is correct (e.g., 2.5 Gbps) → physical connection OK
- If link speed is wrong → check cable, switch port, NIC settings

2. **Driver age check** — Old drivers can cause performance issues:
```powershell
Get-NetAdapter -Name '以太网' | Select-Object DriverInformation
```
- Driver date > 3 years old → consider updating
- Realtek drivers from 2015 are known to have issues with 2.5G

3. **QoS/policy check** — No bandwidth limiting policies:
```powershell
Get-NetQosPolicy | Select-Object Name, Enabled, NetworkProfile
```
- Empty result = no QoS policies (good)

4. **Proxy check** — No system proxy intercepting traffic:
```powershell
reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyEnable
```
- ProxyEnable = 0x0 = no proxy (good)

5. **TCP statistics** — Check for errors/retransmissions:
```cmd
netstat -e
netstat -s | findstr /I "retransmit timeout"
```
- Errors = 0 = no packet loss
- High retransmits = network congestion

6. **Speed test comparison** — Test with speedtest CLI vs browser:
- If CLI speed is fine but browser/app is slow → application-level issue
- If both slow → network-level issue

7. **Router-side rate-limit rules (软路由 iptables/tc/QoS)** — When PC-side checks all pass but throughput is stuck at a round number (e.g. exactly ~10MB/s ≈ 100Mbps), check whether the soft router (iStoreOS) has bandwidth-limiting rules. The user may have asked you earlier to build monitoring/rate-limit rules for specific devices (e.g. IoT 设备监控), and those rules can accidentally match the PC:
```bash
# PVE host: check iptables (filter/mangle/nat) + tc qdisc for rate limits
iptables -L -v -n; iptables -t mangle -L -v -n; iptables -t nat -L -v -n; tc qdisc show
# iStoreOS router: check QoS config + nftables counters (devmon style)
ssh -p 2222 root@ROUTER "cat /etc/config/qos 2>/dev/null; cat /etc/config/tc 2>/dev/null; nft list ruleset | grep -iE 'limit|rate|police'"
```
- Round-number throughput (exactly 100M, exactly 10M) = software rate limit, not link issue
- Also check router CPU/processes — a compromised router running crypto-mining will throttle everything (see `references/router-malware-incident-response.md`)

### Step 8: 把带宽归属到设备，再归属到应用

在下"网络慢"的结论前，先知道字节是谁的：

```bash
# 谁在跟外网通信（按源 IP 数连接）
grep -o 'src=192.0.2.[0-9]*' /proc/net/nf_conntrack | sort | uniq -c | sort -rn | head
# 各物理口 5 秒流量增量（确认实际走的路径 + 有没有在收东西）
for i in eth1 eth2 eth3; do
  a=$(cat /sys/class/net/$i/statistics/rx_bytes); sleep 5
  b=$(cat /sys/class/net/$i/statistics/rx_bytes)
  awk -v a=$a -v b=$b -v n=$i 'BEGIN{printf "%s %.1f Mbps\n", n, (b-a)*8/5/1e6}'
done
```

然后读**应用自己报的数**：单源只肯收 ~100 Mbps 的应用，从网络侧修不好。

- Steam：`logs/content_log.txt` 里的 `Current download rate:` 和每 CDN 一行的 `stats: (CDN, N) host: bytes, sec (Mbps)`。两个 CDN × ~70 Mbps ≈ 实测总量，此时再调网络是白费。
- 若应用侧每源速率之和 = 实测速度，而并发测速顶满线路 → **停手，杠杆在应用内部**（服务器/区域选择，如 Steam 的 `设置 → 下载 → 下载区域`）。

**长得像"硬覆盖"的配置键往往不是。** 删掉 Steam 的 `CellIDServerOverride` 后 CellID 照样是同一个值 —— 客户端按 IP 地理位置重算出了相同结果。声称"钉子是元凶"之前，先重启后重读日志里的 `CellID` 行验证它真变了。

**"我没开代理"也可能是假的。** 加速器（网易UU 之类）在驱动层重定向，注册表 `ProxyEnable=0`、也看不到经典意义的代理进程。查进程列表里的加速器家族（`uu`、`uu_neths_helper`、TAP 虚拟网卡）并杀掉做对照：吞吐没动就说明它无辜，同时你拿到一个有证据的排除项。

### Common Causes

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Speed test OK, download slow | Game/server throttling | Check game settings, try different server |
| Speed test slow, everything slow | Network issue | Check link speed, cable, switch |
| Intermittent slow | Proxy/VPN interference | Check for running proxy software |
| Slow only on WiFi | WiFi congestion | Use Ethernet instead |

### Windows Network Adapter Settings

For Realtek 2.5G NICs, check advanced properties:
```powershell
Get-NetAdapterAdvancedProperty -Name '以太网' | Select-Object DisplayName, DisplayValue
```
Key settings:
- **Speed & Duplex**: Should be "Auto Negotiation" (not forced 100M)
- **Interrupt Moderation**: Enabled (good for throughput)
- **Receive Buffers**: 512+ (adequate)
- **Transmit Buffers**: 128+ (adequate)

**⚠️ PITFALL: Game launchers often throttle download speed.** Steam, Epic, Battle.net all have built-in speed limits. Check launcher settings before blaming network.

**⚠️ PITFALL: 先确认用户说的速度单位。** 用户说"100M"可能指100 Mbps（≈12.5 MB/s）也可能指100 MB/s。必须先确认具体数字再下结论。一次用户说"100M"实际是10 MB/s（≈80 Mbps），误判为100 Mbps导致排查方向错误。

**⚠️ 不能往物理层面上猜。** 当用户说"以前能跑到2000M，现在只能跑10M"且"物理层完全没动过"时，不要猜网线、交换机端口等物理问题。应该直接查软件层面：网卡驱动、QoS策略、iptables/tc限速规则、系统代理设置。物理层如果没变就不是物理层的问题。用户原话："主要就是不能往物理层面上猜，你知道吗？因为物理层面上完全都没有动过。"

**⚠️ 不要假设用户的网络拓扑。** 用户的网络环境可能几个月甚至几年没变过。如果你不确定某个配置是否一直是这样，先查历史记录（session_search）或直接问用户，不要自己假设。用户会因为你的错误假设而失去信任——特别是当你把一个一直存在的配置说成是"新问题"的时候。排查网络问题时，第一件事是确认"什么东西变了"，而不是"什么东西可能有问题"。

**⚠️ PITFALL: BusyBox grep不支持 `-oP`！** iStoreOS的grep是精简版，没有Perl正则。用 `grep "pattern" | awk '{print $2}'` 替代。

**⚠️ PITFALL: 桥接光猫 + OpenClash enable_redirect_dns=1 = 全家DNS瘫痪**

当光猫设为桥接模式时，光猫本身不提供DNS/DHCP服务，iStoreOS的dnsmasq是全网唯一的DNS服务器。如果OpenClash配置了 `enable_redirect_dns=1`，它会用iptables/nftables把所有53端口的DNS查询重定向到自己的DNS监听端口（通常是1053）。

**为什么桥接光猫下特别危险：** 没有兜底。OpenClash的DNS链一旦断了（上游不通、节点没连上、PPPoE重拨时序问题），全网DNS全挂。

**症状：** 换光猫后所有设备打不开网页，关掉OpenClash立刻恢复。或者PPPoE断线重连后DNS突然不好使。

**根因分析流程：**
```bash
# 1. 检查DNS劫持是否开启
ssh -p 2222 root@192.0.2.10 "uci get openclash.config.enable_redirect_dns"
# 返回 1 = 劫持中，危险

# 2. 检查当前模式
ssh -p 2222 root@192.0.2.10 "uci get openclash.config.en_mode"
# fake-ip + redirect_dns=1 = 最危险组合

# 3. 检查nftables是否有DNS重定向规则
ssh -p 2222 root@192.0.2.10 "nft list ruleset | grep -i '53\|dns\|redirect'"
```

**完整修复方案（三步）：**
```bash
ssh -p 2222 root@192.0.2.10 "
# Step 1: 关闭DNS劫持
uci set openclash.config.enable_redirect_dns='0'
uci set openclash.config.redirect_dns='0'

# Step 2: 改redir-host模式（不再用fake-ip）
uci set openclash.config.en_mode='redir-host'
uci set openclash.config.operation_mode='redir-host'
uci commit openclash

# Step 3: 修改YAML配置（fake-ip → redir-host）
sed -i 's/en_mode: fake-ip/en_mode: redir-host/' /etc/openclash/config/\$(uci get openclash.config.config_path | xargs basename)
sed -i 's/operation_mode: fake-ip/operation_mode: redir-host/' /etc/openclash/config/\$(uci get openclash.config.config_path | xargs basename)

# Step 4: 重启OpenClash
/etc/init.d/openclash restart
"
```

**验证修复：**
```bash
# DNS应该走ISP
ssh -p 2222 root@192.0.2.10 "nslookup baidu.com 127.0.0.1"
# 应返回真实IP（不是198.18.x.x）

# OpenClash应该在运行
ssh -p 2222 root@192.0.2.10 "/etc/init.d/openclash status"
# 应显示 running

# 代理应该能用
ssh -p 2222 root@192.0.2.10 "curl -x http://127.0.0.1:7890 -s -o /dev/null -w '%{http_code}' --max-time 8 https://www.google.com"
# 应返回 200
```

**⚠️ PITFALL: MATCH catch-all规则把游戏/Steam流量走代理（限速40M vs 直连1.3G）**

**⚠️ PITFALL: LOL/腾讯游戏疯狂掉线 = 游戏流量被代理劫持（2026-08 实测，完整步骤见 `references/openclash-game-direct-rules.md`）**

游戏（尤其 LOL/腾讯系）掉线重连十几次，但网页/视频正常时，查游戏设备流量是否走了 Clash 代理（conntrack 里 `src=192.0.2.10 sport=7892`）。订阅节点全在香港/日本时，游戏流量被 `MATCH` 兜底规则送去代理 → 延迟爆炸/掉线。**修复：在 rules: 顶部加游戏直连规则**（DOMAIN-SUFFIX qq.com/tencent.com/wegame.com + IP-CIDR 112.224.0.0/12 等腾讯段 DIRECT）。⚠️ **iStoreOS 路由器没有 python3，用 sed 插入**；规则必须放 MATCH 之前；改前备份、改后 `/etc/init.d/openclash restart`、用 ping 游戏服务器验证（应 0% 丢包 16ms 左右）。

OpenClash的规则末尾通常有 `MATCH,SSRDOG` 兜底规则，把所有未匹配的流量走代理。这导致：
- Steam国际下载服务器（不在SteamCN列表里）→ 走代理 → 速度只有代理带宽（40M）
- 其他不需要翻墙的服务也走代理 → 浪费代理流量配额

**⚠️ 订阅更新会改变MATCH行为！** 旧版订阅（ddrdog.yaml）兜底是 `MATCH,DIRECT`（全直连），新版订阅改成 `MATCH,SSRDOG`（全代理）。用户更新订阅后如果发现速度暴跌，先检查MATCH规则是否变了。这是最常见的"明明之前好好的突然变慢"原因。

**诊断：** 在电脑上开/关OpenClash，对比Steam下载速度。如果差10倍以上，说明流量被代理了。也可以直接检查当前配置的MATCH行：`grep MATCH /etc/openclash/config/*.yaml`

**修复：** 在YAML规则的 `MATCH` 行之前加直连规则：
```bash
ssh -p 2222 root@192.0.2.10 "
CONFIG=\$(uci get openclash.config.config_path)
sed -i '/MATCH/a\\    - '\''DOMAIN-SUFFIX,steampowered.com,DIRECT'\''\n    - '\''DOMAIN-SUFFIX,steamcontent.com,DIRECT'\''\n    - '\''DOMAIN-SUFFIX,steamgames.com,DIRECT'\''\n    - '\''DOMAIN-SUFFIX,steamstatic.com,DIRECT'\''\n    - '\''DOMAIN-KEYWORD,steam,DIRECT'\''' \$CONFIG
/etc/init.d/openclash restart
"
```

**原理：** Steam游戏下载走国际CDN（如Akamai），这些IP不在中国的GEOIP列表里，会落到MATCH规则走代理。加了直连规则后，Steam流量不再走代理，能跑满2000M宽带。

**⚠️ PITFALL: API组名含中文emoji需要URL encode。**

当代理服务商升级协议（如从SSR升级到Anytls）并更换订阅链接时，OpenClash可能有两个配置文件但只激活了旧的。

### 诊断：检查当前使用哪个配置

```bash
# 通过SSH检查UCI配置
sshpass -p 'PASS' ssh -p 2222 root@ROUTER_IP "cat /etc/config/openclash | grep config_path"
# 输出: option config_path '/etc/openclash/config/ddrdog.yaml'  ← 旧的

# 列出所有配置文件
sshpass -p 'PASS' ssh -p 2222 root@ROUTER_IP "ls -lt /etc/openclash/config/*.yaml"
# 新的文件通常更新时间更晚
```

### 切换到新配置

```bash
sshpass -p 'PASS' ssh -p 2222 root@ROUTER_IP "
uci set openclash.config.config_path='/etc/openclash/config/新配置文件.yaml'
uci commit openclash
/etc/init.d/openclash restart
"
```

### ⚠️ 协议升级注意事项

- 服务商升级协议（如Anytls）后，旧订阅的节点会失效
- 新订阅链接可能返回新协议格式的节点（type: anytls）
- Mihomo Meta内核通常支持新协议，但旧版可能不支持
- 切换后需要**重启OpenClash**才能生效
- **iStoreOS SSH端口是2222**（不是22，22被关了）

### 验证代理是否工作

```bash
# 从路由器测试
sshpass -p 'PASS' ssh -p 2222 root@ROUTER_IP "
curl -x http://127.0.0.1:7890 -s -o /dev/null -w 'HTTP %{http_code}\n' --max-time 8 https://www.google.com
"
# 返回200=代理通，返回000=代理不通

# 检查Clash日志看节点是否在用
sshpass -p 'PASS' ssh -p 2222 root@ROUTER_IP "tail -20 /tmp/openclash.log | grep -o 'using [^ ]*'"
```

## LXC 磁盘满恢复 + 在线扩容（pct resize）

**症状：** 容器内 `df -h` 100%，浏览器起不来（`BrowserType.launch: ENOSPC: no space left on device, mkdtemp '/tmp/playwright-artifacts-...'`），pip/apt 各种诡异失败，cron 任务静默失败、微信投递报 rate limited。

**排查顺序（先看真实分配，再清缓存，最后扩容）：**

```bash
# 1. 确认实际磁盘大小 —— 用户以为的容量 ≠ 实际分配的容量（2026-08 实测：CT <ID> 只有 20G 而用户以为 80G）
df -h /
sshpass -p 'PASS' ssh root@PVE_HOST "pct config 202 | grep rootfs"   # rootfs: local-lvm:vm-202-disk-0,size=20G ← 真相在这
sshpass -p 'PASS' ssh root@PVE_HOST "pvesm status; lvs | head -12"   # 看 local-lvm 剩余可用，确认能不能扩

# 2. 清缓存（安全项）
rm -rf /root/.cache/pip /root/.cache/uv ~/.hermes/cache/* /tmp/hermes-results/*
# 可安全删除的旧浏览器：/root/.cloakbrowser/chromium-* 保留最新一份即可
ls /root/.cloakbrowser/ | grep chromium   # 通常有 .3 和 .5 两份，删旧的

# 3. ⚠️ 别删 /root/.cache/ms-playwright！那是 playwright 本体，删了 cloakbrowser/playwright 起不来
#    如果不小心删了（报 Executable doesn't exist）：重新安装即可
python3 -m playwright install chromium-headless-shell && python3 -m playwright install chromium

# 4. 在线扩容 LXC rootfs（无需停容器，local-lvm 有空间就行）
sshpass -p 'PASS' ssh root@PVE_HOST "pct resize 202 rootfs 80G"
# 输出: Size of logical volume ... changed from 20.00 GiB to 80.00 GiB + resize2fs on-line resizing required
df -h /   # 立即生效
```

**要点：**
- `pct resize <VMID> rootfs <SIZE>` 对 lvmthin 是**在线扩容**（resize2fs 自动执行，容器不用重启）
- 扩容前先 `pvesm status` / `lvs` 确认存储池有空间；`pct config` 里的 `size=` 是唯一真实容量
- 浏览器起不来 ≠ 浏览器坏了，**先 `df -h` 看磁盘**
- 磁盘满会让 cron 任务静默失败、微信投递报 rate limited —— 先看 df 再看日志

## MC服务器 Core Dump 清理

MC服务器（特别是Forge/模组服）崩溃时会在根目录产生大量core dump文件，每个1.8MB，累积可达数十GB。

### 诊断

```bash
pct exec <VMID> -- bash -c '
echo "core文件数: $(find / -maxdepth 1 -name "core.*" 2>/dev/null | wc -l)"
echo "core占用: $(find / -maxdepth 1 -name "core.*" -exec du -ch {} + 2>/dev/null | tail -1)"
df -h /
'
# 典型情况: 30000+个core文件，占60GB+
```

### 清理

```bash
pct exec <VMID> -- find / -maxdepth 1 -name "core.*" -delete
# 一次性删除所有core文件，零风险
```

### 防止复发

MC服务器的core dump通常由Java OOM或mod冲突引起。建议：
1. 在启动脚本中设置 `ulimit -c 0` 禁止生成core dump
2. 或在 `/etc/security/limits.conf` 中设置 `* hard core 0`

## 下载大文件到PVE的策略

PVE服务器在中国网络环境下直接从GitHub下载大文件经常超时。**最佳模式：在hermes agent服务器上下载，然后SCP到PVE。**

```bash
# 1. 在hermes上下载（有代理/CDN加速）
curl -fsSL -o /tmp/large-file.zip 'https://github.com/.../large-file.zip'

# 2. SCP到PVE
sshpass -p 'PASS' scp /tmp/large-file.zip root@PVE_HOST:/tmp/
```

适用场景：XPenology引导镜像(981MB)、Windows ISO、VM磁盘镜像等。

## NAS Administration (UGREEN DXP4800 / Jellyfin)

For NAS-specific tasks (Jellyfin password reset, music library organization, Docker container inspection on NAS), see `references/nas-administration.md`. Key patterns:

- **UGREEN SSH**: Use `user` (not `root`) — root SSH disabled by default
- **Jellyfin**: 当前是 docker 容器，**先 `docker ps --filter name=jellyfin` 确认再选重启方式**（容器在 → `docker restart jellyfin`；确认没有容器才用裸进程 `kill JELLYFIN_PID`）。它只挂载 film/tv/Music 三个目录——**挂载外的路径 Jellyfin 一律看不见**。
- **MoviePilot 整理管线**：link 模式下源文件永远留在未整理（判断"没整理"必须用 inode/nlink）、多季剧无季标记会全落 Season 1 互相覆盖、整理≠刮削且刮削队列是快照、X-API-KEY 补刮削接口、**识别词是子串匹配会串台续作（transfer 前用 recognize_media 过一遍同剧所有兄弟目录）**、报「已整理过」要先备份再删 transferhistory 成功行（status 是 boolean）、MP 路径是容器命名空间拿错只返空不报错、`transfer_file` 无 episode 参数集号解析不出别盲传、审查拿 TMDB season_info 逐季对账且一次性出完整报告、搜索「过程有→最后空」按两阶段定位（站点原始返回 vs 标题/别名匹配过滤；日志 `/config/logs/moviepilot.log`；`get_search_results` 要带 `page` 才有 results；站点秒回几十条=泛结果不是命中） → `references/nas-administration.md`
- **多下载器转移做种（qB ⇄ Transmission 保种）**：站点 tracker 按 passkey+IP 判「同位置」，源刚删就转移必被拒（`You cannot seed the same torrent in the same location from more than 1 client`），而单个转移插件没有延迟能力 → 必须做 撤源 → 等 ≥1h → 再转移 的两段式 cron；三工具分工与**只能启用一个转移引擎**、IYUU 路径规则分隔符 `{#**#}`（WebUI 显示 `@split`）且 `torrent_path` 必填、QbCommand `pause_cron` 暂停的是全部任务、qB 5.x cookie 登录 / Tr RPC 在 `/transmission/rpc`、内网请求绕代理、**IYUU 容器停摆诊断与 `php /iyuu/webman iyuu:transfer <crontab_id>` 手动补跑、转移归因与标签（`cn_transfer` 定谁转的、IYUU `marker` vs MP `add_torrent_tags` 定谁打的标）、外来种子对已有数据补挂做种（paused→verify→start）** → `references/pt-seeding-transfer.md`
- **MP 登录 admin/<PASSWORD>（2026-10-02 验证，旧 admin/password 已失效）**；「账密进不去」按 哈希回验→本机真实登录→docker logs 看 401 来源IP 三步取证，先证明服务端没被改再谈重置 → `references/nas-administration.md`
- **Password reset**: PBKDF2-SHA512 hash — use `chr(36)` for `$` in Python f-strings
- **Music library**: Reorganize flat files → `Artist/Album/Track` using ffprobe metadata
- **传脚本进 NAS 别硬拼引号**：`scp` 到 `/tmp` 或 `~` 会 `Permission denied`（user 对这两处无写权限），复杂 heredoc 又会在多层引号里炸。可靠做法 = 本地写好脚本 → `base64 -w0` → ssh 管道写进**已存在的可写目录**（如 `/volume1/docker/_tmp`，由 docker 属主的目录先 `mkdir -p`）→ 远端 `sh` 执行完删掉：`echo B64 | base64 -d > DIR/x.sh && sh DIR/x.sh`。容器内改配置/跑脚本一律 `docker exec`（宿主上 user 对 root 属主文件无写权限），heredoc 进容器**必须 `docker exec -i`** 才读得到 stdin。
- **修故障优先「统一根因」，不要提议加监控**：the user 对「加个定时自检/告警」这类补丁方案直接否决（「你加定时自检这种方法太麻烦了，你得一劳永逸」）。范式固定为：先 `docker inspect` 找出所有共享同一物理卷的容器里**挂载点名不一致的那个**，改它统一到主流命名；再把每一层状态对齐到该名（客户端默认路径 → 每个种子的记录 → 转移工具的路径翻译规则）；最后只扫**真实配置**（conf / DB，不含日志与前端 JS 字面量）到残留为 0 才算收工。维持不一致再挂 cron 去比对，等于把活动部件永久留在系统里。

**⚠️ 绿联官方远程连接（UGREENlink）掉线排查（2026-08 实测）**：NAS 本地 ping/端口全通 + web.ugnas.com=200 + 但 App 连不上 → 是 P2P 打洞隧道失效（IPv6 前缀刷新/NAT 会话超时/客户端缓存），不是 NAS 或绿联服务器问题。修复=控制面板→远程访问→关闭再开启 UGREENlink（90% 恢复）。**域名陷阱：`link.ugreen.com` 解析到 SAP Emarsys 营销邮件域名，不是绿联远程服务，别拿它判断绿联挂了；测 `web.ugnas.com` 和 `ug.link`。WAN6 接口显示 pending 不代表 IPv6 坏了——用 `ip -6 neigh` 看 NAS 是否有 2408: 公网前缀 REACHABLE。** 完整排查顺序见 `references/ugreenlink-remote-access-troubleshooting.md`。

## N5095 Mini PC Setup

For N5095-specific issues (eDP phantom display, HDMI audio, DHCP problems), see `references/n5095-mini-pc.md`.

**⚠️ PITFALL: SSH to Windows PC — local IP may differ from Tailscale IP**

The user's Windows PC may have different IPs on LAN vs Tailscale:
- LAN: `192.0.2.10` (DHCP-assigned, may change)
- Tailscale: `100.64.0.1` (stable)

SSH credentials are the same for both: `<PASSWORD>@<IP>` with password `<PASSWORD>`. But:
- LAN SSH may not work if Windows Firewall blocks it on the LAN profile
- Tailscale SSH always works if Tailscale is running
- If LAN SSH fails with "Permission denied", try Tailscale IP instead

```bash
# LAN (may fail if firewall blocks)
sshpass -p '<PASSWORD>' ssh user@192.0.2.10 "echo OK"

# Tailscale (more reliable)
sshpass -p '<PASSWORD>' ssh user@100.64.0.1 "echo OK"
```

## Windows Remote SSH Patterns

For PowerShell variable escaping, Chinese filenames, wmic deprecation, and sudo limitations over SSH, see `references/windows-remote-ssh-patterns.md`. It also covers the patterns that actually decide whether a remote Windows job works at all: running multi-line PowerShell via `-EncodedCommand` (UTF-16LE + GBK output decoding), shipping long scripts local→scp→run with space-free destination paths, keeping a process alive after the SSH session closes (`schtasks` for jobs, a Startup-folder `.vbs` for services — `/RU /RP` is rejected), and confirming a restarted process is really running the new code (`*main.py*` match + `CreationDate` vs patch time).

## LXC Memory & Swap Adjustment

When a container gets OOM-killed (check with `journalctl -u <service> | grep oom-kill`) or user wants more headroom:

### Step 1: Audit Current Allocation

```bash
sshpass -p 'PASS' ssh root@PVE_HOST "
echo '=== Host ==='
free -h
echo '=== Containers ==='
for ctid in \$(pvesh get /nodes/\$(hostname)/lxc --output-format json | python3 -c 'import json,sys; [print(v[\"vmid\"]) for v in json.loads(sys.stdin.read())]'); do
  pct status \$ctid 2>/dev/null | grep -q running && \
  pct exec \$ctid -- free -h 2>/dev/null | awk -v id=\$ctid '/Mem:/{printf \"CT %-4s %s/%s used\n\", id, \$3, \$2}'
done
"
```

Present a table to user: name, used, limit, swap usage. Recommend increases based on actual usage vs limit.

### ⚠️ PITFALL: Supervisord-managed services — SIGKILL in supervisord.log = OOM kill

When a service is managed by **supervisord** (not systemd), the kernel OOM kill does NOT appear in `journalctl`. Instead, it manifests as `SIGKILL` exits in supervisord's own log:

```bash
# WRONG — won't find anything for supervisord-managed services:
pct exec <VMID> -- journalctl -u miloco-backend | grep oom-kill

# CORRECT — check supervisord's log:
pct exec <VMID> -- tail -50 /path/to/supervisord.log
# Look for: "WARN exited: <service> (terminated by SIGKILL; not expected)"
```

**Diagnosis pattern for repeated SIGKILL crashes:**
```bash
pct exec <VMID> -- grep 'SIGKILL' /path/to/supervisord.log | tail -20
# Count crashes: if 10+ SIGKILLs in 30 minutes → OOM
# Each crash cycle: start → run 1-8min → SIGKILL → restart
```

**Confirm OOM hypothesis:** Check container memory limit vs actual usage:
```bash
pct config <VMID> | grep memory    # limit
pct exec <VMID> -- free -m         # actual usage
```

**Fix:** Increase container memory via `pct set <VMID> --memory <NEW_MB>` (requires container restart).

### Step 2: Edit the Config

```bash
sshpass -p 'PASS' ssh root@PVE_HOST "
# Show current config
grep -E 'memory|swap' /etc/pve/lxc/<VMID>.conf

# Update values (memory in MB, swap in MB)
sed -i 's/^memory: <OLD>/memory: <NEW>/' /etc/pve/lxc/<VMID>.conf
sed -i 's/^swap: <OLD>/swap: <NEW>/' /etc/pve/lxc/<VMID>.conf

# Verify
grep -E 'memory|swap' /etc/pve/lxc/<VMID>.conf
"
```

**⚠️ Memory changes require a container reboot** — they don't apply live. Warn the user before rebooting if services are running inside.

### Step 3: Reboot the Container

```bash
sshpass -p 'PASS' ssh root@PVE_HOST "pct reboot <VMID>"
# Wait ~30s for LXC restart + services to come back up
```

### Common Allocations (for reference)

| Use Case | RAM | Swap | Notes |
|----------|-----|------|-------|
| Light (HA, mcp-server) | 2GB | 512MB | Enough for single-purpose containers |
| Hermes Agent (11 MCP servers) | 6GB | 2GB | MCP spawns many child processes |
| MC server (100-200 mods) | 8-10GB | 2-4GB | Java heap + OS + worldgen |

**⚠️ PITFALL**: Don't overcommit beyond host physical RAM. Check `free -h` on the host first. Total allocated can exceed physical (containers don't use all their max), but total **used** should stay under ~80% of host RAM.

## Checking VM Boot Progress (No-VNC Debug)

When user has no PVE web UI access, use QEMU QMP screendump to peek at VM display:

```bash
# From PVE host
echo '{"execute":"qmp_capabilities"}
{"execute":"screendump","arguments":{"filename":"/tmp/vm.ppm"}}' \
  | socat - UNIX-CONNECT:/var/run/qemu-server/<VMID>.qmp

# Copy and analyze
scp PVE_IP:/tmp/vm.ppm /tmp/
python3 -c "...analyze pixel colors..."  # See references/qemu-qmp-debug.md
```

Full guide: `references/qemu-qmp-debug.md`

## iStoreOS 网络设备监控

在iStoreOS路由器上部署设备流量监控（nftables计数器+Web面板+微信推送）。完全独立于fw4防火墙，不影响现有规则。

**⚠️ PITFALL: ping在线检测不可靠——拔设备后仍显示在线！** devmon.sh用 `ping -c 1 -W 1` 判定设备在线/offline，但设备物理断电后，**DHCP租约不会立即过期**（默认1小时+），ARP缓存也保持STALE/REACHABLE状态。ping会重新激活ARP条目，导致脚本误判已断电设备为 `"on":1`。**验证设备真正离线的方法：** 对比两次nftables计数器差值（`nft list counter inet devmon "c_XXX_up"`），如果 `bytes` 不变（`du=0, dd=0`）且速率 `su=0, sd=0`，即使ping能通，设备也已无实际通信。判断逻辑：**ping通 + 流量不变 = 设备可能已断电（DHCP/ARP缓存未清）**；**ping通 + 流量增长 = 设备真在线**。

**⚠️ PITFALL: BusyBox `date -v-1d` 不兼容！** devmon.sh中 `date -d "yesterday" +%Y-%m-%d 2>/dev/null || date -v-1d +%Y-%m-%d` 的macOS fallback在BusyBox上报 `date: unrecognized option: v`。BusyBox的 `-d` 语法是 `-d yesterday`（不支持 `-v-1d`）。修复：去掉 `-v-1d` 分支，或用 `date -d "@$(($(date +%s)-86400))" +%Y-%m-%d` 替代。

**⚠️ PITFALL: `monitor` 是nftables保留字！** 创建表时不能用 `monitor` 作为表名（报 `syntax error, unexpected monitor`）。用 `devmon`、`netmon` 等替代名。

**⚠️ PITFALL: `ensure_rules()` 必须先确保表存在！** 路由器重启后 nftables 表可能被清空，脚本的自动恢复逻辑不能只检查 chain，必须先 `nft list table inet devmon || nft add table inet devmon`。

**⚠️ PITFALL: DHCP 重新分配 IP 后监控失效！** 设备 IP 是 DHCP 动态分配的，重启路由器后可能变。**必须用 MAC 地址自动发现**（MAC 是硬件固定的），从 `/tmp/dhcp.leases` 按 MAC 查当前 IP。不要硬编码 IP。

**⚠️ PITFALL: BusyBox grep 不支持 `-oP`！** iStoreOS 的 grep 是 BusyBox 精简版，没有 Perl 正则。用 `grep "bytes" | awk '{print $2}'` 替代。

**⚠️ PITFALL: IoT 设备下载量天生为 0。** 摄像头/传感器主要往外推流，几乎不收数据。下载列长期为 0 是正常的，不是 bug。

**部署模式：**
1. 创建 `inet devmon` 表 + ingress/postrouting 链（priority -15）
2. 每设备两条计数规则（IP 匹配 + named counter）
3. 采集脚本按 MAC 自动发现 IP → 读计数器+ping → JSON → CGI端点
4. Hermes cron推送微信日报+异常告警

**清理：** `nft delete table inet devmon` 一键恢复。

完整步骤和所有 pitfall 见 `references/istoreos-network-monitoring.md`。

## iStoreOS 防火墙备份对比（配置变更排查）

当网络问题突然出现且怀疑防火墙被改时，iStoreOS会在 `/etc/config/` 下保留 `.bak` 备份文件。

### 查找备份文件

```bash
ssh -p 2222 root@ROUTER "ls -la /etc/config/firewall.bak*"
# 典型输出: firewall.bak.20260527_210720
```

### 对比差异

**⚠️ iStoreOS BusyBox 极度精简，以下工具不可用：** `diff`, `od`, `python3`, `grep -b`, `grep -oP`, `cat -v`, `head`(部分版本), `file`, `sshpass`。

可用的替代方案：
```bash
# 用awk逐行对比（替代diff）
ssh -p 2222 root@ROUTER 'awk "NR==FNR{a[NR]=\$0;next} \$0!=a[FNR]{print \"BAK:\"\$0; print \"NOW:\"a[FNR]}" /etc/config/firewall.bak.YYYYMMDD_HHMMSS /etc/config/firewall'

# 或者把文件拷到PVE宿主机上用diff
sshpass -p 'PASS' ssh root@PVE_HOST "scp -P 2222 root@ROUTER:/etc/config/firewall.bak.YYYYMMDD /tmp/fw_bak; scp -P 2222 root@ROUTER:/etc/config/firewall /tmp/fw_now; diff /tmp/fw_bak /tmp/fw_now"
```

### 已知关键差异模式

| 差异 | 影响 | 修复 |
|------|------|------|
| `wan.input` ACCEPT→REJECT | IPv6/入站流量被拒 | `uci set firewall.@zone[1].input='ACCEPT'; uci commit firewall; /etc/init.d/firewall reload` |
| `wan.forward` ACCEPT→REJECT | WAN→LAN转发被拒 | 同上改forward |
| 新增 port redirect 规则 | 端口映射变化 | 对比后按需恢复 |

**修复后必须 reload firewall：** `/etc/init.d/firewall reload`（不是 restart，reload不会中断现有连接）

**⚠️ 检测工具本身可能有问题！** fastnet等IPv6检测工具报HTTP 502时，是检测工具后端挂了，不是你的IPv6有问题。先用 `ping6 2400:3200::1`（阿里DNS）验证路由器IPv6，再用 `cat /proc/net/nf_conntrack | grep 'ipv6' | grep ESTABLISHED` 确认PC有活跃IPv6连接。有活跃连接=IPv6正常。

### iStoreOS BusyBox 工具限制速查

| 工具 | 状态 | 替代方案 |
|------|------|----------|
| `diff` | ❌ 不可用 | `awk` 逐行对比，或拷到PVE用diff |
| `od` | ❌ 不可用 | 拷文件到PVE分析 |
| `python3` | ❌ 不可用 | 用awk/shell脚本替代 |
| `base64` | ❌ 不可用 | 脚本在本机写好，`scp -P 2222` 传过去执行（复杂转义别硬拼） |
| `timeout` | ❌ 不可用 | 用 SSH 调用自带的超时（terminal `timeout=`），或 `nohup … > log 2>&1 &` 后轮询日志 |
| `ps aux` / `ps -a` | ❌ 不支持（BusyBox ps） | `ps w`（全格式单行） |
| `grep -b` / `grep -oP` | ❌ 不支持 | `grep "pattern" \| awk '{print $2}'` |
| `cat -v` | ❌ 不支持 | 拷到PVE用 |
| `file` | ❌ 不可用 | `hexdump` 或 `strings` |
| `sshpass` | ❌ 不可用 | 用SSH密钥 |
| `ss` | 部分版本不可用 | `netstat -ulnp` |
| `traceroute` | ✅ 可用 | — |
| `tcpdump` | ✅ 可用 | — |
| `nft` | ✅ 可用 | — |
| `iptables` | ✅ 可用 | — |

**核心原则：** 需要复杂分析时，把文件拷到PVE宿主机（`scp -P 2222`），用PVE的完整工具链处理。

## Homelab Networking & Proxy (Consolidated from homelab-proxy)

This section covers Clash/OpenClash transparent proxy, DNS/fake-IP debugging, GFW workarounds, Docker proxy, BrightData search setup, and network health checks. These are common concerns when running services behind GFW on a homelab with iStoreOS/Clash.

### Environment Quick Reference

| Component | Address | Notes |
|-----------|---------|-------|
| Router (iStoreOS) | 192.0.2.10 | J4125, OpenClash, SSRDOG |
| HTTP Proxy | 192.0.2.10:7890 | 代理认证已关闭（`openclash.@authentication[0].enabled=0`，连接无需账密）；要重新开启去 LuCI → 覆写设置 → 代理认证 |
| Router SSH | root@192.0.2.10 | Port 2222 |
| WiFi APs | .228, .171, .142/.117/.174/.169 | Ruijie EG210G-P-E + EAP602/EAP262E；DHCP 静态租约已绑名 `ruijie-ac-eg210g`(.228)、`ruijie-ap-{117,142,174,169}`，IP 不再漂 |

### Clash/OpenClash Core Concepts

- **Fake-IP mode:** OpenClash intercepts DNS and returns fake IPs (198.18.x.x) for all queries. This means `dig` always returns 198.18.x.x — use `dig +short domain @203.0.113.1` to get real IPs.
- **Transparent proxy:** All traffic from the LAN passes through Clash. Apps that don't respect system proxy (curl, pip, apt) still go through it via iptables/nftables TUN rules.
- **Connection inspection:** See `references/clash-api-connection-inspection.md` for how to check if a specific connection is going through proxy.
- **Config mismatch diagnosis:** See `references/openclash-config-mismatch-diagnosis.md`.

### Docker Proxy

**`docker pull` 慢/卡在 Retrying/EOF → 先查 dockerd 进程自己的 proxy 环境；配置文件存在 ≠ 生效。** 容器侧代理（`docker run -e`、daemon.json 的 `proxies` 段）只管容器运行时，**dockerd 拉镜像走不走代理由启动 dockerd 的那条命令的环境变量决定**，两处互不相通。按宿主的启动体系注入：

| 启动体系 | 注入点 | 判据 |
|---|---|---|
| systemd | `docker.service.d/*.conf` 的 `Environment=` | `systemctl cat docker` 看到 drop-in ≠ 生效，以 `/proc/<dockerd-pid>/environ` 为准 |
| **procd（OpenWrt / iStoreOS 路由器）** | `/etc/init.d/dockerd` 的 `start_service()` 里，`procd_open_instance` 之后加 `procd_set_param env HTTP_PROXY=… HTTPS_PROXY=… NO_PROXY=…` | 路由器上 systemd drop-in 是**死文件**（dockerd 由 procd 拉起，systemd 根本不读），改它毫无效果 |
| 无 init 系统（裸 LXC） | 启动包装脚本里 `export HTTP_PROXY=…` 再 `exec dockerd` | 见 `references/docker-hub-tls-failure-data.md` |

- `NO_PROXY` 必须带全内网段（`localhost,127.0.0.1,192.0.2.10/16,192.0.2.10/8,192.0.2.10/12`），否则容器与内网 API 调用也绕代理。
- **代理 URL 只允许一个 `http://`**：从既有配置抠出 `user:pass@host:port` 再拼 `http://${cred}@host`；把原串再包一层协议得到 `http://http://…`，dockerd 会静默忽略，症状依旧是拉取慢，极难看出是 URL 拼错。
- 验证只认进程不认配置：`tr '\0' '\n' < /proc/$(pidof dockerd)/environ | grep -i proxy`，变量都在再实测 `docker pull`。
- 重启 docker 前确认现有容器 restart policy 全是 `unless-stopped/always`（`docker inspect -f '{{.HostConfig.RestartPolicy.Name}}' <容器>`），否则重启 = 服务不回来。
- 本环境自带 OpenClash：**别先挨个试国内公共 mirror**（实测白名单制/收费/EOF 三连败，纯浪费轮次）——直接确认 dockerd 的代理注入，一次就通；mirror 只作代理不可用时的备选。

按容器绕代理：

```bash
# Bypass proxy for a specific domain
NO_PROXY=localhost,127.0.0.1,192.0.2.10/16,192.0.2.10/8,.local docker run ...
```

### BrightData Search Setup

See `references/brightdata-setup.md` for configuring BrightData's search_engine as the primary web search tool (bypasses GFW, returns clean structured results).

### Exa Search Backend (Hermes native web search)

See `references/hermes-exa-search-integration.md` — Hermes natively supports Exa as `web.search_backend` (config.yaml `web:` section or `EXA_API_KEY` env var; `exa-py` already in deps, no install needed). Also lists the other built-in backends (Tavily/SearXNG/Firecrawl) and how to check the current backend.

### Network Health Checks

See `references/node-latency-test.md` for testing connectivity to various endpoints through and bypassing the proxy.

### Key References (from homelab-proxy)

| File | Content |
|------|---------|
| `references/clash-api-connection-inspection.md` | Check if a connection goes through Clash proxy |
| `references/openclash-config-mismatch-diagnosis.md` | Diagnose OpenClash config issues |
| `references/openclash-fakeip-throughput-penalty.md` | Fake-IP mode performance impact |
| `references/openclash-rule-provider-setup.md` | Rule provider configuration |
| `references/openclash-slow-network-triage.md` | Debug slow network through OpenClash |
| `references/openclash-tailscale-bypass.md` | Bypass OpenClash for Tailscale traffic |
| `references/wechat-bypass-openclash.md` | WeChat-specific proxy bypass |
| `references/router-ssh-brute-force-defense.md` | Router SSH brute-force defense |
| `references/lxc-network-optimization.md` | LXC container network tuning |
| `references/docker-hub-tls-failure-data.md` | Docker Hub TLS failures behind GFW |
| `references/huggingface-tls-failure-diagnosis.md` | HuggingFace TLS issues |
| `references/macos-proxy-cleanup-script.md` | macOS proxy cleanup |
| `references/brightdata-setup.md` | BrightData search engine setup |
| `references/free-apis.md` | Free API alternatives |
| `references/mcp-ecosystem.md` | MCP ecosystem overview |
| `references/mcp-governance-guide.md` | MCP governance |
| `references/tool-alternatives.md` | Tool alternatives |
- `references/openclash-dns-mode-decision.md` — fake-ip vs redir-host选择指南，含决策树和修复模板
- `references/voicebox-evaluation.md` — VoiceBox evaluation
| `references/industry-landscape.md` | Industry landscape |
| `references/chinese-app-walled-gardens.md` | Chinese app walled gardens |
| `references/jina-reader-china-failure.md` | Jina Reader failure in China |
| `references/webclaw-fakeip-analysis.md` | WebClaw fake-IP analysis |
| `references/windows-evtx-analysis.md` | Windows EVTX log analysis |
| `scripts/iphone_monitor.sh` | iPhone monitoring script |

## Home Assistant Administration (Consolidated from homeassistant-sysadmin)

When the user asks about Home Assistant (HA), use this section. HA runs inside a PVE LXC container — access it through PVE's `lxc-attach`, not direct SSH.

**Quick access pattern:**
```bash
sshpass -p 'PVE_PASS' ssh root@PVE_HOST "pct list | grep -i 'ha\\|home'"
sshpass -p 'PVE_PASS' ssh root@PVE_HOST 'lxc-attach -n <VMID> -- bash -c '\''COMMAND'\'' 2>&1'
```

**Key containers:** homeassistant (8123), go2rtc (1984/8554), xiaoi-webhook (51666)

**Common issues:** xiaoi-webhook unhealthy (usually benign), SSH timeout for router sensors, Xiaomi humidity range errors, HA API requires auth token

**Full details:** `references/homeassistant-administration.md`, `references/ha-instance-config-2026-05-19.md`, `references/ha-dashboard-layout-optimization.md`
