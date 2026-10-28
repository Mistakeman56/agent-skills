# 「升级宽带后下载跑不满」怎么查（以 iStoreOS / J4125 为例）

## 用户会这么描述

「升级 2000M 之后一开始很快，后来 IStore 里的测速一直 1M，下载也跑不满，真想重装系统从 0 开始」。

**别顺着「重装」走。** 先证明到底谁在限速，因为重装会丢掉 DDNS 脚本/端口转发/OpenClash 配置/监控/Docker，而且如果是服务器侧限制，重装一点用没有。

## 关键方法：单流 vs 多流 × 路由器自身 vs 经转发

这四个数交在一起就能定位限速在哪一层：

| | 单流 | 多流(8~16) |
|---|---|---|
| **路由器自己下载**（不经转发） | 路由器 CPU / 对方服务器 | 路由器 CPU / 线路 |
| **局域网客户端下载**（经转发） | 加上转发开销 | 转发能力 + 线路 |

- **单流（路由器自身）≈ 单流（经转发）** → 转发不是瓶颈（路由器清白）
- **多流能到线路速度** → 线路清白
- **同一时刻换几个不同国内源测单流** → 差几倍到几百倍就是**对方服务器限制**（实测：清华 24.4 / 阿里 12.8 / USTC 0.1 MB/s）
- **多流时看 loadavg** → 一直 0.1~0.2 就不是 CPU 瓶颈

脚本（本地写好 scp 上去跑，别用 `timeout`）：

```bash
U="https://mirrors.cloud.tencent.com/ubuntu/ls-lR.gz"   # 约 38.5MB
run_batch() { for i in $(seq "$1"); do curl -s -o /dev/null -m 20 -r 0-25000000 \
  -w "%{speed_download}\n" "$U" & done; wait; }
echo -n "单线程 ⇒ "; curl -s -o /dev/null -m 25 -r 0-150000000 -w '%{speed_download}' "$U" \
  | awk '{printf "%.1f MB/s (%.0f Mbps)\n",$1/1048576,$1*8/1000000}'
for N in 8 16; do echo -n "$N 并发 ⇒ "; run_batch $N \
  | awk '{s+=$1} END {printf "%.1f MB/s 合计 (%.0f Mbps)\n",s/1048576,s*8/1000000}'; done
wc -c /proc/loadavg; cat /proc/loadavg   # 跑的时候另开一个 shell 看
```

**注意**：`ls-lR.gz` 只有 38.5MB，单流测试会包含 TCP 慢启动，**实测值偏低，别当成稳态上限**。

## 坑：iStoreOS 自带测速 `/usr/bin/speedtest` 会选境外服务器

```
Server: kdatacenter.com - Seoul (id: 48402)
[error] Error: [0] Timeout occurred in connect.
Download: 549 Mbps   Upload: 80 Mbps
```

它列出的服务器里**几乎没有国内联通节点**（只剩昆山杜克 30852，还报 `Cannot open socket`）。所以 iStore 里那个测速数**对 2000M 国内线路毫无参考价值**，用户看到的「一直是 1M」就是这个工具连不上/选到烂节点。

**要准数据：让用户在浏览器里跑 speedtest.cn，或用多线程下载器。**

## 上行是不是被 SQM 掐住了（A/B 法）

```sh
tc -s qdisc show dev pppoe-wan           # 看 cake bandwidth 值
/etc/init.d/sqm stop; sleep 4            # 临时拆掉限速（可 sqm start 恢复）
# 同一端点、同一服务器重测上传，直接对比
/etc/init.d/sqm start                    # 记得恢复！
```

**参考实测（2000M 联通，真实上行 ~90M）**：SQM 开 62.6 Mbps vs 关 67.4 Mbps → 只差 8%，说明 `upload='90000'` 基本等于真实上行，**配置正确，不要乱改**。cake 的 `overlimits` 计数很大是正常现象（它就该限速）。

## flow offloading 与 SQM 互斥

`nft list ruleset | grep -c flowtable` = 0 表示软件流量卸载没开。开了能降 CPU，但**被 offload 的连接会绕过 cake → SQM 失效**。所以：

- 先看 loadavg。**没跑满就不要开**（拿 SQM 换一点 CPU 余量不值）
- 只开 `firewall.@defaults[0].flow_offloading='1'`（软件），**别开 `flow_offloading_hw`**（J4125 不支持，可能反而变慢）
- OpenClash 不自己管 flow_offload（已 grep 确认），但用它时仍需手动关卸载

## 本文这套设备的基准数据（2026-10 实测，供对比）

```
Intel Celeron J4125 @2GHz 4核 / 8GB / iStoreOS 24.10.8 / 内核 6.6.144
转发 单流      375 Mbps
转发 8 并发   1770 Mbps
转发 16 并发  2379 Mbps   ← 2000M 线路真实可达，路由器不是瓶颈
路由器自身单流 319 Mbps    ← 与转发值几乎相同，证明转发无损耗
CPU           loadavg 0.11~0.18，从未跑满
\nsqm.eth1: interface=pppoe-wan upload=90000 download=0 qdisc=cake
```

**结论口径**：「你的线、路由器、CPU 都是好的；单流跑不满是对方服务器掐的，换任何路由器都一样」——用上面那张对比表说话，别说「CPU 瓶颈」（会被用户拿 loadavg 打脸）。

---

## 路由器脚本 / 命令铁律（踩过的坑）

- **BusyBox 没有 `timeout`**：写了会 `ash: timeout: not found` 秒退，循环里每项都显示 ❌，**看起来像「所有 DNS 全挂了」的假警报**。排查 DNS 别只在路由器自测，**务必从局域网客户端交叉验证**。
- **BusyBox `date` 不支持 `%N`**：测毫秒耗时要用客户端 Python，别在路由器上算。
- 测速/吞吐脚本**本地 write_file + scp**，不要用 heredoc/`echo >>`（BusyBox 没有 base64）。
- **别在 terminal 工具里写 `&` 后台符**（会被拒），并行 curl 要包在脚本文件里。
- 读代理/订阅配置会**带出节点密码**，输出前先 `sed -E 's/password: [^,}]+/password: <REDACTED>/'`。

---

## 「某个站点 / 某个设备卡顿」怎么查（≠ 整条线跑不满）

用户会说「我刷抖音又开始卡了」。**分三层定位，不要跳步**：代理/出口 → 无线空口 → 客户端自身。

### 第 0 步：先证明代理到底有没有参与 ★★

国内站（抖音/B站/微信）卡，**第一反应不能是「代理节点死了」**。Clash 日志里出现
`level=error ... context deadline exceeded` 这类节点健康检查失败，**只是某个节点在健康检查里超时，
不代表任何真实流量走过它** —— 顺着这条线索查，会白烧一整轮还带偏用户。

两条命令定性：

```sh
A="Authorization: Bearer <secret>"
curl -s -m 8 -H "$A" http://127.0.0.1:9090/rules | tr "{" "\n" | grep -iE "douyin|bilibili|GeoIP|Match"
curl -s -m 8 -H "$A" http://127.0.0.1:9090/connections
```

- `DomainSuffix douyin.com → DIRECT` + `GeoIP cn → DIRECT` → **国内站本来就直连，代理无关**
- 再看连接表：**目标站点的连接根本没出现** = 它压根没进 Clash，代理嫌疑彻底排除
- 兜底 `Match → <节点组>` 只管「未命中任何规则」的境外流量

### 第 1 步：路由器自身直连目标站 + 看 WAN 是否被占满

```sh
curl -s -o /dev/null -m 15 -w "dns=%{time_namelookup}s connect=%{time_connect}s total=%{time_total}s code=%{http_code}\n" https://www.douyin.com/
r1=$(cat /sys/class/net/pppoe-wan/statistics/rx_bytes); sleep 2
r2=$(cat /sys/class/net/pppoe-wan/statistics/rx_bytes); echo "$(( (r2-r1)/2/1024 )) KB/s"
```

`code=200` + `total` ≈0.1~0.2s → 出口清白。用户说「在刷视频」而 WAN 只有几十~几百 KB/s，
说明要么他没在刷、要么 App 卡在连不上 —— **两种情况都不是带宽问题，别在这层继续纠缠**。
（顺带看一眼 loadavg / CPU，<0.3 就与转发瓶颈无关。）

### 第 2 步：无线空口 —— 看 `min` vs `avg/max`，别只看平均值 ★★★

这是定位「视频一卡一卡」的核心手法。**ping 目标设备的同时，ping 一台有线设备做对照**：

```sh
ping -c 30 -W 1 <无线客户端IP>          # 小包：看 min 与抖动
ping -s 1400 -c 20 -W 2 <无线客户端IP>   # 大包：空口拥塞在大包上恶化更明显
ping -c 10 -W 1 <有线设备IP>            # 对照基准
```

| 现象 | 含义 |
|---|---|
| `min` 个位数 ms + `avg/max` 暴涨到几十~上百 ms | **信号满分但抢不到空口** → 同频争用/重传，视频必卡 |
| `min` 本身就大（>20ms） | 覆盖/距离问题 → 调功率或补 AP |
| 有丢包 | 严重干扰，或设备省电休眠 |

**实测对照（同一条 2000M 线、同一时刻）**：有线设备 `0.18/0.31/0.38ms` 稳如磐石；
无线手机 `2.4/39.4/111.9ms`、iPad `17/80/128ms` —— `min` 只有 2.4ms 说明信号满分，
**`avg` 被拉到 39ms 就是纯排队**。有线 vs 无线这个数量级差，就是「不是代理、不是线路、是空口」的铁证。

**铁律：单次 ping 不能当结论。** 同一台手机几分钟内可以从 `3ms` 变成 `39ms`；
下结论前至少采两轮、并与有线对照，否则会把波动误判成常态（或反过来）。

### 第 3 步：客户端 IPv6 幽灵（会伪造出「卡」）

IPv4-only 的网络里，客户端仍可能握着**不可路由的全局 IPv6 地址**：

```sh
ip -6 neigh show dev br-lan | grep -v fe80   # 出现 2408:/2400: 等全局地址 = 有幽灵
ping6 -c 3 -W 2 2400:3200::1                 # Network unreachable = 路由器没有 v6 出口
ip -6 route show default                     # 空 = 无 v6 默认路由
```

国内 App（抖音/B站）多用**自家 HTTPDNS，会绕过 dnsmasq**，所以 `filter_aaaa='1'` 生效也拦不住它
自己拿到 AAAA → 先试 IPv6 → 撞墙等超时 → 回退 IPv4 → 表现成卡顿。

清理（可回滚；改前先 `uci export dhcp > 备份`）：

```sh
sysctl -w net.ipv6.conf.br-lan.disable_ipv6=1
grep -q br-lan.disable_ipv6 /etc/sysctl.conf || echo "net.ipv6.conf.br-lan.disable_ipv6=1" >> /etc/sysctl.conf
ip -6 neigh flush dev br-lan
/etc/init.d/dnsmasq restart
```

⚠️ 这是**消除隐患**的动作，不是本次卡顿的结论。做完仍要用第 2 步确认抖动来自空口；
**如实告诉用户这是独立异常、并给出还原路径**，别把它包装成「找到真凶了」——
被用户追问「抖音为什么不直连、要走土耳其节点」就是这么来的（把一条无关线索当成了主因）。
