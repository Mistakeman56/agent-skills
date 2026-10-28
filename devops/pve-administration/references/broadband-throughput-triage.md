# 宽带 / 链路吞吐排查（协商对了但跑不满）

触发：用户说「家里是 2000M，为什么下载只有 100 多兆 / Steam 跑不满」，并强调「电脑到路由器的电路没问题，是链路」。

先把两个词对齐（照用户的说法）：

- **电路** = 物理连通性：网线线序、carrier、operstate
- **链路** = 协商速率：speed / duplex
- 但 **协商对了 ≠ 跑得满** —— 还要看这一跳的实际吞吐、CPU/软中断、offload 是否真的接上、以及流量有没有被用户态代理转发。

## 按顺序排查（每步排除一层，别跳步）

### 1. 终端网卡协商速率

Windows 经 SSH（多行 PS 一律 `powershell -EncodedCommand <base64(UTF-16LE)>`）：

```powershell
Get-NetAdapter | Where-Object {$_.Status -eq "Up"} |
  Select-Object Name,InterfaceDescription,LinkSpeed,ReceiveLinkSpeed,TransmitLinkSpeed
```

输出里中文网卡名会乱码，**用 `InterfaceDescription` / MAC 认设备**。拿到 `2.5 Gbps` / `1 Gbps` / `100 Mbps` 就能立刻锁定或排除这一段。

### 2. 路由器每个口的协商速率

不要只看「能通」，要看每一跳协商到哪一档：

```sh
for i in 0 1 2 3 4 5; do p=/sys/class/net/eth$i; [ -d "$p" ] && \
  echo "eth$i: $(cat $p/operstate) carrier=$(cat $p/carrier) $(cat $p/speed)Mb/s $(cat $p/duplex)"; done
cat /sys/class/net/pppoe-wan/mtu          # PPPoE 正常 1492
```

配合桥成员判断哪个口朝哪边走：`ls /sys/class/net/br-lan/brif/`（或 `brctl show br-lan`）。**无管理交换机看不到端口状态**，只能靠两端协商值推断它有没有降档；这类交换机过热会协商降档且是历史复发问题，先断电重启再谈别的。

### 3. 实测吞吐（关键：分跳同时采样）

对 `pppoe-wan` 和各个 `eth*` **同时**按 2 秒粒度取 `/proc/net/dev` 差值换算 Mbps —— 分跳对比才能定位损耗发生在哪一跳（本次就是这样确认「PC 收到的 ≈ WAN 进来的」，瓶颈不在 LAN）。直接跑 `scripts/wan-throughput-sample.sh`，不要内联手写。

### 4. CPU / 软中断

```sh
top -bn1 | grep -E "^%?Cpu|^CPU:"
grep -E "eth[0-9]|pppoe" /proc/interrupts
```

**单次快照只能当参考**：本次采到 92-95% idle，但那只是一个瞬间；要判定 CPU 是否瓶颈必须在负载持续期间连续采样，并分清 `usr/sys/sirq`。中断分布看单个 CPU 是否被打满（多队列网卡本来就会把某个队列钉在一核上）。

### 5. offload 是否真的接上（模块加载 ≠ 生效）

```sh
lsmod | grep -i offload
nft list ruleset | grep -A5 flowtable        # 空 = software flow offload 没配
uci show firewall | grep -iE "offload|fullcone"
```

本次环境即 `nf_flow_offload` 已加载而 flowtable 为空 —— 这类配置缺口要在怀疑 CPU 之前先查，否则会在错误的方向上加硬件。

### 6. 路由器自身有没有限速器（SQM / cake）

`piece_of_cake` 这类 SQM 会在 `pppoe-wan` 上挂 root qdisc，把整口整形成配置的带宽。先看它是否在跑、限的是哪个方向：

```sh
tc qdisc show dev pppoe-wan        # 例：qdisc cake 800a: root bandwidth 90Mbit ...
tc -s qdisc show dev pppoe-wan     # overlimits 数字很大 = 一直在削流量
cat /etc/config/sqm 2>/dev/null    # interface / download / upload / script / linklayer
```

**别靠推理判定它是不是元凶，做 A/B**：备份 `/etc/config/sqm` → 先测速 → `/etc/init.d/sqm stop` → 再测同样几次取最好值 → 对比。本次 303.9 vs 294.8 Mbps（0.97 倍）证明 SQM 与下载无关（它只整形发送方向），方向因此从「路由器限速」扳回「对端」。

★ **cake 只管发送方向**：`bandwidth 90Mbit` 作用在 TX（上行），除非配了 IFB 才碰下行。看到这个数字先确认作用方向，不要当场当成全家带宽上限。停 SQM 前记得它多为开机自启，重启就回来；`stop` 后 `tc qdisc` 应变成 `fq_codel`。

### 7. 带宽到底给够没有：单连接 vs 并发对照

这是把「链路/带宽不足」和「对端/单流受限」分开的决定性实验，**必须做**：

```sh
# 同一 URL：先单流，再 8 并发，各取最好值
for i in 1 2 3 4 5 6 7 8; do ( curl -s -o /dev/null -w '%{speed_download}' -m 10 --noproxy '*' "$URL" > /tmp/sp$i & ); done; wait
```

- 单流上不去、并发能拉满 → **带宽没问题**，问题在对端限速或单连接特性（本次单流 306M vs 8 并发 1534M / 1786M ≈ 套餐值）。这一条能把前面所有「链路瓶颈」的猜测一次性证伪。
- **换两个以上不同源的 CDN 各测一轮**，否则会把「某个镜像慢」当成带宽结论（本次阿里源 8 并发只有 24.5M，腾讯源 1786M）。
- 路由器上并发测速会被它自己的 CPU 吃掉一部分 → **结论以终端侧（PC）实测为准**；PC 跑并发时若前台还有别的下载在进行，两边数字一起看，别互相误判成限速。

### 8. 应用自己怎么说（比外部测速更接近真相）

下载慢但带宽充足时，读应用自己的日志与配置，而不是继续猜网络：

- **Steam 日志**：`<SteamPath>/logs/content_log.txt` 里的 `stats: (CDN, n) <host>: <bytes>, <sec> (X Mbps)` **直接给出每条 CDN 的实际速率**——若几条 CDN 各只给 70M，合计就是用户看到的值，结论即「对端只喂这么多」，并可据此给动作。
- **Steam 配置**：`<SteamPath>/config/config.vdf` → `CellIDServerOverride`（把下载区钉死在某个 CellID，常见于加速器写入）、`DownloadThrottleKbps`（0 = 自身没限速）、`RecentDownloadRate`。
- **连接数**：`Get-NetTCPConnection -State Established` 按进程名聚合，看应用连了几条（曾见 Steam 同时 73 条连接却只有 143M → 每条都被对端压着）。
- 结论必须落成可执行动作：换下载区域 / 清掉被写死的 CellID / 关掉加速器隧道。

### 9. 用户态代理 / 游戏加速器

除 Clash 一类代理，**游戏加速器（如网易 UU，进程名 `uu*`）也会接管 Steam 等应用的下载流量并限速**：

```powershell
Get-Process | Where-Object { $_.ProcessName -match '(?i)clash|v2ray|xray|sing-box|uu|accelerator|proxy' } |
  Select-Object ProcessName, Id, Path
Get-NetAdapter | Select-Object Name, InterfaceDescription, Status   # TAP/TUN 虚拟网卡 = 存在隧道
```

顺带查系统代理开关（`HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings` 的 `ProxyEnable` / `ProxyServer` / `AutoConfigURL`）与环境变量里的 `*proxy*`。

国内直连流量也可能被 Clash 内核接管（`DIRECT` 不等于「不经过 Clash」）→ 见 `openclash-fakeip-throughput-penalty.md`，那里的确诊方法（路由器自身 curl 国内站点的速率对比 + 关 Clash 对照）可直接复用。**停加速器/代理做对照前先问用户是否正在用**（可能正给游戏加速），或只停很短时间再恢复。

### 10. 以上全干净，才轮到上游

光猫 PON 口能力 / 运营商实际下发 / 对端 CDN 限速。到这一步给结论要标明「已排除 LAN 与路由器自身」，别把上游问题说成内网问题。用户说「桥接猫不管事」时照他的判断跳过光猫管理页（桥接模式下其 Web 也常常打不开），直接查 PPPoE 会话与上游。

## 坑

- **先确认负载还在跑**：数字一路往下掉（700→200→120）时，先查「下载/传输是不是已经结束或换档了」。把自然收尾读成「被限速」是最容易犯的误判。
- **协商速率不是交付带宽**：WAN 口 2500Mb/s 只说明这一跳的链路能力；PPPoE 开销 + 上游限速 + 对端限速都会让它低于套餐值。
- **单连接速率 ≠ 带宽**：单个 curl / 单条 TCP 只跑出 300M 不代表链路只有 300M（TCP 窗口、时延、对端限速都会压住单流）；小文件更是被握手时间主导。判定带宽必须**并发 N 条对照**，结论要有持续采样支撑。同一原则见 `openclash-fakeip-throughput-penalty.md` 的「排障误区」。
- **Windows 远端传多行脚本时 `-EncodedCommand` 有命令行长度上限**：超长会**静默无输出**（看不出报错）。改用分块 base64：`cmd /c echo <约400字符块>>>%TEMP%\x.b64` 逐块追加 → `certutil -decode %TEMP%\x.b64 %TEMP%\x.ps1` → `powershell -NoProfile -ExecutionPolicy Bypass -File`。写字面中文的 .ps1 要 UTF-8 BOM。PowerShell 回显中文会因代码页乱码，认数据即可。
- **路由器没有 python3**（iStoreOS）：脚本一律纯 sh + awk，浮点换算在路由器上就做完并把 Mbps 打印出来。
- **不要在远端内联长命令**：引号/`$`/括号嵌套会静默把命令拼坏（本次先后出现 `NameError: name 'sp' is not defined`、`hostname contains invalid characters`）。一律本地 `write_file` + `scp` 传脚本再 `sh` 执行。
- 采样窗口要覆盖用户抱怨的时刻：用户说「正在下载」不代表它还在下载，先扫一眼实时吞吐再决定要不要让他保持负载。
