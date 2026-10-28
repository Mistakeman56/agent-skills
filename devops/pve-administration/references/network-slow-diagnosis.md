# 家里网速/卡顿排查（实测有效，2026-10-07 跑通的全套命令）

## 三条入口（全部只读）

```bash
# 路由器 iStoreOS（2222 端口，root，key 已配）
ssh -p 2222 root@192.0.2.10
# PC（4080S，key 已配）
ssh user@100.64.0.1   # 或 192.0.2.10（DHCP 会变）
```

**Pitfall：给远端传带单引号/双引号的命令会炸。**
- shell 命令：把**整条**远端命令 `shlex.quote()`/`shell_quote()` 后再拼进 ssh 参数——整体 quote 过，内部单引号、`docker exec x sh -c '…'` 嵌套都安全；会炸的是**没包 quote 的裸 f-string/repr 拼接**（repr 是 Python 引号不是 shell 引号，出现 `'` 即 `unterminated quoted string`）。
- PowerShell：`powershell -NoProfile -EncodedCommand <base64(UTF-16LE)>`，脚本控制在 ~1.5KB 内（再大会被当成超大 payload 拦掉，返回 `duration=0.02s` 空结果）。
- 多行 cmd 用 `&` 连接；`
` 换行通过 ssh 到 cmd 会整段丢掉。
- Win11 已无 `wmic`（`'wmic' 不是内部或外部命令`）→ 用 PowerShell/CIM。
- SSH 到 Windows 默认 shell 是 cmd，PowerShell 里报错走 CLIXML，注意 grep 掉 `#< CLIXML`。

## 动手前三问（每问都比抓包快，问完再动手）

1. **是不是按钟点爆的？** 整点准时起病、到点自愈 → 先查定时配置：`uci -q get appfilter.time.time`（oaf 封禁时段）、`crontab -l`、Wi-Fi 定时/夜间模式。**定时类故障窗口外复现不了**——白天测通不能证明修好，确认修复必须在窗口内实测（手段见下文 oaf 段）。
2. **是不是挑应用的？** 百度通、名单应用（抖音/B站/小红书/淘宝/京东/闲鱼）死 = 应用层策略不是链路 → 先 `uci show appfilter`（配置面见 `istoreos-app-filter.md`，真凶抓包判据见下文 oaf 段），再查 dnsmasq 广告过滤/家长控制，最后才上抓包。
3. **双点对照**：同一 URL 分别在路由器本机 curl（OUTPUT 路径，不走透明代理，只能证明上游通）和局域网客户端（CT <ID>/手机，转发路径）打——路由器通、客户端挂 → 故障在家内转发/策略层；两边都挂 → 上游/代理。

## 判定顺序（别一上来就猜）

1. **先测链路质量**（PC 上，20 发）：
   `ping -n 20 192.0.2.10` / `203.0.113.1` / `www.bilibili.com` → 看 loss/avg/max。
   正常基线：网关 <1ms 0%丢、203.0.113.1 ~19ms、bilibili CDN ~8ms。
2. **再测 TTFB**（curl，别测整页体积）：
   `curl.exe -o NUL -s -w "code=%{http_code} conn=%{time_connect} ttfb=%{time_starttransfer} total=%{time_total}\n" URL`
   国内正常 0.07–0.15s；经 OpenClash 出境 0.16–0.83s（抖动大属正常）。
3. **再测吞吐**（B站视频最真实）：
   拿 CID：`api.bilibili.com/x/web-interface/view?bvid=BV...` → `data.cid`
   拿播放地址：`api.bilibili.com/x/player/playurl?bvid=&cid=&qn=64&fnval=1`（带 `Referer: https://www.bilibili.com/video/BV...`）
   `curl -e <referer> -o /dev/null -w speed` → 实测 ~2.4MB/s（≈20Mbps，单连接 CDN 限速水平，**不是宽带不够**）。
4. **再测 Chrome 本身**（排除扩展/profile）：
   `"C:\Program Files\Google\Chrome\Application\chrome.exe" --headless=new --user-data-dir=%TEMP%\chtest --dump-dom <url>`，PowerShell `Measure-Command` 计时。
   无头+全新配置加载 B站 = **1.2–1.9s**。无头很快而真人版卡 → 查扩展/渲染，不是网络。
   ⚠️ 直接 robocopy 运行中的 Chrome profile 会**卡死**（默认对锁定文件重试100万次）→ 必须 `/R:0 /W:0` 且排除 Cache/Code Cache/Service Worker。

## 已知结论（2026-10-07 全绿时的基线）

- 小红书：`www.xiaohongshu.com/explore` 5发全200 @0.37–0.45s；`edith.xiaohongshu.com` TLS 握手 0.086s；`sns-webpic.xhscdn.com` 连接正常；图片 URL 实测200/108KB/0.213s。**服务端和家里链路没问题**。
  - `sns-img.xhscdn.com` 这个名字是**不存在的**（AliDNS NXDOMAIN），真实域名是 `sns-webpic.xhscdn.com` / `sns-img-al.xhscdn.com` / `growth-img.xhscdn.com`。
- B站：页面/图片/视频 CDN 全快，Ping 0% 丢包。
- PC：有线 2.5G，无系统代理、无 clash 进程、无代理快捷方式参数；磁盘 C 剩 131GB；Chrome 155，CPU 负载 24%，15 个 chrome 进程 958MB。
- PC 扩展只有 4 个：`ghbmnnjooekpmoecnnnilnnbdlolhkhi`（Google Docs 离线）、`hehggadaopoacecdllhhajmbjkdcmajg`（ChatGPT sidebar）、`kdbmhfkmnlmbkgbabkdealhhbfhlmmon`（SteamDB）、`nmmhkkegccagdldgiimedpiccmgmieda`（Chrome 应用商店支付）。

## 真正查出来的三个隐患（都不是当场的卡，但都属实）

1. **WAN 会重拨**：路由 `up 4 days` 但 `ifstatus wan` 的 `uptime=171482s`（≈47.6h）→ PPPoE 4 天里重拨过一次。
   ⚠️ **别再推断「光猫死机」**：用户明确澄清光猫从未死机过，是他自己主动关过光猫（还优化过散热）。重拨＝用户操作或 ISP 侧，不要提光猫死机。
   光猫 192.0.2.10 ping 通但 HTTP 超时（code=000，桥接下管理页不通）。
2. **IPv6 状态（2026-10-07 核实）**：路由器 IPv6 **是开的**——`network.wan.ipv6='1'`，`dhcp.lan.ra='server'`、`dhcp.lan.dhcpv6='server'`，独立的 **`wan6` 接口**（proto dhcpv6）拿到 PD `2408:822f:20a0:b4d0::/60`，br-lan 上有 `2408:822f:20a0:b4d0::1/64`。
   ⚠️ **看 PD 必须用 `ifstatus wan6`**：`ifstatus wan` 的 `ipv6-prefix` 永远是空的（IPv4/PPP 那个接口），用它判断「没有 PD」是错的。
   当时 PD 的 `preferred/valid` 只剩 **2023s**（≈33 分钟）→ 租约很短，续租失败地址就会整个消失，这是排查「设备时不时没 IPv6」的头号线索。
   路由器 DNS 不回 AAAA（`nslookup www.bilibili.com 192.0.2.10` 只有 A），所以 v4/v6 双栈目前没在拖慢。
3. **DNS 偏慢**：路由器 DNS 对**未缓存**域名 `dig @192.0.2.10 <random>.com` 恒定 **73ms**（OpenClash DNS 管线；fake-ip 模式下连随机域名都返回 NOERROR）。页面一开十几个子域名，缓存未命中时叠起来有感。

## oaf 应用防火墙在时段内对名单应用伪造 RST（抓包实锤；用户有意的防沉迷，不是故障源）

**症状特征（和「挂代理卡」极易混淆）**：LAN 设备（手机/CT <ID>）访问特定应用（抖音/B站/小红书/淘宝/京东/闲鱼）返回 000 / TLS RST，**百度等不在名单的站点全通**，**路由器自己 curl 全通**，换 WiFi/重连无效。**配了时段就只在时段内发作**（本路由 `uci -q get appfilter.time.time` = `00:00-07:00` 全周）——起病钟点对得上窗口就直接查它。

**机制**：OpenAppFilter（`oaf.ko` + `oafd`）`appfilter.global.tcp_rst='1'` 对名单应用注入伪造 RST，**阻断走转发路径**。OpenClash 全量 TCP redirect 时转发路径被抢走、oaf 读不到报文（判据与四个处置选项见 `istoreos-app-filter.md`）；关掉 OpenClash、流量改走转发后，**窗口内**名单应用立刻全黑——「关了 OpenClash 还是黑」的真相是「时段到了 + 流量改道」叠加，与代理残留无关；窗口外关 clash 不触发，白天复现不了。

**定位方法（一击必杀的证据）**：路由器上 `tcpdump -i any -n -v 'tcp port 80 or tcp port 443'` + LAN 侧触发 curl：
- RST 出现在 `br-lan Out`（**ttl=64、id=0**、cksum incorrect），**从不出现在 `pppoe-wan In`**，且 ClientHello 发出后 **<1ms** 返回（RTT 是 9-20ms，物理来不及）→ 本地内核伪造，不是远端/运营商。
- 排除法：`nft list ruleset` 无 reject（fw4 干净）、`iptables -t filter/mangle/raw/nat -S` 全空、`tc filter` 全空 → `lsmod | grep` 看到 **`oaf` 占用 `nf_reject_ipv4`** → 实锤。

**隔离验证（临时手段，不是修复——这功能用户要保留）**：
```sh
uci export appfilter > /root/appfilter.bak.$(date +%Y%m%d%H%M%S)  # 先备份
/etc/init.d/appfilter stop    # 停 oafd
rmmod oaf                     # 必须卸载！规则活在内核模块里，只停服务不生效
```
停后窗口内名单应用立刻恢复 = 真凶确认，**随即 `/etc/init.d/appfilter start` 恢复**（自动 `modprobe oaf`；查活 `grep oaf /proc/modules` + `ps w | grep oafd`）。
**验证分两半**：窗口外 curl 名单应用通，只证明不误伤白天；**窗口内实测**才证明拦截在工作（`match_time=1` + 对照站通/目标站失败，三件套见 `istoreos-app-filter.md`）。白天排障等不到窗口，就用一次性 `cronjob_manage`（`schedule` 传窗口内 ISO 时间戳）把验证放过去自动跑——那是验证手段，不是修复方案。
**名单+时段是 deliberately by the user配置、明确要求保留的防沉迷**：排查其它故障时窗口内名单应用黑 = 设计行为；停用或改名单前先 `uci export appfilter` 备份并问一句，别当故障拆掉。

**抓包方法论 Pitfall（这次踩过的）**：
- busybox **没有 `timeout` 命令** → `tcpdump ... & TP=$!; sleep 42; kill $TP`。
- `tcpdump -v` 是**双行制**：接口标签在上一行，RST 内容行不带时间/接口 → 查 RST 归属必须 `grep -B1 'Flags \[R\]'`。
- DNS 每次轮询换 IP → 按具体 IP 设 filter 会抓空，用 `tcp port 80 or tcp port 443` 宽过滤。
- hermes terminal 会回收 `&` 后台子进程 → 前台命令里别用 `&`：短任务 `setsid nohup`，长任务（等 264G 校验、轮询状态）交给外层 terminal `background=true` 独立会话，完事再取结果。
- 反证思路：路由器(OUTPUT 路径)全通 + 转发设备全挂 → 差异就在 FORWARD 链的处理者。

## 间歇性掉线/整机打嗝：哨兵先行法

单发 20 发 ping 永远测不出「一会儿断一下」——**报『一直掉线/间歇卡』时，第一步是取证动作（布哨兵或读已有病历），不是翻配置**：家宽**整体**间歇断先读 `home-network-outage-forensics.md` 的 netmon 病历；1–7 秒瞬时事件的判别与 1 秒粒度采样见 `game-stutter-latency-sampling.md`；本节补的是**单机三路哨兵的布防、读数与丢包模式判读**（PC 打嗝类投诉最常见）。用户在急症中时，布完哨兵先回一句现状（已布防、目前 N 分钟全绿/已捕到断点）再继续查，别连打十轮工具不回话。

**布防**（三路各一路：网关/公网/具体业务目标，逐秒写文件；启动形态见 pc-remote-ops 铁律 6——Start-Process 不带 `-Wait` 跨 ssh 会话存活）：
```bash
powershell -NoProfile -Command "Start-Process cmd -ArgumentList '/c','ping -t 192.0.2.10 > C:\Users\<u>\pinglogs\gw.txt' -WindowStyle Hidden"
# 同样再布 203.0.113.1 与业务目标两路
```

**读数（编码安全，GBK 细节见 pc-remote-ops 铁律 11）**：`loss = $(wc -l < f) - $(grep -c TTL= f) - 2`（-2 = 空行 + `正在 Ping` 头行）；1 pps ⇒ **行号 N ≈ 文件创建时刻 + N 秒**，把丢包行号换算成时刻去和事件日志对表：`Get-EventLog -LogName System/Application -After <t1> -Before <t2>`。

**三层判读表**（先看丢包模式再决定往哪查）：

| 丢包模式 | 结论 | 下一步 |
|---|---|---|
| 三路**同时**丢，**含网关** | 本机整机停顿/内核打嗝，与外网无关 | 查 PC 侧同时段事件日志；**零系统事件 + 三路同断 = 纯软件层停顿**（无网卡重协商/硬盘报错/驱动重置），对象是杀软/激活服务/第三方工具周期任务，不是硬件 |
| 只丢公网+业务目标，网关稳 | 外线/PPPoE/上游 | 路由器侧：`ifstatus wan` uptime、重拨记录 |
| 只丢单一业务目标 | 到该目标的路由/该服务本身 | 对该目标持续打点 |
| 只丢网关 | 内网链路（线/口/AP） | 交换机/AP/网线 |

**抓真实业务端点**（游戏/实时流这类目标 IP 只有会话时才知道）：`Get-NetUDPEndpoint` 按业务进程 PID 过滤取 `RemoteAddress`，对它单独布一路哨兵；进程 `.Path` 为空 = 提权进程读不到，别死磕路径，改用「进程存在 + UDP 端点是否存在」判业务状态（无远端端点 = 没连上会话）。断点时刻的伴随事件只当线索，不当定罪。

## 其他有用的只读信息源

```bash
ssh -p2222 root@192.0.2.10 "uptime; cat /proc/loadavg; ifstatus wan; cat /proc/net/dev"
# 看 OpenClash 关键规则（QUIC 处理、DNS 劫持）
nft list ruleset | grep -n -E 'udp|tproxy|redir|443' | head -60
# 关键规则实测存在：
#   udp dport 443 ip daddr != @china_ip_route reject ... "OpenClash QUIC REJECT"（境外 QUIC 被 ICMP 拒，强制回退 TCP；国内 QUIC 放行）
#   meta l4proto { tcp, udp } th dport 53 redirect to :53  "OpenClash DNS Hijack"（250956 packets）
```

**绝对不能动**：fw4/nftables 规则、OpenClash 配置开关。以上全部只读。
