---
name: pt-connectivity-triage
description: Use when PT站连接性为否、种子tracker报错、入站端口不通、公网IP变动影响绑定服务时排查。
---

# PT 站连通性排查（按层取证）

## 铁律
- **「连接性为否」= 站点反连你 announce 的 IP:端口失败**，是三方对齐问题：announce 出口 IP、站点记录的 IP、端口转发，任一错位都报这个。先定哪方错位，别猜。
- **播报成功 ≠ 连接性正常**：tracker 播报是「出站」，连接性是站点「入站反连」，两条路独立，必须分别验。
- **系统没病不重装**：重装路由器系统不解决 IP 变动和分流错位，还会冲掉 nft 绕行/custom 规则。
- 「以前好好的现在不行」→ 先查最近的变更（重启重拨、配置切换），时间线常严丝合缝。

## 访问入口
- 路由器：`ssh -p2222 root@192.0.2.10 'sh -s' <<'EOF' ... EOF`（busybox sh、无 python3、无 timeout）。**`<<'EOF'` 引号 heredoc 把 `$VAR` 原样传给远端展开，别加 `\$` 转义**——加了传的是字面量，脚本静默返回空。
- NAS：`sshpass -p '<密码在记忆>' ssh user@192.0.2.10 'sh -s' <<'EOF'`
- 种子/端口/凭证细节另有档案：`pve-administration/references/pt-seeding-transfer.md`。

## 取证步骤（自上而下，每层定罪再进下一层）

### ① 播报层：tracker 现在通不通
```sh
# 凭据在容器 env，键名是 USER= / PASS=（不是 TRANSMISSION_*，那些常为空）
U=$(docker inspect transmission_4.1.0 --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -E '^USER=' | cut -d= -f2-)
P=$(docker inspect transmission_4.1.0 --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -E '^PASS=' | cut -d= -f2-)
docker exec transmission_4.1.0 transmission-remote -n "$U:$P" -t all -it   # -it = tracker 信息
# 主机清单 / 错误计数：
docker exec ... -it | grep -oE 'Tracker [0-9]+: [^ ]+' | awk '{print $3}' | sort | uniq -c
docker exec ... -it | grep -icE 'error|fail|bann|timeout|refus'
```
- **0 报错 = 播报层无罪**，问题在下层，别在这儿纠缠。
- ⚠ `-st` 是会话统计，不是 tracker 状态；tracker 只认 `-it`（--info-trackers）。
- ⚠ 直连 RPC（9091）要先 GET 握手拿 `X-Transmission-Session-Id`，否则 409；`ids:"all"` 可能返回空数组，transmission-remote 更稳。

### ② 转发层：外部到底能不能打进来
```sh
# DNAT 计数器隔几秒采样两次，看是否在涨
nft list ruleset | grep 'tcp dport <端口> counter' | grep -v saddr
# 现行外部连接：conntrack 输出里 dst 恒为内网 IP，只能按 src 字段抽！
conntrack -L -p tcp --dport <端口> | awk '{print $5}' | grep -v '^src=192.168' | sort | uniq -c
```
- ⚠ **禁止用「从代理节点 curl 自己公网 IP:端口」当外部反测**——GEOIP,CN 规则会把流量 hairpin 回内网，测了个寂寞。conntrack 现行外部连接 + 计数器增量才是真证据。
- ⚠ conntrack 整行 `grep -v 192.168` 会把所有行滤光（每行 dst 都含内网 IP），必须先 `awk '{print $5}'` 抽 src。

### ③ IP 变动层：公网 IP 是不是漂了
```sh
ifstatus wan | grep -E '"up"|uptime'    # uptime 秒数 = 距上次重拨时长
ip -4 addr show pppoe-wan               # 当前公网 v4，与档案基线比对
ip -6 addr show pppoe-wan               # v6 前缀也比对（/64 全变 = 重拨）
```
- 对不上基线 = 重拨换过 IP。PT 站反连的是它记录的旧 IP → 必然失败。慢性漂移的治本是 DDNS 或站点 IP 绑定刷新。

### ④ 分流层：浏览器路径 ≠ 客户端路径（fake-ip 模式高发）
```sh
nslookup <PT域名> 127.0.0.1             # 返回 198.18.x.x = fake-ip 模式
# mihomo 实时连接走了哪条规则哪个组（路由器无 python3，JSON 拉回本机解析）
curl -s -H 'Authorization: Bearer <Clash API secret>' http://127.0.0.1:9090/connections
```
- 症状组合「网页显示连接性为否 + 种子播报却成功」= 分流错位：浏览器流量走代理（站点看到节点 IP，反连节点端口必败），客户端有源 IP 直连规则（announce 报真 IP）。两侧 IP 不一致 → 站点判定异常。
- 修法：PT 域名加 `DOMAIN-SUFFIX,<域名>,DIRECT` + 进 fake-ip-filter；**只加 SrcIPCIDR 源规则不够**——网页流量来自其他设备，必须按域名直连。改完去站点重新登录刷新 IP 记录。
- ⚠ **写完规则必须在运行配置里验证落地**：`grep <域名> /etc/openclash/config/<cfg>.yaml`。OpenClash 的 custom 规则合并只在 LuCI 保存配置时触发，`restart` 不会重新合并——grep 不到就直接写进配置的 `rules:` 段（4 空格缩进），再 `clash -t -f <cfg>` 验证后重启。

### ⑤ IPv6 层（站点 v4/v6 双探时）
- 站点探 AAAA：v6 入站没放行/前缀变了 → v4 全通也显示「否/部分」。
- 验：`nft list table ip6 fw4 | grep <端口>`（空 = 无 v6 放行）；NAS 全局 v6：`ip -6 neigh show dev br-lan | grep 2408`。

## 定罪表
| 证据组合 | 根因 | 修 |
|---|---|---|
| 播报 0 错 + conntrack 有外部连接 + IP 漂了 | 站点绑旧 IP | 站点面板重登/刷新绑定；慢性漂移上 DDNS |
| 播报成功 + 网页「连接性为否」+ 域名走代理组 | 分流错位 | PT 域名 DIRECT + fake-ip-filter |
| conntrack 无外部连接 + DNAT 计数器不涨 | 转发缺/坏 | 查 /etc/config/firewall（先备份） |
| v4 通 + 站点仍否 + v6 前缀变 | v6 反连失败 | 补 ip6 放行，或确认站点只看 v4 |

## 修复纪律
- 动转发/规则前先带时间戳备份；改完验三件套：DNS（`nslookup baidu.com`）+ WAN（`ping -c1 203.0.113.1`）+ OpenClash 存活（`/etc/init.d/openclash status`，勿 `pgrep mihomo`，二进制叫 clash）。
- 重启后 mihomo 消失且日志报 `OpenClash Now Disabled, Need Start From Luci Page`：`uci get openclash.config.enable` 置 0 了，`uci set openclash.config.enable='1'; uci commit openclash; /etc/init.d/openclash start` 拉回。
- 流量归因（「N 天 N G 花哪了」）：mihomo **无历史账本**，/connections 只有现役连接，事后无法回溯——只能装定时采样脚本从现在起记，别承诺回溯定罪。
- 路由器防火墙/nftables 只读优先；写操作先报命令等用户点头（红线）。