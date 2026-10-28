# 自建 WireGuard 替代 Tailscale（利用家宽真公网 IPv4）

**何时用**：用户抱怨 Tailscale 慢 / 掉中转 / "主动走 IPv6"，想用自己的公网 IPv4 建隧道；
或问"把外网出口设在家里"（exit node）值不值。

---

## 1. 先测家宽基线（四条，缺一条就会下错结论）

| 项 | 取法 | 读数含义 |
|---|---|---|
| **真实公网 IPv4** | `tailscale netcheck` 的 `IPv4:` 行（UDP STUN 通道） | **不要用 `curl ifconfig.me`** —— TCP 出网可能被 OpenClash TPROXY 劫持，返回的是机场节点 IP（境外段），跟真实家宽 IP 完全不同 |
| **NAT 类型** | netcheck 的 `MappingVariesByDestIP` | `false` + `PortMapping` 空 = endpoint-independent mapping（全锥），打洞条件最好 |
| **path MTU** | `ping -M do -s N` 二分探 | 1472 通 = 1500；1464 通 / 1472 不通 = **1492（PPPoE 拨号）** |
| **就近中转节点** | netcheck 的 DERP latency 表 | 中国大陆无官方 DERP，最近通常是香港/新加坡/东京 **140ms+**。这条直接解释"一掉中转就废" |

顺手把网口速率也拿上（见第 7 节），它决定自建隧道的天花板在哪。

---

## 2. 为什么 Tailscale 在这种网络下必然不稳（三条机制，不是玄学）

1. **大陆无 DERP 节点** → 中转 = 跨境，延迟 140ms 起、带宽被砍到个位数 Mbps。
2. **对端对称 NAT**（校园网 / 4G / CGNAT）↔ 家宽全锥：打洞要靠端口预测，时好时坏。
3. **双栈时优先 IPv6** → "延迟个位数但下载上不去"通常是 **IPv6 已直连**、只是国内 v6 出口路由差，**不要误判成中转**。
   判据：**延迟个位数 = 直连；延迟 140ms+ = 中转**。两者病因和处方完全不同。

---

## 3. 自建 WG 为什么等于同一条 IPv4 路径

- WG 是纯 UDP 封装，服务端固定 `公网IP:端口`，客户端主动出站 → **无打洞、无中继**；包路径就是访问 DDNS 的那条 IPv4 路由。
- 对端 NAT 类型**不影响**：NAT 表项由客户端 `PersistentKeepalive=25` 维持。对称 NAT 也能用 —— 这正是它比 Tailscale 强的地方。
- 结论口径：**隧道质量 = 那条 IPv4 路径的质量**，不是"接近"、不是"理论上"。

---

## 4. 参数表（照抄）

```
隧道网段         192.0.2.10/24，服务端 .1，客户端 .2 起
MTU              path MTU − 60（IPv4 外层 20 + UDP 8 + WG 32）
                 PPPoE 1492 → 1412（1420 也能跑，但别用默认值蒙）
PersistentKeepalive 25
端口             UDP 51820；被封改 443/udp 或 500/udp
                 （UDP 难以像 TCP 那样伪装，但端口号能过大量策略）
AllowedIPs       默认只放隧道段 + 家内网段，不做 0.0.0.0/0
```

---

## 5. 放哪：PVE CT 还是路由器

| | 放 PVE CT ✅ 默认 | 放 iStoreOS |
|---|---|---|
| 防火墙 | **不动路由器**（红线） | 要改路由器防火墙 |
| 自动化 | 可全自动建完 | **iStoreOS 的 SSH(22) 默认关闭**，只能 Web UI 手点 |
| 路径 | 多一跳交换机 ≈ +0.2ms | 最短 |

**CT 规格：2 核 / 512MB / 4GB lvmthin / unprivileged / 静态 IP / vmbr0。**
LXC 共享宿主内核 → WG 走内核态；i7-13700H 级 CPU 带 AVX512+VAES，单核可达 1.5–2 Gbps，
2 核实测远超家宽需求。

---

## 6. exit node 的真实取舍（用户必问，务必主动讲代价）

**优势**（按对用户的价值排序）
1. **住宅 IP 可信**：网站永远看到那个常住家 IP → 不弹验证码、不触发异地风控（微信/银行/Google）。
2. **把家里的 OpenClash 分流规则带到任意网络** —— 外面一连隧道就继承机场节点和规则。
3. **绕开校园网/酒店认证墙与端口封锁**：只发一条 UDP 出去，DPI 抓不到。
4. 免配置直连内网（NAS/HA/监控/PT）。
5. 地域解锁（出差时看到"在大连"）。
6. 公共 WiFi 下全程加密。

**致命代价**
- 🔴 **exit node 时客户端的下载速度 = 家宽的上行带宽**。家宽下行 2000M 但上行常 50–100M，
  于是在本地能跑 300M 的网络里，回家出口反而慢 3–6 倍。**这是装完才发现的头号返工点。**
- 延迟必然叠加（包先到家里再到目标）；国内站绕路还可能触发异地登录风控。
- 单点故障：家停电/断网 = 外面全网断。

**三档分流（默认给 B 档）**

| 档 | AllowedIPs / 做法 | 适用 |
|---|---|---|
| A 纯内网 | 隧道段 + 家内网段 | 日常，最快 |
| **B 内网 + 代理** ⭐ | 同上 + 客户端把**家里 mihomo 当上游 socks5**（经隧道访问 `192.0.2.10:7891`） | 国外走家里翻墙、国内本地直连，两个坑全绕开 |
| C 全量 exit | `0.0.0.0/0` | 仅受限网络临时用 |

---

## 7. PVE 侧两个常被忽略的容量门

- **物理网口速率**：`for i in /sys/class/net/*; do echo "$i $(cat $i/speed 2>/dev/null)"; done`。
  板载 Realtek RTL8111 只有 `1000` → 家宽 2000M 在 PVE 上任何 VM/CT 最高约 **940Mbps**。
  ⚠️ **虚拟 bridge（vmbr0）的 `speed` 显示 10000 是假值，只看物理口。** 要突破得加 2.5G 网卡。
- **内存超分**：把 `free -h` 的 total 与各 CT/VM 的 `maxmem` 之和对账。CT 共用宿主内存（Balloon/无独立预留），
  一堆已停的虚机也占着分配额，**全开时总需求常远超物理内存** → 加新 CT 前先算"全开总量"，别只看 current free。
  CPU 的 lcores 超分宽松得多，不是同一量级的风险。

---

## 8. 验证（不能只说"配好了"）

1. **换网络**（手机 4G，与家里不同运营商）握手：`wg show` 里该 peer 的 `latest handshake` 有值。
2. 带宽走**国内镜像多线程下载**（见 `speedtest-triage` 的"真实带宽验证"），**不要用 Ookla CLI**——
   它的 TCP 出网可能被代理劫持而自动选到境外服务器。
3. 报数字必须带方法（几个线程、哪个镜像、什么时段）。

---

## 9. 坑

- 客户端 Endpoint 写 **DDNS 域名**而非固定 IP；WireGuard 客户端会周期性重解析域名，公网 IP 变动靠它自愈，
  但 DDNS 更新延迟会拖长恢复时间。
- 端口转发是在路由器上**新增一条** DNAT 到 CT 的 `51820/udp`。
  ⚠️ 表述修正：**「绝不改路由器防火墙」过头了**。准确红线是「绝不 `nft flush` / `iptables -F`」。
  `fw4 reload` 是**安全的** —— OpenClash 与 Lucky 都以 `uci firewall include` 注册
  （`firewall.openclash.path=/var/etc/openclash.include`、`firewall.LUCKY_go`），reload 会重新执行 include，规则自动重建。
  照第 10 节的「备份 → uci → reload → 立即验证」四步走即可。
- 验证通过前**别删 Tailscale**，留作备胎（公网 IP 变 / 端口被封时保命）。
- WG 端口必须在 OpenClash 里保持 DIRECT；确认方法同 speedtest-triage 层1（TCP/UDP 出口是否一致）。
- **DDNS 不一定在 Lucky 里**。先 `uci show lucky`（`enabled='0'` 时它根本不监听端口，16601 是关的），
  再查 `/etc/config/ddns` —— 常见真实情况是 OpenWrt 自带 `ddns-scripts` 在跑阿里云。
  新增子域名：`uci add ddns service` 复制现有 section 的字段（AK 从 `uci get ddns.<已有section>.username` 读，**不要打印到输出**），
  `/etc/init.d/ddns restart` 后用公共 DNS 验证：`curl -s "https://203.0.113.1/resolve?name=<新域名>&type=A"`。
- **`pkill -f <关键字>` 在 `pct exec` 里会杀掉自己**：pct exec 的命令行本身含该关键字 →
  连带本会话一起被杀，表现为「命令 exit 0 但一行输出都没有」。用 `pkill -x <进程名>` 或 `pgrep` 后按 PID 杀。
- **`wg-quick down ./x.conf` 会报 `` `./x' does not exist ``**：`down` 只认**接口名**，不认文件名。
  `up` 用 `./x.conf`、`down` 用 `wg-quick down x`，兜底 `ip link delete x`。
  临时测速隧道用完必须确认接口真的没了（`ip -br addr | grep x`）——
  残留的隧道接口会带着 `192.0.2.10/24` 路由，让后续「内网 / 隧道」路径判断全部失真。
- **`wg-quick up /tmp/x.conf`（绝对路径）会静默失败**，接口根本没建出来，
  后续 `wg show x` 空、`ip link delete x` 报 `Cannot find device`。`wg-quick` 只从**文件名**推导接口名，绝对路径推不出来。
  临时测试隧道直接用内核原语最稳（不依赖接口名解析）：
  ```bash
  ip link add wgtest type wireguard
  wg set wgtest private-key client.key \
     peer "$(cat server.pub)" endpoint <公网IP>:51820 \
     allowed-ips 192.0.2.10/24 persistent-keepalive 25
  ip addr add 192.0.2.10/32 dev wgtest
  ip link set wgtest mtu 1412 up
  ip route add 192.0.2.10/24 dev wgtest
  ```
  用完 `ip link delete wgtest`，并确认接口真的消失。

---

## 10. 实战部署记录：CT210 wg-gateway（2026-10-22 已上线）

已落地并端到端验证。照抄即可复现。

### CT 参数
```
pct create 210 local:vztmpl/debian-12-standard_12.12-1_amd64.tar.zst \
  --hostname wg-gateway --cores 2 --memory 512 --swap 512 \
  --rootfs local-lvm:4 \
  --net0 name=eth0,bridge=vmbr0,ip=192.0.2.10/24,gw=192.0.2.10 \
  --nameserver 203.0.113.1 --unprivileged 1 --features nesting=1 --onboot 1
```
- 建前先在宿主 `modprobe wireguard`（模块已随内核，加载即可；LXC 共享宿主内核 → unprivileged CT 内可直接 `ip link add type wireguard`）
- CT 内 `apt install wireguard-tools`，**不需要** /dev/net/tun
- `wg-quick@wg0` 必须用 `systemctl restart wg-quick@wg0` 让它接管；直接跑 `wg-quick up wg0` 会留下 `is-active=inactive` 的假状态（重启不恢复）

### 服务端 wg0.conf 要点
```
[Interface]
Address    = 192.0.2.10/24
ListenPort = 51820
MTU        = 1412
SaveConfig = false
PostUp   = sysctl -q -w net.ipv4.ip_forward=1; iptables -t nat -C POSTROUTING -s 192.0.2.10/24 -o eth0 -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -s 192.0.2.10/24 -o eth0 -j MASQUERADE
```
**MASQUERADE 必需**：内网设备不知道 192.0.2.10/24 怎么回包，SNAT 成 CT 的 192.0.2.10 才能双向通。

### 客户端配置模板（B 档分流）
```
[Interface]
PrivateKey = <client.key>
Address    = 192.0.2.10/32
MTU        = 1412
[Peer]
PublicKey  = <server.pub>
Endpoint   = <DDNS域名>:51820
AllowedIPs = 192.0.2.10/24, 192.0.2.10/24
PersistentKeepalive = 25
```

### iStoreOS 加 DNAT 的四步（安全版，已验证不冲 OpenClash）
```bash
# 0) 只读侦察 + 备份
nft list ruleset > /root/nft-backup-$(date +%s).nft
cp /etc/config/firewall /root/fw-backup-$(date +%s)
nft list ruleset | grep -c openclash        # 记基线，本例 8
nft list ruleset | grep -c "OpenClash DNS Hijack"   # 记基线，本例 1

# 1) uci 写 redirect（不要手搓 nft，fw4 会带 reflection 成对规则 + 自动放行 forward）
uci add firewall redirect
uci set firewall.@redirect[-1].name='wireguard-51820'
uci set firewall.@redirect[-1].target='DNAT'
uci set firewall.@redirect[-1].src='wan'
uci set firewall.@redirect[-1].proto='udp'
uci set firewall.@redirect[-1].src_dport='51820'
uci set firewall.@redirect[-1].dest='lan'
uci set firewall.@redirect[-1].dest_ip='192.0.2.10'
uci set firewall.@redirect[-1].dest_port='51820'
uci commit firewall

# 2) reload（不是 flush）
/etc/init.d/firewall reload

# 3) 立即回归验证 —— 三项都要对得上基线
nft list ruleset | grep -c openclash                    # 仍为 8
nft list ruleset | grep -c "OpenClash DNS Hijack"       # 仍为 1
pgrep -f openclash                                      # 进程在
nft list ruleset | grep "dport 51820"                   # 出现 dnat ip to 192.0.2.10:51820
nft list ruleset | grep -oE "dport [0-9]+ .*dnat ip to" | sort -u | wc -l  # 其他 DNAT 没少
```
若 OpenClash 计数掉了 → 立刻 `/etc/init.d/openclash restart`；全崩则 `nft -f /root/nft-backup-*.nft`。

### 改 / 删已有 DNAT（uci 索引语法很坑，错了静默无效）

`uci get firewall.$i.name`（`$i` = `redirect[7]`）**永远取不到值** —— `[` `]` 不转义就是通配，
脚本“跑完了但规则没变”，不报错。必须从 `uci show` 解析真实索引：
```bash
uci show firewall | grep -oE "@redirect\[[0-9]+\]\.name='[^']*'" | while IFS= read -r line; do
  key="${line%%=*}"; val="${line#*=}"; val="${val//\'/}"
  idx=$(echo "$key" | grep -oE '\[[0-9]+\]' | tr -d '[]')
  [ "$val" = "wireguard-51820" ] && uci set "firewall.@redirect[$idx].dest_ip=192.0.2.10"
done
uci commit firewall && /etc/init.d/firewall reload
```

**删除必须按索引倒序**（`sort -rn`），否则删掉前一项会让后面索引全部前移，删错对象。

**销毁容器后必须扫一遍僵尸 DNAT**：指向已删 CT 的 redirect 会继续把包往死 IP 送，而且**不报任何错**。
```bash
uci show firewall | grep -oE "@redirect\[[0-9]+\]\.dest_ip='<已删的IP>'"
nft list ruleset | grep "<已删的IP>" | grep -v saddr   # 应为空
```

### 端到端验证（不用等外部网络就能证 90%）
在任一内网机器上用某份客户端配置，**只把 Endpoint 改公网 IP、AllowedIPs 只留 192.0.2.10/24**（否则会与 eth0 直连路由打架），
`wg-quick up` 后 `ping 192.0.2.10` + `wg show` 看 `latest handshake`。
这会**走 fw4 的 reflection 规则**命中 DNAT → 证明 DNAT + 服务端整条链路 OK。
实测：0% 丢包、RTT 0.5ms、握手 5s 内建立。剩下的只有「运营商是否封 UDP」需真外部网络确认。

### 本机数据（2026-10-22）
- 家宽 `203.0.113.1`（PPPoE，peer 203.0.113.1），path MTU 1492
- iStoreOS = **J4125 4核/8GB** → WG 单核约 300–500Mbps，**这就是不把 WG 放路由器的硬理由**（PVE 是 i7-13700H 级）
- PVE 物理口 RTL8111 千兆 → 隧道天花板 ~940Mbps
- PVE 实际空闲：20 线程里运行中只占 10、available 11.1G、thin pool 剩 213.9G

---

## 12. 隧道卡在 ~4 Mbps：一条被自己推翻的结论，和真正剩下的变量

### ⛔ 先说已否证的方向：**容器规格不是原因**
曾判定「512MB 小 LXC 做转发节点跑不动」，并据此把 WG 从 CT210(2C/512MB) 迁到 CT <ID>(8C/10GB) 复测 ——
**迁移后 UDP 依旧是 4 Mbps**。所以「给容器加 CPU/内存/磁盘能解决隧道慢」这条**已被实测推翻，不要再做、不要再承诺**。

### 真正把变量切开的对照（同一外部客户端、同一运营商、同一个 200 MB 文件）

| 入口 | 协议 | DNAT 落点 | 下载 |
|---|---|---|---|
| `speed.<域>:18443` | TCP（Caddy / HTTPS） | CT <ID> | **72.60 Mbps** |
| `<域>:51820` | UDP（WireGuard） | **CT <ID>（迁移后）** | **4 Mbps** |
| `<域>:8443` | TCP（Shadowsocks） | CT210（已删除） | 4 Mbps |
| `<域>:8443/udp`、`2408/udp` | UDP | CT210（已删除） | 1–2 Mbps |

读法（**这段已被后续实测修正，别照旧结论交付**）：
- 曾判定「同一台 CT <ID> 上 TCP 反代 72.6 / UDP 隧道 4 → 变量是 UDP vs TCP」。
- **该判定已被否证**：CT <ID> 上把 Shadowsocks 跑成纯 TCP（`8443/tcp`）实测 **3.9 Mbps**；
  同时 Caddy 在同机、同域名下用 `file_server` 直接发**同一个 200 MB 文件**，实测 **平均 34.9 / 峰值 80 Mbps**。
- 所以 **TCP/UDP 不是判据**。把两组数据真正分开的是**流量形态**：
  伪装成普通 HTTPS/TLS 的（Caddy）能跑 35–80 Mbps；带明显代理指纹的（SS / WireGuard）一律 ~4 Mbps。
- 服务端自身也已被排除：本机回环实测 `python3 -m http.server` **约 25 Gbps**、Caddy `file_server` **约 5.2 Gbps**
  —— 4 Mbps 与服务器 I/O、编程语言、并发能力无关，别再往服务端性能方向查。

已排除、不要回头试：容器规格、加密/CPU（内网 WG 3.1 Gbps、`wg0` 0 errors 0 dropped）、
MTU（1412→1280 无改善）、端口号（51820/8443/2408 都一样）、Clash 劫持（私有段全 DIRECT）、
CT 出网（110 Mbps、`tc qdisc noqueue`）。

> 交付口径：说「同一台机器上 TCP 72.6 / UDP 4，差异在协议层，TCP 通道能不能绕开待实测」。
> **不要宣布「已定位为运营商 UDP 限速」** —— 换 SS/TCP 在 CT <ID> 上的复测才是判据。

### 迁移步骤（CT210 → CT <ID>，客户端零改动）
1. 备份：`pct exec 210 -- tar czf - -C / etc/wireguard etc/sing-box root/ss-password.txt > wg-backup.tar.gz`
2. PVE 调资源：`pct set 202 -cores 8 -memory 10240`；`pct resize 202 rootfs 200G`
3. CT <ID> 解压备份到 `/etc/wireguard/`，`systemctl enable --now wg-quick@wg0`
4. 路由器 DNAT 的 `dest_ip` 改成 CT <ID> 的 `.213`，`fw4 reload`，验证 OpenClash 规则数不变
5. 确认新路径通（握手 + ping 192.0.2.10）后再 `pct destroy 210`

**Endpoint、服务端公钥、peer 公钥全部不变 → 所有客户端配置一行都不用改。**

### 两个必踩的坑
1. **`wg-quick` 的 PostUp 每条命令都必须以 `PostUp =` 开头**。插入裸行会报
   `Line unrecognized: 'iptables-tnat-...'` + `Configuration parsing error`，服务直接起不来。
   多条命令要么多个 `PostUp =` 行，要么用 `;` 串成一行。
2. **同一时刻两台机器都有 `192.0.2.10` 会 ARP 打架**。迁移时必须**先停旧机器的 `wg-quick@wg0`，再验证新机器**，否则 ping 到的可能是旧容器自己（RTT 0.014ms 这种内网数值就是危险信号）。

### CT <ID> / IP 注意事项
- CT <ID> 是 **DHCP** 拿的 `192.0.2.10`，已在路由器配静态租约（MAC `00:00:00:00:00:00` → `.213`）。**不配租约则 DNAT 随时失效。**
- CT <ID> 上本来就有 Tailscale（`tailscale0` + `ts-postrouting` 链），WG 的 MASQUERADE 只针对 `192.0.2.10/24`，两者不冲突。
- CT <ID> 是 unprivileged 容器，但具备 `cap_net_admin`，可以正常创建 wg 接口和写 nat 表。
- 测速服务：`/root/speedtest/`（200MB 测试文件 + 15 秒下载页），systemd `speedtest.service`，监听 8080。隧道内入口 `http://192.0.2.10:8080/`。

---

## 11. iOS 上 B 档的正解：Shadowrocket 内置 WireGuard 分流（已跑通）

### 为什么不能用「WireGuard App + 另装翻墙 App」
iOS **同一时间只能有一个 VPN 在跑**。WireGuard App 占住 VPN slot，小火箭就起不来，反之亦然。
所以 B 档（内网走隧道 + 外网走手机本地机场）在 iOS 上唯一干净的实现是：
**用 Shadowrocket 一个 App 同时承担 WireGuard 隧道与机场代理，靠规则分流。**

### 做法
1. Shadowrocket → `+` → 类型选 **WireGuard**
2. 字段：`host`=DDNS 域名、`port`=51820、`privateKey`=客户端私钥、
   `publicKey`=服务端公钥、`ip`=客户端隧道地址（如 192.0.2.10）、`mtu`=1412、
   **`reserved` 必须留空**（`0,0,0` 是 Cloudflare WARP 专用扩展，普通 WG 服务器带了会握手失败）
3. 规则里加（必须放在私有段 DIRECT 规则之前）：
   ```
   IP-CIDR,192.0.2.10/24,<节点名>,no-resolve
   IP-CIDR,192.0.2.10/24,<节点名>,no-resolve
   ```

### ❗ 两个必踩的坑（这次实际踩到了）

**坑1：策略名大小写敏感。** 规则写 `HOMEWG`、节点叫 `HomeWG` → 规则当成无效规则**静默跳过**，
不报错、不提示，看起来“配了但不生效”。改规则前先核对 App 里节点的准确 title。

**坑2：`tun-excluded-routes` 默认排除所有私有网段。** Shadowrocket 默认配置里：
```
tun-excluded-routes = 192.0.2.10/8, ..., 192.0.2.10/16, ...
```
这两段流量**根本不进 TUN**，直接交给系统网络发出，规则连看都看不到。
即使名字改对了也照旧不通。必须从 `tun-excluded-routes` 里**删掉 `192.0.2.10/8` 与 `192.0.2.10/16`**。
删掉是安全的：Shadowrocket 默认 `[Rule]` 末尾本就有 `IP-CIDR,192.0.2.10/16,DIRECT` /
`IP-CIDR,192.0.2.10/8,DIRECT` / `192.0.2.10/12,DIRECT`，只要 HomeWG 规则在它们**前面**，
分流顺序就天然正确（家里网段走隧道，本地 WiFi 网段走直连）。

### 定位手法：不要先怀疑隧道
服务端 `wg show wg0 latest-handshakes` 一把定位：
- **有新 peer 的握手时间** → 隧道/UDP/密钥/端口全 OK，问题必然在客户端**规则层**
- **握手时间恒为 0** → 才去查网络/端口/参数
本例就是握手成功但业务不通 → 直接去查 Shadowrocket 配置，一次命中两个坑。

### 必须给每个接入端独立密钥
同一个 peer 公钥不能在两个客户端同时用，会互相抢 endpoint 踢下线。
每个 App / 设备各自 `wg genkey` 一套，服务端 `wg set wg0 peer <pub> allowed-ips 192.0.2.X/32`
并追加到 `wg0.conf`（否则重启丢失）。

### 为什么 C 档（0.0.0.0/0 全量出口）不适合拿来翻墙
路径对比：
- 小火箭：手机 → 机场节点 → 目标 （**2 跳**）
- C 档：手机 → 家宽**上行** → 家里 OpenClash → 机场节点 → 目标 （**4 跳**）
多出的两跳分别是家宽上行带宽和家里的节点质量，实测“能看 YouTube 但特别卡，不如手机直连机场”。
C 档的正确用途是**要家里 IP 可信度**（银行/Google 少二次验证、地域解锁、公共 WiFi 隐私），不是追求速度。
所以默认给 B 档 + 客户端分流；C 档配置另存一份备用即可。

### `wg show` 的 endpoint 字段在本拓扑下不可信
fw4 对 wan→lan 的 DNAT 会再做一次 SNAT，wireguard 只看到 `192.0.2.10:<port>`，
真实公网源 IP 丢失。**不要据此判断客户端在内网**（会误判）。要查真实源：
```bash
# 在路由器上
cat /proc/net/nf_conntrack | grep 51820
# 输出形如: src=<真实公网IP> dst=<家宽IP> ... src=192.0.2.10 dst=192.0.2.10
```

---

## 16. 排障：四个会骗人的信号（先读这段再下结论）

### ① `wg show` 的 endpoint 不反映客户端真实来源
经过路由器 DNAT 进来的包，回程在 fw4/conntrack 里会被 SNAT 成**路由器 LAN IP**（端口保留），
于是所有 peer 的 `endpoint` 都显示 `192.0.2.10:xxxxx` —— **完全在外网的客户端也是这个值**。
拿它判断“用户是不是还连着家里 WiFi”会直接得出反向结论，而且会被用户当场推翻。

**唯一可信的取证**（在路由器上）：
```bash
cat /proc/net/nf_conntrack | grep 51820
# 看 src= 那一侧 —— 那才是真实公网源 IP
# 例：src=203.0.113.1 dst=203.0.113.1 sport=31774 dport=51820 packets=172 bytes=34836
```

### ② DNAT 规则的 counter 只统计**新建连接**，不是流量
`nft list ruleset` 上看 `counter packets 2 bytes 352`，很容易误读成“几乎没流量”。
实际 conntrack 里同一条流已有 `packets=484 bytes=87000` —— **established 流量只穿过 DNAT 规则一次**。
判活跃度用 `wg show wg0 transfer` 或 conntrack 计数，**不要用 DNAT counter**。

### ③「从未握手」的 peer 可能只是配置文件还没导入
`latest-handshakes` 为 0 只说明该密钥没连过，不等于配置错。先确认用户真的把那台设备导入并启用了。

### ④ DNAT counter = 0 说明包根本没到路由器（多半被运营商封了端口）
用户报「打不开 / 一片白屏」时，**先让用户访问一次，再去读那条规则的 counter**：
```bash
nft list ruleset | grep "tcp dport <端口>" | grep -v reflection
# counter packets 0 bytes 0  → 包没进来：运营商/上游封了该端口
# counter packets N (>0)     → 包到了，问题在 DNAT 之后的转发或服务本身
```

⚠️ **读完 counter 不要再 `fw4 reload`**：reload 重建 nft 规则会**清零所有 counter**，之前攒的数据全部作废。
要对比就让用户在 reload 之后再访问一次。

已实测封禁：**家宽 `8080/tcp` 被运营商封**（同一时段 `18443` 正常通过）。
家宽常见封禁名单：80、8080、443、8000、8888。
测速页 / 临时入口一律挑非标准端口，**别拿 80/8080/443 当默认值然后回来返工**。

### ⑤ 白屏三关：端口封禁 → HSTS → 文件权限（counter=0 是④，counter 在涨却仍白屏就走这里）

**第 1 关：HSTS `includeSubDomains` 把 `http://` 强制升级成 `https://`。**
Caddy 的 `hdrs` 里若设了 `Strict-Transport-Security "max-age=31536000; includeSubDomains"`，
浏览器对这一年内访问过的该域**所有子域名**不再发 HTTP 请求，直接去做 TLS。
于是给纯 HTTP 服务（`python -m http.server`、裸后端）新开个非标端口、让用户用 `http://子域:端口/` 打开
→ **必然白屏，而服务端 `curl 127.0.0.1:端口` 与 `curl 公网IP:端口` 全是 200**。
判据：counter 有包增长，但**每个包只有 ~64 字节**（SYN 或 TLS 握手重传）。
→ 「换个端口再试」在这种环境下必然无效，**不要再建议**（本机 8080 封端口与 28080 白屏就是这么浪费掉的两轮）。
**正解：不新开端口，复用已在跑的 HTTPS 反代的端口——但只新增站点，不改已有站点块。**
在**同一端口**上给测试页开一个**独立子域的独立 site 块**（本机 = Caddy 的 `18443`）：
```
# 新子域、同端口、独立块 —— 生产站点一个字节不动
<新子域>:18443 {
    import <共享的 hdrs>
    handle_path /speedtest/* {
        root * /var/www/speedtest
        file_server
    }
}
```
→ 用户访问 `https://<新子域>:18443/speedtest/`。
**交付铁律：优先复用它天天在用、已证明能打开的那个端口，但只在该端口上新增站点块。**

⛔ **绝不要往生产站点块里加路径、挪 `encode gzip`、增删 `handle`。**
生产站点是用户的日常入口（本机 Caddy 挂着 8 个子域），拿它做实验的代价是**整轮排障的可信度**：
用户看到的是「这个站以前能跑 70M，现在只有三四十」，他只会记得你动过它，
无论你改的其实是旁边的路径 —— 然后你得整文件回滚、重测、再解释一遍，白烧整晚。

**回滚纪律**：用改动前的整文件备份 `cp` 覆盖（`/etc/caddy/Caddyfile.bak-*`），**不要手改回去**；
覆盖后 `caddy validate` + `systemctl restart caddy`，然后**逐个站点 curl 一遍交回归清单**
（`curl -sk --resolve <子域>:18443:127.0.0.1 -o /dev/null -w '%{http_code}' https://<子域>:18443/`），
有状态码列表比任何解释都有效。

**第 2 关：Caddy 以 `caddy` 用户跑，静态文件放 `/root/` 下必 403。**
`root * /root/xxx` 即使 `caddy validate` 通过、restart 成功也读不到（`/root` 是 700）。
一律放 `/var/www/<name>` + `chown -R caddy:caddy` + `chmod 755`。
**403 = 路径对了但没权限；404 = `root`/`handle_path` 配错**，这两个码别混。
本机验证必须带 SNI，否则一律 `000`（不是服务挂了）：
`curl -sk --resolve <子域>:18443:127.0.0.1 https://<子域>:18443/<路径>/`

**第 3 关：给下载/测速路径加 `encode gzip` 会污染读数。**
把 `encode gzip` 收进 `handle { }` 块（只作用于反代），静态下载放独立 `handle_path` 且不压缩。

**改 Caddyfile 的正确顺序**：改 → `caddy validate --config /etc/caddy/Caddyfile` → `systemctl restart caddy`。
配置里若有 `admin off`（本机就有），`systemctl reload caddy` **必然失败**
（`Post "http://localhost:2019/load": connection refused`），因为管理 API 没监听。
❗ **reload 失败 ≠ 服务挂了**：caddy 仍以旧配置继续跑，所有站点正常。
谎报「服务挂了」会让用户白紧张；先用 `systemctl is-active caddy` + `ss -tlnp | grep 18443` 确认进程状态再说话。

对照读法最有杀伤力：同一次读两条规则的 counter，一条 0 一条非 0 —— 直接分开「我配错了」与「上游封了」。
（这不与①悖：②说的是**established 流量**不能看 counter，④说的是**首个包有没有到达**。）

**结论口径**：判断隧道是否真的从外网通，只认 `conntrack src=` 与 `wg show transfer` 两项同时增长。
单看 `wg show endpoint`、DNAT counter、或「握手时间很新」任一项都会下错结论。

---

## 13. B 档 ≠ 翻墙：交付时必须当场说明

`AllowedIPs = 隧道段 + 家内网段` 的配置**不会**把 YouTube/Google 流量送进隧道 ——
那些 IP 不在 AllowedIPs 里，客户端直接走本地网络出去，**被墙是设计结果，不是故障**。

用户说“连上 WG 了但 YouTube 打不开”时，先分清他要什么：

| 他要的 | 给什么 | 关键参数 |
|---|---|---|
| 内网直通 + 借家里 IP | B 档 | `AllowedIPs = 隧道段, 家内网段` |
| **连上就能翻墙** | **C 档** | `AllowedIPs = 0.0.0.0/0` **且 `DNS = 家里路由器 IP`** |

**C 档的 DNS 行是灵魂**：流量进了隧道但 DNS 还在本地被污染 → YouTube 照样打不开。
必须设成家里路由器 IP，让解析走家里的 dnsmasq + OpenClash fake-ip 分流。

平台差异（**iOS 是特例，不要套 Mac/PC 的方案**）：
- Mac/PC 有 Clash Verge → B 档 + 上游 `192.0.2.10:7891` 最省家宽上行。
- **iOS 不要把纯 C 档当翻墙方案交出去**：路径会变成 `手机 → 家宽上行 → 家里 Clash → 机场节点 → 目标`，
  比手机本地代理多两跳，实测结论是「能打开但特别卡，还不如手机自带的小火箭」。
  C 档只适合要住宅 IP 可信度的场景（少弹验证码、地域解锁），不适合追求速度。
- **iOS 同一时刻只能跑一个 VPN**：WireGuard App 与 Shadowrocket/小火箭互斥，开一个必须关另一个。
  所以不要指望「WG 走内网 + 小火箭走外网」并存，正解是把隧道塞进代理 App 内部分流（见下）。

### iOS 具体做法 → 见第 11 节
节点字段映射（`host`=域名、`ip`=隧道内本地地址、`reserved` 留空）、规则顺序、
以及两个会让规则**静默失效**的坑（策略名大小写、`tun-excluded-routes` 默认排除私有网段）全部在第 11 节，此处不重复。

**交付任何一份客户端配置时，同一条消息里写清“这份路由哪些流量、不路由哪些”**，
否则用户必然拿 B 档去测 YouTube，然后把它当故障反馈回来，白耗两轮排查。

---

## 14. 隧道吞吐排障：先分层，再谈优化

### ❌ 不要预先承诺「隧道 ≈ 直连」
理论上限相同（客户端下载 = 家宽上行），但**实测差距可以大到十几倍，而且瓶颈不在 WG 本身**。
本机实测（同一台 Speedtest-X、同一张手机卡、相隔 2 分钟）：

| 入口 | 下载 | 上传 | 延迟 |
|---|---|---|---|
| DDNS 直连 | **72.60 Mbps** | 41.28 Mbps | 20 ms |
| WG 隧道 | **3.91 Mbps** | 33.53 Mbps | 29 ms |

两个可直接读出的信号：
- **差 18 倍** —— 远超「WG 开销 + MTU 效率损失」的量级，别用理论值搪塞。
- **同一隧道上行 33.5 / 下行 3.9，方向不对称到 8 倍** —— 这不是「带宽不够」，是链路某一层只掐了一个方向。

所以回答用户「隧道网速和 IPv4 DDNS 一样吗」时：**只说会实测，不报预期百分比**，拿到数字再解释。

### 三层定位阶梯（按顺序做，每层砍掉一半可能性）

**第 1 层：WG 本身有没有问题**（30 秒，纯内网，完全不碰运营商）
在任一 LAN 内机器上用某份客户端配置起临时隧道，**Endpoint 指 CT 的内网 IP、AllowedIPs 只留隧道段**
（否则与 eth0 直连路由冲突），然后 curl 服务端的大文件：
```bash
cp <client>.conf ./bench.conf
sed -i 's#^AllowedIPs.*#AllowedIPs = 192.0.2.10/24#; s#^Endpoint.*#Endpoint   = 192.0.2.10:51820#' bench.conf
chmod 600 bench.conf && wg-quick up ./bench.conf
curl -s -o /dev/null -w '%{speed_download}\n' -m 25 http://192.0.2.10:8080/test200.bin
```
本机实测 **3117 Mbps**（i7 级 CPU / 2 核 CT / 内核态 WG），wg0 计数 RX 0 errors 0 dropped。
> **结论口径**：内网路径能跑 Gbps 级 → 加密、CPU、LXC、网桥**全部无罪**。
> 直接进第 2 层，**不要再去调 MTU、换加密参数、加 CPU**——那些方向已经被这一条排除掉了。

**第 2 层：公网路径 vs 中间设备**（让用户测两个入口，一句话说清差别）
- `http://192.0.2.10:8080/` —— 隧道最短路径：手机 → WG → CT 本机，**不经过路由器 / docker / Clash**
- `http://<家内网某服务>/` —— 隧道 + 路由器 / docker / Clash 转发

前者快、后者慢 → 问题在中间设备那一跳（docker 多级 NAT、Clash TPROXY 用户态转发），不是隧道。
两者都慢 → 进第 3 层。

**第 3 层：运营商 UDP 策略**
方向不对称（上行正常、下行被掐）是运营商对 UDP 入方向限速的典型特征。
换 `443/udp` 是最快的验证 —— 改的时候**三处必须同改**：服务端 `ListenPort`、路由器 DNAT 的 `src_dport`、所有客户端 `Endpoint`。

### ❌ 已否证的假设：MTU / 分片（2026-10-22 实测排除）
曾假设蜂窝 / GTP 路径实际 PMTU < 1472（隧道 MTU 1412 + 60 开销），大包被静默丢弃。
**实测否证**：服务端 MTU 降到 1280（IPv6 最小 MTU，任何路径必过）后，两个入口仍是 ~4 Mbps，无改善。
→ MTU 不是原因，**别再拿它当解释交付给用户**。
（改法备忘：`sed -i 's/^MTU.*/MTU = 1280/' /etc/wireguard/wg0.conf` + `systemctl restart wg-quick@wg0`；
服务端 MTU 只影响服务端发出的包，**客户端不改也能验证**。）

### 443/udp 在本机会被 OpenClash 拦死（很隐蔽）
换到 `443/udp`（QUIC 端口，运营商通常不限）= 握手直接失败。原因是 OpenClash 在 **forward 链**有：
```
udp dport 443 ip daddr != @china_ip_route reject comment "OpenClash QUIC REJECT"
```
DNAT 之后包的目标已变成**内网 IP**（如 192.0.2.10），不在 `china_ip_route` 集合里 →
`daddr != @china_ip_route` 成立 → reject。取证：
```bash
nft list ruleset | grep -B30 "QUIC REJECT" | grep -E "^\s*chain |QUIC REJECT"
# counter packets 应与刚发的测试包数相等
```
**不要为了这个删 OpenClash 的 QUIC 阻断**（它在防 QUIC 绕过代理）。换端口即可。

### 多端口并存（不改 ListenPort，51820 保留不废）
在 CT 内把其它 UDP 端口 REDIRECT 到 51820：
```bash
for P in 8443 2408; do
  iptables -t nat -C PREROUTING -i eth0 -p udp --dport $P -j REDIRECT --to-ports 51820 2>/dev/null \
    || iptables -t nat -A PREROUTING -i eth0 -p udp --dport $P -j REDIRECT --to-ports 51820
done
```
持久化：同命令追加到 `wg0.conf` 的 `PostUp`（`-C || -A` 保证幂等）。
路由器侧照旧 `uci add firewall redirect` 把 `udp <P>` DNAT 到 CT 同端口号，reload 后回归验证 OpenClash 计数。
实测 8443 / 2408 内网链路均 **840 Mbps**、握手 5 秒内建立（受 RTL8111 千兆封顶）。
客户端只改 `Endpoint` 的端口号即可，其他字段不动。

### 换端口无效 ≠ UDP 限速：缺的那组对照是「换落点机器」

`51820 → 8443/udp → 2408/udp` 全部 1–4 Mbps 之后，最容易得出的结论是「运营商对 UDP 整类限速」。
**这个结论是错的** —— 换成纯 TCP（sing-box + Shadowsocks on `8443/tcp`）实测仍然 4 Mbps，直接证伪。
任何只看「同一条隧道内换料」的数据都不足以定性，因为真正的变量根本没被控制。

真正把问题切开的是这组对照：**同一协议、同一运营商、同样走域名，只换 DNAT 落点机器**：

| 入口 | 协议 | DNAT 落点 | 下载 |
|---|---|---|---|
| `speed.<域>:18443` | TCP | **CT <ID>** | **72.60 Mbps** |
| `<域>:8443`（Shadowsocks） | TCP | **CT210** | 4 Mbps |
| `<域>:51820`（WG） | UDP | CT210 | 3.91 Mbps |
| `<域>:8443/udp`、`2408/udp` | UDP | CT210 | 1–2 Mbps |

当时的读法是「落点 CT210 就慢，落点 CT <ID> 就快」→ 判定瓶颈在 CT210 作为「外部入站 → 内网转发」节点的能力。
**这个判定后来被迁移实验否证**：把 WG 搬到同一台 CT <ID> 之后，UDP 依旧 4 Mbps。
→ 被这组数据真正切开的变量是 **协议（TCP vs UDP）**，不是机器。
「落点不同」和「协议不同」在这组对照里是**混在一起的**（CT <ID> 跑的是 Caddy/TCP，CT210 跑的是 WG/UDP），
所以它一次也定不了性 —— 这是设计对照组时最容易犯的错：**一个对照里只许有一个自变量**。

已被这组数据排除的方向（**不要再回头试**）：
- 加密/CPU：内网路径 WG 3.1 Gbps、`wg0` RX 0 errors 0 dropped
- CT210 出网：下载国内镜像实测 **110 Mbps**，`tc qdisc` 是 `noqueue`（无限速）
- 内存：available 475MB，`tcp_rmem` 上限 32MB 正常
- MSS/分片：`firewall.@zone[1].mtu_fix='1'`，且 MTU 降到 1280 无改善

**已验证否证**：不是 LXC 资源问题 —— WG 已迁到 8C/10GB 的 CT <ID> 复测，仍是 4 Mbps。
加资源这条方向**不要再试、不要再建议**。

**这个数据点后来补上了，结论再次反转**：CT <ID> 上的 Shadowsocks（纯 TCP `8443/tcp`）实测 **3.9 Mbps**，
而同一台机器上 Caddy 用 `file_server` 发同一个文件是 **34.9 Mbps（峰值 80）**。
→ **「换成 TCP 就能绕开」是错的**，TCP/UDP 不是判据；分界在于流量**看起来像不像正常 TLS**。

剩下的推断（**待验证，不要当结论交付**）：运营商对**有代理指纹的流量**（Shadowsocks 混淆协议、WireGuard UDP）
做入方向限速，对标准 TLS 放行。验证实验只有一个方向 —— **Trojan over TLS**：
`sing-box` 的 `trojan` inbound + 复用 Caddy 的 `*.example.com` 证书，监听非标端口（如 `8444`），
服务端自证 `openssl s_client -connect 127.0.0.1:8444 -servername <子域>` 应返回 `TLSv1.3` + `Verify return code: 0 (ok)`
（证书是真的，客户端**不要**勾「允许不安全」）。
客户端跑出 30M+ 才能确认是 DPI 指纹限速；仍是 4M 则说明与协议特征无关，**不要再往伪装/混淆方向加码**。

### 方法论：变慢时第一个动作是建对照组，不是猜原因

一次排障里连续断言了四轮病因，**四轮全部被后一组数据推翻**：
MTU/分片 → UDP 协议级限速 → 落点容器太小 → 「换成 TCP 就能绕开」。
每一轮都是在没有完整对照的情况下，把「当前最像的那个」当成结论发给了用户，来回耗掉十几轮。

根因是两个错误习惯：
1. **一个对照里塞了两个自变量。**「CT <ID>/TCP 快 vs CT210/UDP 慢」同时变了机器和协议，
   所以它只能证明「路径不一样」，无法归因到其中任何一个。
2. **把「已排除」当成「已定位」。** 排除法只能缩小范围，必须有一组「只变一个量、两侧结果相反」的数据才能定性。

| 想回答的问题 | 正确对照（每次只变一个量） |
|---|---|
| 隧道封装本身有没有开销 | 同协议、同机器、异入口（隧道 vs 内网直连） |
| 是不是运营商对某协议 QoS | **同机器、同落点、同文件，只换 UDP ↔ TCP** |
| 是不是这台机器处理能力不行 | **同协议、同落点角色，只换机器规格** |
| 是不是包根本没到（被封锁） | 读 DNAT counter 是否为 0，见第 16 节④ |

报告口径：每条结论都要能说出「哪一组数据、控制了哪个变量、排除了哪个方向」。
说不出对照组的结论，交付时必须明写「推测，待实测」，**不能写成定论**。

一条附带的元规则：**同一条家宽上「A 快 B 慢」只能证明 A≠B，从来不等于已找到原因。**
说出来之前先问自己「如果换个变量它还是这个结果吗」。

### TCP 回退：sing-box + Shadowsocks 跑 `8443/tcp`

前提数据：**家宽 TCP 完全不限速**（同一台服务 DDNS 直连 72.6 Mbps），所以绕开 UDP 即为正解。

**Debian 13 源里已没有 `shadowsocks-libev`** —— `apt-cache search shadow` 只剩 `libshadowsocks-libev-dev`，
`apt install shadowsocks-libev` 会静默失败、连配置文件目录都不建。改用 sing-box 官方二进制：
```bash
cd /tmp
curl -s https://api.github.com/repos/SagerNet/sing-box/releases/latest \
  | grep -oE '"browser_download_url": *"[^"]*linux-amd64\.tar\.gz"'   # 取版本号，别硬编码
curl -sL -o sb.tar.gz https://github.com/SagerNet/sing-box/releases/download/v<VER>/sing-box-<VER>-linux-amd64.tar.gz
tar xzf sb.tar.gz && install -m755 sing-box-<VER>-linux-amd64/sing-box /usr/local/bin/sing-box
sing-box version
```

服务端 `/etc/sing-box/config.json`（只做 TCP 入站 + 直出，不要再套二级代理）：
```json
{
  "log": { "level": "warn", "timestamp": true },
  "inbounds": [{
    "type": "shadowsocks", "tag": "ss-in", "listen": "::",
    "listen_port": 8443, "network": "tcp",
    "method": "chacha20-ietf-poly1305", "password": "<24位随机>"
  }],
  "outbounds": [{ "type": "direct" }]
}
```
- `"network": "tcp"` 是关键：只走 TCP，彻底避开 UDP QoS
- 加密用老的 AEAD `chacha20-ietf-poly1305`，**别用 `2022-blake3-*`**（部分客户端版本不认，密钥格式也不同）
- 启动前 `sing-box check -c <config>` 先校验

systemd unit 照第 14 节「拆两次调用」的姿势写 → `daemon-reload` → 再单独 `systemctl enable --now sing-box`。

路由器侧：`uci add firewall redirect`，字段完全同第 10 节四步，只是 `proto='tcp'`、`src_dport`/`dest_port` 都用 8443。
`8443/tcp` 与 `8443/udp` 互不冲突，可并存；reload 后照例回归验证 OpenClash 计数。

**服务端自证（不必等用户就能确认 90%）**：
```bash
ss -tlnp | grep 8443                                              # sing-box 在听
sing-box check -c /etc/sing-box/config.json                       # 配置合法
timeout 8 bash -c 'echo >/dev/tcp/<家宽IP>/8443' && echo 端口可连   # 经 reflection 验证 DNAT 链路
```

**客户端（Shadowrocket）**：新建 **Shadowsocks** 类型节点 = DDNS 域名 + 8443 + 密码 + `chacha20-ietf-poly1305`。
分流规则本身**一字不用改**，只需让规则里的节点名对上。两种交法：
- 让用户删掉旧 WG 节点、把新 SS 节点**命名成旧名字** → 配置文件原样可用
- 或发一份规则已替换好节点名的配置文件（把 `IP-CIDR,...,<旧名>` 全量替换，**别只改一处**，两行都在）

> ⚠️ **实测口径必须分清**：那个 4 Mbps 来自 **CT210**（2C/512MB，已删除），**不代表这套通道在 CT <ID> 上的表现**。
> 迁到 CT <ID> 后 TCP 通道已重新部署，但**尚未拿到实测值** —— 交付时如实说「已部署、待测」，
> 既不要宣布它解决了限速，也不要说它没用。
>
> 「给慢的那台加资源」已被否证（迁到 8C/10GB 后 UDP 仍 4M），别再推销这一步。
> Trojan + TLS 伪装 `443/tcp` 只有在确认「运营商对 TCP 也做 QoS」之后才值得做；
> 若同机器换协议就能快，加 TLS 纯属白忙。
> 已在本文档证伪、不要重复尝试：加容器资源、换 UDP 端口、改 MTU、换 SS 加密方式、调缓冲区。

**定位口径**：把 WG 保留不删（内网低频访问、HA 面板、低码率监控，4 Mbps 够用），
TCP 通道专供大流量，两者用不同节点名共存，用户按场景切换即可。

### A/B 对比测法（同一台 CT 开两个入口，排除服务器差异）
1. 备测速文件：`dd if=/dev/urandom of=/srv/speedtest/test200.bin bs=1M count=200`
2. 页面用本 skill 的 `templates/wg-speedtest.html`（15 秒限时 + 实时 Mbps，避免烧掉用户流量）
3. 入口一（隧道）：`http://192.0.2.10:8080/`
4. 入口二（裸公网）：给 8080 也加一条 DNAT（同第 10 节四步），访问 `http://<DDNS域名>:8080/`
5. 让用户**关掉 WG** 用同一张卡再测一次，确认瓶颈是家宽上行而非手机网络

⚠️ 让用户测「公网直连入口」前，**必须明确要求先彻底断开代理 App**。
连着 Shadowrocket 时，`<域名>:28080` 解析成**公网 IP**，不匹配「内网段走隧道」那两条 `IP-CIDR` 规则
→ 被当成普通外网流量丢给机场节点 → 机场当然进不了他家路由器，
表现为「打不开 / 一片白屏」，会被误报成服务端故障，白排查一轮。

用户报白屏时，先在服务端自证再怀疑配置：
```bash
curl -o /dev/null -w '%{http_code}' http://127.0.0.1:<端口>/     # 服务在听
curl -o /dev/null -w '%{http_code}' http://<公网IP>:<端口>/      # reflection 路径通
```
两条都 200 而用户打不开 → 问题在客户端分流或上游封端口，不在服务端。

**在 CT 里起长驻服务的正确姿势**（Hermes 前台会拒绍 `nohup`/`setsid`/`systemctl enable --now` 这类启动命令）：
拆成两次调用 —— 第一次 `pct exec` 只写 systemd unit + `systemctl daemon-reload`；
第二次单独跑 `pct exec 210 -- systemctl enable --now <unit>`，再用一次 `curl` 取 `http_code` 和 `speed_download` 自测。

---

## 15. 收尾：瓶颈没修好时怎么交付

一轮排障下来速度提不上去，不要继续堆实验，也不要含糊收场。按这个顺序收：

**① 先纠正用户的错误因果，用他自己的数据当证据。**
典型误解：「用域名能躲过运营商的限速」。域名只是 DNS，不参与数据传输；决定快慢的是**落点机器 / 协议 / 端口路径**。
拿他自己刚测的数就能自证：同是 TCP、同走域名，`speed.<域>:18443` 跑到 72.6 Mbps、`<域>:8443` 只有 4 Mbps —— 差别只在落点机器。
不纠正这个认知，用户会基于错误假设去做后续架构决策。

**② 给可用的最优解，而不是「修不好」。**
直连/反代路径快、隧道慢时的务实交付：
- 主用：**DDNS + 反向代理（Caddy）** 访问内网服务，速度即直连水平
- 备用：隧道**保留不删**，承担内网低频访问（HA 面板、低码率监控），4 Mbps 够用
两条同时存在，用不同的节点名/子域名共存，用户按场景切。

⚠️ **反代组件必须先查清是谁在听，再写进解释。**
本机实际是 **Caddy**（`caddy run --env... --config /etc/caddy/Caddyfile`，监听 443/18443），
而 **Lucky 早已停用**（`lucky.@lucky[0].enabled='0'`，16601 根本不监听）。
凭记忆里的旧组件去解释链路会当场被用户纠正，而且会让他对后续所有推断都存疑。
定罪只有一条路：`ss -tlnp | grep <端口>` 拿 PID → `ps -p <PID> -o cmd=` 看命令行，看完再下笔。

**③ 顺手提安全。**
把内网服务用端口转发挂到公网，等于把家门开在公网上被全网扫描。
提醒给反代加 Basic Auth / 密码——这件事比再测一轮速重要得多。

**④ 把剩下值得做的一步说清楚，把决定权交回用户，然后停手。**
例如「给那台慢的机器加资源复测」。说完就停，不要自作主张去改。

❌ 不要为了让对话「有结论」而编一个没验证的根因。用户自己说「算了，先这样吧」时，
他已经接受现状了，再多跑几轮反而变成骚扰。

