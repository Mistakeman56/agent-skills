---
name: speedtest-triage
description: 'Use when 测速异常(测速软件/裸下载都测不出宽带)——四层定性：劫持/GeoIP/附属/出口限速。'
---

# 家用宽带测速异常排查（四层定性法）

> 场景：软路由环境下 fastnet(:3200)、Ookla `speedtest` CLI、网页测速均测不出标称带宽（如 2000M 只测出几十 M）。多为多因素叠加，**逐层排除，不一上来改配置**。

## 分层诊断（按序执行）

### 层1：流量劫持（fake-ip / 代理卷入）——可修
测速域名在 fake-ip 模式下拿 198.18.x 假 IP → 被卷进代理 → 测的是节点带宽。
- 判据：`nslookup <测速域名> 127.0.0.1` 返回 198.18.x = 被劫；Ookla JSON 的 `externalIp` 若=真实公网 IP 则劫持已解（**修好后慢≠还在走代理，别被用户判断带偏**）。
- 修法：`/etc/openclash/custom/openclash_custom_fake_filter.list` 加 `+.域名` 白名单 + `openclash_custom_rules.list` 加 `DOMAIN-SUFFIX,<域名>,DIRECT` → `clash -t` 校验 → `/etc/init.d/openclash restart`。
- 高频劫持面（测速全家桶）：`ooklaserver.net`（Ookla 服务器长尾父域，FastNet 列表里国内服务器全是 `*.prod.hosts.ooklaserver.net`）、`jsinfo.net`、`shunicomtest.com`、`dukekunshan.edu.cn`、`test-ipv6.com`、STUN 服务器（如 `stun1.ddnsto.com`）。**白名单写父域 `+.ooklaserver.net` 而非逐个子域——长尾拼接域（x.y.com.prod.hosts.ooklaserver.net）只匹配后缀父域才全覆盖**。
- **TCP 与 UDP 出口不一致 = 全量透明代理的判据**：容器/内网主机上 `curl -4 https://ip.sb` 返回的常是**机场节点 IP**（境外段），
  而 UDP STUN（`tailscale netcheck` 的 `IPv4:` 行）才是真实家宽 IP —— 因为 TPROXY 只接管 TCP，UDP 直出。
  **任何基于 TCP 的测速/上传下载结论都可能测的是节点带宽**：典型表现是 `speedtest-cli --json` 自动选到境外服务器、
  `ping` 报出几十万毫秒、上行看着正常而下行只有几 Mbps。要测真实家宽必须走国内服务器/国内镜像，或换 UDP 通道；
  **报数字前先确认出口归属**，别把节点带宽当成家宽带宽交给用户。
  **解法是换测量位置，不是绕代理**：`curl -4 https://ip.sb` 出口是境外节点时，容器/内网主机上的
  一切吞吐结论全部作废——TPROXY 在内核层拦截，`--noproxy '*'` 和清 `LOCAL_PROXY` 环境变量都没用。
  直接 SSH 到路由器（PPPoE 端点，自身流量不被劫）跑真实带宽验证，那才是家宽出口。

### 层2：GeoIP 误判（本地无解，只定性不修）
Ookla/speedtest.net 服务端 GeoIP 库把家庭 IP 定位到错误城市（实测大连联通被定位首尔 306km）→ 自动选服永远首选境外服务器 → 跨境晚高峰 45~180M + 高抖动。
- 判据：选服列表/距离异常（如"最近"服务器在境外）；早先能测满速=当时定位正常选中了国内服务器。
- 处置：明确告知用户「测速工具的服务端数据坏了，不是你家网络/路由器坏了」，**别承诺修复、别继续挖配置**。国内 Ookla 服务器稀少且多为大学小水管（昆山杜克 307 重定向、CLI 报 socket 错但 curl 能连、FastNet 后端无视 serverId 强制回落首尔）——均属服务器侧，不深挖。

### 层3：附属症状甄别
- **「对称 NAT」误报**：PPPoE 直持公网 IP（`ip addr show pppoe-wan` 直接看到公网 IP）时根本没有 NAT，STUN 报"对称型"=STUN 服务器本身不回包的垃圾结论，不是网络问题。
- **IPv6 检测失败**：先 `nslookup <检测域名>` 看 DNS 与 `curl -6 ifconfig.co` 看本机 v6 出口——两者正常则是检测程序自身 bug。注意不动 `ipv6_enable` 红线。

### 层4：出口限速（本地全干净、速度恒定卡在一个数）

先跑「真实带宽验证」；若**跨源多线程总吞吐仍恒定在同一数值**（实测：单线程 42M、8 线程跨 4 源 44M、
16 线程反而 32M —— 加线程、换源都不涨），用下面四条定性。**先排本地整形再谈运营商**：
跳过第 0 条就把结论推给运营商，一旦用户自己发现 SQM 有 90M 限速值，整轮可信度归零。

0. **本地整形（SQM/cake/tc）——最先查，也最容易误判**：
   `tc qdisc show dev pppoe-wan`（找 `cake … bandwidth XMbit`）、`uci show sqm`
   （看 `enabled`/`interface`/`download`/`upload`）。**看到限速值不等于它是瓶颈**，按三条判：
   `download='0'` **且下载侧确实没有重定向** ⇒ SQM/cake 只挂 egress，**下行完全不受影响**；
   `upload` 上限高于实测上行 ⇒ 从未触发，同样无罪。三条都不指向 SQM 才往下查。
   **判「下载侧没有重定向」必须用对探针**：SQM 的 ingress 中间设备是独立 netdev
   （`ifb4pppoe-wan`），不是 qdisc —— `tc qdisc show | grep -c ifb` **永远返回 0**，
   拿它当证据会交出假排除，而这是整轮最有说服力的那条「排除」。三条正确探针：
   `ip -br link show | grep -i ifb`（设备在不在、是否 DOWN）、
   `tc filter show dev pppoe-wan ingress`（输出空=确实无 ingress 重定向）、
   `cat /sys/class/net/ifb4pppoe-wan/statistics/rx_bytes` 隔 3 秒两次（不增长=没在搬下载流量）。
   `tc qdisc show dev pppoe-wan` 里那条 cake 是 **egress**，只作用于上传方向。
   `logread | grep -i sqm` 能直接读到 `Starting SQM script … in: 0 Kbps, out: 90000 Kbps` 与
   `hotplug: add … ifb4pppoe-wan` —— **出现 ifb 不等于它生效**，以 rx_bytes 判定。
   顺手核对配置年代（`ls -l /etc/rc.d/ | grep sqm` 的自启链接日期）——长期存在的整形不该被说成
   「最近有人动了它」，也不该反过来当成运营商限速的证据。

1. **WAN 网卡实测速率对账（最硬的一条）**：下载进行中读
   `cat /sys/class/net/pppoe-wan/statistics/rx_bytes` 前后差 ÷ 间隔。若 24 线程压测时 WAN 实收
   只有 ~30-45Mbps，说明包根本没到路由器，是上游没给发下来。
2. **本地链路自证干净**：`ethtool eth0` = 2500Mb/s Full + `Link detected: yes`；`rx_errors=0`；
   5 秒内 `rx_dropped` 不增；`/proc/net/snmp` 的 `Tcp: RetransSegs` 10 秒增量占总段数 <1%
   （≈0.2% 属正常）；cake `pk_delay` µs 级、`backlog 0b`。
3. **软路由不是天花板**：用户怀疑「软路由烂/想重装」时，这条最能止争。两条分开测、分开说：
   - **在路由器本机跑 curl**，流量既不转发也不进 TPROXY，**mihomo CPU 必然 ≈0**——
     这**不构成**「已排除 userspace 代理瓶颈」的证据，只证明 PPPoE 收包路径很便宜。
     汇报时必须说清测的是哪条路径，别把本机测速的结论套到转发路径上。
   - **整机 CPU 用 `/proc/stat` 两次采样算差值、逐核报**，别用 busybox `top -bn1` 接 awk 取列：
     列错位会把 `%VSZ` 当成 `%CPU`，读出 921% 这种超过「核数×100」的不可能值。
     实测 J4125 四核跑 47 Mbps 时合计占用 9.8%、单核最高 12.4%、空闲 90% ⇒ 47M 与 CPU 无关。
     **报「CPU 才 10%」比报「mihomo 0%」有说服力得多**，用户也更认这个。

形态与处置：
- **上下行卡在同一个数（实测下行 40M / 上行 40M）= 限速模板**，不是线路老化；只有单方向低才像协商/线路问题。
  配套的两个签名同样硬：**时延 4 ms + 抖动 0 ms** —— 抖动 0 直接排掉干扰/拥塞/信号差/网线烂；
  这组数字拿去跟运营商举证最有效，比口头描述强得多。
- **换测速节点做交叉验证**：从无线客户端（路由器 App 能显示接入的 AP，如一楼 AP 192.0.2.10）
  测出同一个数、且 Wi-Fi 协商 518 Mbps 只用到 8.9% ⇒ 与内网、与 Wi-Fi 全部无关。
  「路由器本机 + 无线客户端 + 多线程镜像三处同数」是交给用户最易懂、最难反驳的结论形式。
- 定性到这一层后**别改任何本地配置、别换节点、别建议重装软路由**，限速在运营商/光猫侧。
- 让用户在运营商 App 查三样：本月已用流量（达量限速）、账号状态（欠费降速）、套餐是否被改。
  用户报的历史值（「昨晚还能 40MB/s」）是时间线锚点 —— 说明是一两天内的变化，优先达量限速。
- 重拨 PPPoE 是验证「会话级限速」的唯一低风险手段（`ifdown wan; ifup wan`，断网 10~20s）。
  **用户在对局/工作中必须先问再断**；PPPoE uptime 已几天到几周 = 从没重拨过，值得一试。
  **重拨后必然换公网 IP**，顺手核 DDNS 跟上没有：`ifstatus wan` 取新 `address`，
  再 `nslookup <动态域名>` 比对——不一致才算 DDNS 故障（本机 DDNS 在路由器 `/etc/config/ddns`，
  实测重拨后自动更新正常，别把换 IP 当异常报给用户）。重拨完立刻复测，数字不变 = 会话级限速已排除。

## 换路径对照实验（用户提出「拔掉软路由换台路由器」时）

用户想把软路由拔掉换另一台设备验证，**方向是对的**（换掉变量最干净，别否定它）。
做法是：先把已排除项列成一张表交出去，再把实验设计对——否则测出来的「恢复正常」可能是假象。

- **最大的陷阱：新路由器插上自动 DHCP 就上网** ⇒ 光猫在路由模式，测的是完全不同的路径，
  结论作废。必须先确认光猫桥接，新设备**同样 PPPoE 拨号、同一个账号**，才是同一条路径。
- **更快的对照是 PC 直接 PPPoE 拨号**（网线直插光猫，Windows 建宽带连接填同账号）：十分钟做完，
  不用拆机；而且 PC 网卡和软路由不是同一颗，能连网卡本身一起排除。用户会追问「Windows 怎么拨」——
  直接把点击路径给他，别只说「建个宽带连接」：
  `设置 → 网络和 Internet → 拨号 → 设置新连接 → 连接到 Internet → 宽带(PPPoE)`，
  填 `wan.username` / `wan.password`，勾「记住此密码」（后面还要复测）。
  Win10 旧版走 `控制面板 → 网络和共享中心 → 设置新的连接或网络`，路径不同、字段一样。
  顺带提醒：**物理拔线这一步本身就是断网**，用户在看电视/开会时先说清再动。
  四个必须交代的细节，漏一个就白测：
  - **先拔掉光猫到软路由的 WAN 网线**，再插 PC。一个宽带账号只允许一个会话，
    软路由还在拨时 PC 一定拨不上（表现像“密码错”）。
  - **光猫 LAN 口直连 PC，不经过交换机**，否则又多一个变量。
  - **测速必须手动选国内服务器**（speedtest.cn 或 Ookla 网页版手选大连/沈阳）。
    自动选服会飘出境，量到的 0.47M 是垃圾数据，拿它当结论等于重蹈覆车。
  - 账号密码不知道不要猜：它就在路由器 `/etc/config/network` 的 `wan.username` / `wan.password`，
    自己读出来即可（属于用户自己的宽带凭据，不往聊天里贴）。
- **测完回复时盯住一件事：网线插回去后软路由会自动重拨、公网 IP 必变**，要确认 DDNS 跟上，
  别把“IP 变了”当成新故障报给用户。
- **判读**：PC 拨号也慢 ⇒ 线路/光猫侧，软路由无辜；PC 拨号满速 ⇒ 确实在软路由，下一站查网卡驱动
  （Intel I225/I226 的 `igc` 有出名的降速问题）与 PPPoE 实现。
- **用户决定改走「主路由 + 软路由降级当旁路由」时，先把摆放讲对**：别默认把主路由 DHCP 的
  默认网关全指到旁路由——那样全屋流量仍要绕软路由一圈，等于主路由白买，**原来的吞吐问题会原样重现**。
  正确摆法是主路由默认网关指向自己，只让需要代理的设备手动指网关（或主路由做策略路由按 IP 段分流），
  直连流量完全不碰软路由，它的吞吐再差也影响不到全屋。这个拆分本身就是最快的二分法：
  以后出问题一眼能分清是哪一跳。
- **先盘一遍手上闲置硬件，再谈买新的**：用户手上常有一两台闲置迷你主机，性能可能已经超过现役软路由。
  对比实测口径：现役 J4125（Gemini Lake Refresh，4 核 2.0 GHz）vs 闲置 **N5095**（Jasper Lake，
  4 核 2.0–2.9 GHz）—— **N5095 高约 30–40%**，8 GB 内存跑 PPPoE + NAT 绰绰有余。
  把它装成 iStoreOS 当主路由、原软路由降级旁路由，就是零成本的双机对照：主路由拨号跑满 ⇒
  原软路由有问题；仍卡同一个数值 ⇒ 线路/光猫。比「先下单买台路由器」快得多，也正好兑现用户
  「出问题一下就知道是谁的问题」的诉求。**前提先问清网口数**：≥2 个千兆口才能当主路由，
  1 个口只能做单臂路由（VLAN 单线复用，绕），别在网口不明时先给方案。
- **替主路由选型先卡 2.5G WAN 口**：家宽跑 2000M 时，只带千兆口的主路由上限锁死在 ~940M，
  换上去只会得到一个「修好了一半」的假结论。光猫到路由这段是 2.5G（`ethtool` 看 2500Mb/s 协商），
  主路由至少 1×2.5G WAN + 2×2.5G LAN 才配得上。**顺带核 LAN 侧端口**：同一台机器上
  各口协商速率并不一致（实测 eth1/eth3 只到 1000Mb/s），从这些口接的客户端永远测不出 >940M。
- **换设备前把「不是这些」的证据交全**：`/proc/stat` 逐核 CPU、空闲内存、SQM/ingress 三条探针、
  物理层错误（`rx_crc_errors`/`rx_frame_errors`/`collisions` 全 0）、链路协商（`ethtool eth0` 的
  Speed/Duplex/Link detected）、PPPoE MTU 1492 与 `pppoe`/`pppox` 模块。
- 用户情绪已经上来、明确说某侧没问题时（「我都说了联通这没问题」），**不要再重复外部归因**，
  直接认可他的实验设计并把它做对——这是唯一还能推进的动作。

## 真实带宽验证（绕开一切测速软件，定案铁证）
国内镜像多线程并发下载（每线程 `curl -sL --max-time <20> -o /dev/null -w %{speed_download} %{http_code} <大文件URL>`，后台并行 + `wait`，shell 算术求和换算 Mbps）。选阿里/清华/USTC/腾讯云镜像。**必须 `-sL` 跟随重定向并核对 `http_code=200` 且 `size_download` 足够大**——镜像常 302 跳转，不跟会给 1704 B/s 量级的假低速；曾因漏 `-L` 把"单线程≈46M"当结论（错数，后被用户质疑），校正后单线程≈345Mbps。参照值（本机 2000M 宽带）：单线程≈345Mbps、8 并发≈685Mbps。**报任何吞吐数字前先自证测量方法正确，数字被用户质疑时立即承认修正不辩解**。

- **跨源聚合才分得清「单站限速」和「本地上限」**：单源多线程只能证明「该站不限速」。要 4~6 个不同网络的
  镜像同时压（每源 4 线程）；实测同一时刻各源差异极大（34M / 2M / 8M / 0M，多家 404 直接 0），
  **总和仍被压在同一数值**才是本地上限，否则是单站限速。
- **镜像大文件 URL 必须先探活**：`curl -sIL -m 8 -o /dev/null -w '%{http_code}' <url>` —— 阿里云
  `ubuntu-releases` 常 302、TUNA `24.04.1` 已下架 404、USTC 403、腾讯云 404。实测稳定可用的单体：
  `https://mirrors.tuna.tsinghua.edu.cn/ubuntu-releases/22.04/ubuntu-22.04.5-desktop-amd64.iso`
  （200，4.76GB），同版本号路径在 `mirror.nju.edu.cn` / `mirrors.huaweicloud.com` / `mirrors.bfsu.edu.cn` 也通。
- **Ookla `speedtest` CLI 的可信方向随所选服务器而变，不是固定的「只信下行」**：
  先读结果里的 `Server:` 行判位置。**选到境外**（如 Keelung 基隆，Idle 71ms）时
  **下行是垃圾、上行反而准**——实测同一轮 `Download 0.47 Mbps` / `Upload 42.01 Mbps`，
  上行与多线程镜像实测吻合，下行是跨境小水管。**选到国内**时反过来：下行可信、上行失真
  （实测 CLI 报 3.79Mbps，同期上行真实 40Mbps）。
  判据是「这个方向能不能跑满本地出口」，不是某个字段天生可靠。**报数字必须连同服务器名/地区
  一起报**，跨境那一侧的数值直接标为无效，别把它当成「你家下行只有 0.47M」交给用户。
  上行独立求证：`curl -F file=@<30MB随机文件> https://speed.cloudflare.com/__up`（看 `%{speed_upload}`）。
- **并行压测脚本一律先落成文件再重定向执行**：write_file 到 `/tmp/spd.sh`，再
  `ssh -p <port> root@<router> 'sh -s' < /tmp/spd.sh`。`&`/`wait` **只许出现在文件内部**——
  terminal 前台会拒绝命令文本中任何位置的 `&`，**包括 heredoc 正文**（实测把整段
  `<<'ENDSCRIPT' … curl … & … ENDSCRIPT` 原样发过去，直接报 "uses '&' backgrounding" 被拦）。
  所以 heredoc 只适合灌无后台的短脚本，带并发的一律走文件重定向。scp 到 Windows PC 时：
  scp 端是 Windows OpenSSH，写 `/c/Users/...` 会 `dest open ... No such file or directory`，
  要传 `C:/Users/<u>/spd.sh`，再用 Git Bash 的 `/c/Users/...` 路径跑。

## 路由器侧工具坑（OpenWrt busybox）
- **SSH 不在 22 端口**：iStoreOS 路由器 SSH 是 **2222**，22 直接 `Connection refused`
  （别因为 22 拒绝就断定路由器没开 SSH）。连法 `ssh -p 2222 root@192.0.2.10`，密钥已配好可免密。
  顺带：80/443/8080 在此线路被封，2222/32778/9090 通。
- 无 `base64` 命令：脚本传输只能 heredoc 灌（`ssh ... 'sh -s' <<'ENDSCRIPT'`，**脚本内不得含 `&`**）
  或内联 `sh -c '...'`（脚本内避免单引号）。
- **`nc -z` 在此路由上不可信**（实测能跑 46Mbps 的 443 端口它也报 DEAD）：端口探测一律 `curl -s -m5 -o /dev/null -w %{http_code}`。
- Ookla CLI **无 `-o` 输出文件选项**：`-o` 会被当成重复选服报 `Only one server selection can be specified`。
  `-f json` 裸跑会吐 `{"error":"Cannot write: "}`——**不是 stdout 问题，是当前目录不可写**：
  先 `cd /tmp`，并补 `--accept-license --accept-gdpr`。可用形式：
  `cd /tmp && speedtest --accept-license --accept-gdpr -f json`（不加这两个 flag 还会卡在交互式同意）。
- 后台任务（`nohup`）会搅空 heredoc stdin（写成 0 字节文件）：nohup 脱离+落盘分步读，或改内联执行。
  更根本的坑：`terminal(background=true)` 跑的 `ssh 路由器 sh /root/xx.sh` 会随 Hermes 会话结束一起死，
  用户下次进来就是「刚才让你干的活没了」。**跨会话要活的采集一律落成目标机 cron + pidfile 幂等**
  （`[ -f $PIDF ] && kill -0 $(cat $PIDF) && exit 0`），并且 Hermes 会直接拒掉前台命令里的
  `nohup`/`setsid`/`&`，别花时间绕。可复用脚本见 game-latency-triage 的 scripts/pppoe_latency_mon.sh。
- **建 cron 前先 `ps w | grep crond` 数实例**：本机 s6 已在跑 `busybox crond -f -S`，
  再执行 `/etc/init.d/cron restart` 或 `enable` 会起第二个 `/usr/sbin/crond -f -c /etc/crontabs`，
  于是 devmon/netmon 等所有任务**跑两遍**，还留下 `/etc/rc.d/S??cron` 开机自启链接。
  误开了就 kill 掉新实例 + `rm /etc/rc.d/S??cron` 恢复原状。
- 并行压测自干扰：测速期间禁止同时跑其他大流量任务，单线程干净测。

## 归因纪律（用户明确否决过"甩锅给外面"）
- **先本地排除、后外部归因**：下"是外部/服务端问题"的结论前，必须先交本地关停差分证据——把被点名的本地组件彻底关死（`systemctl stop` + `disable`，**凡自建服务连自愈 timer 一并停**，否则会被自动拉起造成假排除），在原生状态下复测，结果不变才算排除。用户点名"是你搞的 DNS/配置"时照做不辩解，拿数据说话。
- **本机架构事实（排除时引用）**：路由器解析链 = 路由器 dnsmasq(53) → `127.0.0.1#7874` = mihomo(clash 进程) → 真上游 203.0.113.1/203.0.113.1；Hermes 容器（CT <ID>）自建 dnsmasq 只绑自身 127.0.0.1，**不在全家解析链上**，关它不影响任何其他设备。
- **用户否决外部归因时的备择假设**：mihomo userspace 是 DIRECT 也必经的进程，弱 CPU 软路由可能成吞吐天花板（特征=本地并发/单线程也远低于标称）。验证用「`/proc/stat` 逐核 CPU 差值 + 绕过内核的裸吞吐对照」，**别用路由器本机测速时的 mihomo 占用当证据**（本机流量不进 TPROXY，mihomo 必为 0，见层4第3条）。不空口站队。

## 改动纪律：生产路径不做实验

排障时**实验对象和用户的日常入口不能是同一个东西**。本机教训：为了给测速页找个能打开的地址，
往用户天天在用的 `speed.<域>:18443` 站点块里加了路径、挪了 `encode gzip`；
随后用户报「这个站以前能跑 70M，现在只有三四十」——改的其实是旁边的路径，但他只看到「你动过它」，
整轮排障的可信度当场归零，用户直接发火要求停手。

规则：
- **实验一律新开独立 site / 独立端口 / 独立子域**，生产配置一个字节都不动。
- 用户报「以前是 X 现在是 Y」时，**第一动作是把近期改动整文件回滚 + 逐个验证**，然后才谈测试结果。
  不要先解释「理论上碰不到这条路」——那正是最像辩解的一句话。
- 回滚后交**回归清单**（每个站点一条状态码/每个服务一行状态），比任何解释都有说服力。
- 只改一处、改完立刻自测；**同一晚不要在同一个服务上叠三轮以上实验**。
  连续三轮假设被自己推翻之后，正确动作是停手交付现状，不是再猜第四个原因。

## 汇报纪律（用户明确纠正过）
此类排查必然多轮往返，**每轮收尾必须带状态块主动汇报**（修了什么/证据/剩余尾巴），严禁静默收尾等用户来问「到底修没修好」。
