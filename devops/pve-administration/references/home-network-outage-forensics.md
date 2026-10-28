# 家网「卡 / 断 / 慢」投诉的取证顺序

## 铁律：先读病历，再看配置

用户报「网卡 / 断了 / 下载跑不满」时，**第一步不是 ssh 进路由器翻配置**，而是读常驻监控的历史事件。

配置层的可疑点（DNS 干等、代理没生效、假 IP 失效）绝大多数是**放大器**，而「网本身会间歇性掉」才是根因 —— 后者**只存在于历史日志里**。

跳过这一步的代价是确定的：一晚上修一个冒一个，每个「真凶」单看都成立，但用户仍然认为根本问题没被解决。**修放大器之前，先确定底层那层稳不稳。**

## 病历在哪

```
/etc/netmon/events.log           # 事件流水 —— 先看这个
/etc/netmon/netmon.log           # 每 2 分钟全量采样
/etc/netmon/crash_YYYYMMDD.log   # 事件发生当时的 syslog 快照 + pppoe-wan 地址
/etc/netmon/{state,onu_state}    # 上次采样状态
crontab -l                       # netmon.sh 每 2 分钟 / devmon.sh 每 5 分钟
```

采样行格式（一条 = 一个时刻）：

```
<时间> uptime=<WAN已连秒数>s ip=<公网IP> loss=<丢包%> avg=<延迟ms> bw=<MB/s> load=<负载> ct=<conntrack> onu=<yes/no> [EVENT:<事件>]
```

`uptime` 是**上一次 PPPoE 连接已存活的秒数**，重播事件里的 `prev=` 就是它 —— 这是判断线路周期的关键字段。

## 事件签名 → 结论速查

| 事件 | 判据 | 结论 |
|---|---|---|
| `ONU_LOST` | 光猫管理口不可达 | **光猫自己死了**。全屋断网；重启路由器无效、**重启光猫才生效**。硬件/电源/散热问题，与软路由、代理、DNS 全无关 |
| `PPPoE_RECONNECT prev≈691200s` | 上次存活差几十秒满 691200s | 运营商 **PPPoE 会话上限（8 天）强制踢线**，正常现象不可消除 |
| `PPPoE_RECONNECT` 且 `prev` 远小于 691200s、`ip=;` | 没活满周期就没了 | 线路/光猫侧异常，继续查 ONU 与光衰 |
| `PACKET_LOSS 33/66/100%` | ping 目标丢包 | 100% 且**同时没有** PPPoE_RECONNECT = 链路在但对端不通（纯断网，不触发重播） |
| `BANDWIDTH_DROP <1MB/s` | 采样下载速率掉底 | 间歇性吞吐塌陷 —— 用户体感的「下载跑不满」多出自这里，不是服务器限速 |
| `HIGH_LATENCY` | 平均延迟超阈值 | 线路拥塞或劣化 |

**间隔算术用工具算，别脑算**：`prev/86400` 看是否为整数天；`691200s = 8 天`；`345600s = 4 天`。差几十秒满整数天的重播 = 运营商定时踢线，不是故障。

## 先排除「是不是软路由的锅」

- `load` 长期 < 0.5，且 `ct` 远低于 `nf_conntrack_max` → 路由器完全不是瓶颈
- 各网口 `rx_errors`/`tx_errors` 全 0，只有少量 `rx_dropped`/`rx_fifo_errors` → 正常（无硬件卸载时的缓冲区溢出）
- **要证明「重装/换软路由没用」**：把 `ONU_LOST` 与运营商 8 天踢线两条列出来 —— 硬件与 ISP 侧的行为，换任何路由器都不变。用户动念「从 0 重装」时，这是唯一有说服力的论证方式

## ★ 双面哨兵：一次断线把锅劈成三份（用户坚持「肯定是路由器的锅」时用数据终结争论）

单侧 ping 分不清「PC 整机卡」「PC↔路由器这段断」「路由器上游断」—— **两侧同时布，断线一次出结论**：

```sh
# PC 侧（Git Bash；Start-Process 脱离 ssh 会话存活，见 game-stutter §2）
powershell -NoProfile -Command "Start-Process cmd -ArgumentList '/c','ping -t 192.0.2.10 > C:\Users\<PASSWORD>\sent\gw.txt' -WindowStyle Hidden"
# 同法再布「公网IP」「运营商游戏节点」两路；三路同时丢（含网关）才是整机/本地段事件
# 坑: bash 脚本里嵌 PS 载荷必须用 bash 单引号包 (-Command '... $_ ...')，否则 bash 先展开 $_，PS 报莫名其妙的 CommandNotFoundException

# 路由器侧（busybox sh）：printf 写文件 → 独立 ssh 起进程。别在 ssh 单命令里内嵌 heredoc，引号会被本地 shell 吃掉（exit 255）
printf '%s\n' 'while true; do ts=$(date +%H:%M:%S); ping -c 1 -W 2 <PC-IP> >/dev/null 2>&1 && lan=OK || lan=FAIL; ping -c 1 -W 2 203.0.113.1 >/dev/null 2>&1 && wan=OK || wan=FAIL; echo "$ts LAN=$lan WAN=$wan" >> /tmp/rtsent.log; sleep 1; done' > /tmp/rtsent.sh
sh -n /tmp/rtsent.sh || exit 1
kill $(ps | grep '[r]tsent.sh' | awk '{print $1}') 2>/dev/null
nohup sh /tmp/rtsent.sh >/dev/null 2>&1 &   # tail -3 确认起跑再走
```

| 断线瞬间四方表现 | 归因 |
|---|---|
| PC 三路全断（含网关）+ 路由器哨兵 LAN=FAIL | PC↔路由器段（网卡/网线/AP 上联）或 PC 整机冻结 —— 查 PC 系统事件；日志全空 = 纯软件层打嗝，不是硬件 |
| PC 三路全断 + LAN=OK WAN=FAIL | 路由器上游 / PPPoE → 转本文件「病历在哪」 |
| 只有到游戏或单一目标丢，网关与路由器哨兵全 OK | **外面那条路的事**，家里配置全清白；用户仍怪路由器时，此表 + 时间线即答复 |
| 路由器哨兵自身停摆/超时 | 路由器整机卡顿（dmesg 查 soft lockup、conntrack 刷屏） |

## ★ 候选原因先过「以前不卡」这条时间线

症状是新出现的 → 病因必须是**近几天变过的**；没动过的设置默认无罪，除非它依赖对端协商。用户拿「以前一直好好的」反驳时，别辩护，按下面顺序重新取证：

- **协商型设置先查两端**：EEE/Green Ethernet 需两端都通告才生效 —— 路由器 `ethtool --show-eee <if>` 显示 disabled 时，单关 PC 侧 `*EEE` 是无效功，别提这个方案
- **「有种子在传」≠「打满上行」**：用 Transmission `session-get` 的 `uploadSpeed`、torrent `uploadedEver > 0` 说话；0 字节空转的种子排除出局
- **`expectation table full` ≠ 连接表满**：前者是 helper/P2P 打洞条目表；主表水位看 `sysctl net.netfilter.nf_conntrack_count` 对 `nf_conntrack_max`（占用万分之几 = 无关）
- 对齐顺序：**症状开始时刻 → 近 48h 变更清单（配置/设备/流量形态）→ 日志最早异常时刻**，三者对上才下结论；用户声称「你探测前就卡」时，先用日志（游戏黑匣子/哨兵/系统事件）证明或证伪这个前提，再谈原因

## ★ 先修可观测性，否则永远只能猜

症状：`logread` 里几乎全是 `dnsmasq: query[A]/reply/forwarded`（30 台设备 + fake-ip 模式下每秒几十条），而 `system.@system[0].log_size` 默认只有 **128（KB）** → 环形缓冲几秒被冲掉，**故障发生完就没记录了，别的子系统日志（pppoe/netifd/kernel）全被挤出去**。

```sh
cp /etc/config/dhcp /etc/config/system /root/net-bak-$(date +%Y%m%d-%H%M%S)/
uci set dhcp.@dnsmasq[0].logqueries='0'    # 关掉逐条查询日志
uci set system.@system[0].log_size='1024'   # 缓冲 128KB → 1MB
uci commit dhcp; uci commit system
/etc/init.d/dnsmasq restart                 # DNS 闪断 <1 秒，可接受
```

验证（必须真验，不能只看 UCI 值）：

```sh
# 重启时刻之后新增的 query[ 条数必须为 0
logread | grep 'query\[' | awk '$4 > "HH:MM:SS"' | grep -c 'query\['
# 顺便复检 fake-ip 行为没被 dnsmasq 重启破坏
nslookup www.bilibili.com 127.0.0.1 | grep Address    # 期望真 IP
nslookup www.google.com 127.0.0.1 | grep Address      # 期望 198.18.x.x
nslookup <自建域名> 127.0.0.1 | grep Address           # 期望真 IP（白名单）
```

`logd` 缓冲在 RAM，**重启即失** —— 持久病历只有 netmon 写到 `/etc/netmon/` 的那几个文件，别指望 `logread` 跨重启。

## ★ 测量陷阱：先确认你的测法真的走了那条路

「所有测速都正常」和「这条路径是死的」都是最容易出错的两个结论。**在把任何一个当成事实去改配置之前，先问：我这个测法实际经过了哪条路径？**

| 陷阱 | 机制 | 正确做法 |
|---|---|---|
| 内网测速仪（Speedtest-X 等） | 跑在路由器上的 Docker 容器里，结果里的 `192.0.2.10` 就是容器网段 → **只测「设备↔路由器」这一段**，既没碰出口也没经过 OpenClash 内核 | 别拿它证明「外网好 / 代理没问题」。测出口要**从 LAN 侧设备**测，或按下面②经代理端口测 |
| 容器里的浏览器测速页（NAS/路由器上的 Firefox 或测速网站） | ① bridge NAT/conntrack 一段 ② 浏览器要给 GB 级流量做 TLS 加密+JS 计算+渲染，弱 CPU 必被卡住 ③ 页面 JS 定时器粒度 ≈16–20ms → **抖动恒等于一个帧间隔** | 别用它判定链路延迟/抖动，更别据此怀疑交换机。归因用 A/B ping（`lan-switch-discovery-and-latency-ab.md`），干净的内网吞吐/抖动用 iPerf3；**上行恰好 ≈1G** 时先怀疑测速服务器上行 |
| 从路由器本机 `curl` 访问被墙站点 | 路由器自身流量**不走透明代理**（TPROXY/redirect 只作用于 FORWARD 链）→ 必然超时，**伪造出「代理挂了」的假警报** | 测代理链路：`curl -x http://127.0.0.1:7890 https://www.google.com/generate_204`（期望 204）；刻意走直连时写 `--noproxy '*'` 表明意图 |
| `/connections` 快照 | 一次瞬时快照，抓不到短连接多的 App，也抓不到收发完就消失的 UDP 流 | **「快照里没有」推不出「这条路是死的」**。看 `nft list ruleset` 规则的 **counter packets 累计值** |
| 控制器/面板上的客户端数据 | AC 无线拓扑页有自己的 `Last Updated` 时间戳，客户端 RSSI / 协商速率可能是几小时前的旧值 | 别拿面板数字判无线故障。让用户在自己设备上跑一次测速（延迟 + 抖动 + 吞吐）比面板可信 |
| `nft get element ... \| grep <ip>` | `nft get element inet fw4 china_ip_route '{ 203.0.113.1 }'` 回显的是**包含该 IP 的网段**（如 `1.2.0.0/16`），不是该 IP 字面量 | 回显里出现网段 = **命中**。grep 字面 IP 会得到完全相反的结论 |

**一键只读取证**：`scripts/net-layer-probe.sh`（scp 到路由器执行）—— 已把「①直连 / ②经代理」分开测、并把 nft 累计 counter 一起打出来，就是为避免上面这几个坑。

**uci 改了 ≠ 生效了**：`uci set/commit` 只写配置，`enable_udp_proxy` / `disable_udp_quic` 这类开关由 init.d + 防火墙脚本在 **reload 时**才落地（没有可单独跑的脚本）。所以「已提交未 reload」是一个**哑弹**：当下看起来没变，某次重启/重载会突然按它运行。**前提一旦被推翻，必须把已 commit 的改动显式改回去**，不能靠「反正没 reload」放着。

**被证伪的假设要落盘**：同一类症状会被反复重新假设。把「已排除项 + 排除依据」写进本文件或对应 reference，下一轮才不用重走（示例见 `references/openclash-douyin-tiktok-ruleset.md` 末尾的证伪表）。

- **用户说「我们以前一直有 / 一直在用 X」就先按事实处理**：当前配置里没有 ≠ 从没有过。下否定结论前先找物证 —— 脚本里的注释与逻辑（例如 DDNS 脚本写着「把 AAAA 指向本机 IPv6」）、DNS 记录残留、被注释掉的配置行，都证明它工作过。拿现状否定历史会推出整套错误建议（包括「要不要恢复这项能力」这种决策）。

## 面向用户的报告顺序（用户明确在意这个）

1. **病历**：带日期的原始事件 + 间隔算术，不做推测性结论
2. **分层**：哪些是根因（硬件 / 运营商），哪些只是放大器（DNS / 代理 / 假 IP）
3. **明确说清哪些问题换设备/重装也解决不了** —— 直接掐掉「从 0 重装」的念头
4. 分清「免费可做」与「需要他拍板（物理 / 光猫 / 运营商）」的动作，不要一次抛一堆选项

## 光猫间歇死机的候选处置（**未实测，动手前须征得同意**）

`ONU_LOST` 是硬件侧行为，配置改不动，方向只有两个：

- **报修换光猫**：拿 netmon 的 `ONU_LOST` 记录当证据，比口头「老是掉线」有力得多
- **自动痊愈**：netmon 检测到 `ONU_LOST` → 触发光猫断电重上电（现成的智能插座即可），或先试光猫管理口能否远程重启。**这会碰物理/光猫，必须用户点头**
- **运营商 8 天踢线**：无法消除，只能把它挪到低峰时段主动重播（netmon 已在记 `uptime`，判据现成）。改 WAN 行为有风险，须先备份 + 用户同意
