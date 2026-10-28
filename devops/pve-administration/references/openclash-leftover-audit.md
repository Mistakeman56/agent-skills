# OpenClash 关闭后的残留审计 + fake-ip/redir-host 选型

用途：用户说「今天更新/开关过 OpenClash 之后网变卡」「怀疑流量还在走代理」「国内网站波动大、下载一动不动」时的取证流程。

**铁律：先证明「不是代理」，再查别处。** 用户的主观归因（「肯定是走了代理」）经常是错的；把七项全查一遍只需 2 分钟，否则会在错误方向上耗很久。

## 一、七项残留审计（全部只读）

```sh
# 1) nftables 重定向/tproxy
nft list ruleset | grep -inE "redirect|tproxy|7890|7891|7892|7874|9090|clash"
# 2) iptables legacy
iptables-save | grep -inE "REDIRECT|TPROXY|7890|clash"
ip6tables-save | grep -inE "REDIRECT|TPROXY|7890|clash"
# 3) dnsmasq 上游被劫持（OpenClash 会插 */tmp/dnsmasq.d/* 指向 7874）
ls -la /tmp/dnsmasq.d/
grep -rn "7874\|7890\|127.0.0.1#" /tmp/dnsmasq.d/ /etc/dnsmasq.conf /var/etc/dnsmasq.conf*
cat /tmp/resolv.conf.d/resolv.conf.auto
# 4) DHCP 给客户端下发代理/改网关
uci show dhcp | grep -E "option (3|6|44|252)|dhcp_option"
# 5) 策略路由（最容易被忽略）
ip rule show                      # 看有没有 fwmark → table 100/101/354
for t in 100 101 102 200 201 202 354; do ip route show table $t; done
# 6) 进程与服务自启
ps | grep -iE "[c]lash|[m]ihomo"
ls -la /etc/rc.d/ | grep -i openclash
crontab -l | grep -i clash
# 7) firewall 里的死 include
fw4 check 2>&1 | grep -i "unreachable path"
```

**结论模板**：
- 1–6 全空 → 代理**完全脱钩**，卡的锅不在代理规则。**别停在这里**：若症状是「挑应用黑」（百度通、抖音/B站/小红书死）且起病有钟点规律，锅是 oaf 时段封禁而不是残留——按 `network-slow-diagnosis.md` 的「动手前三问」+ oaf 段走，配置面见 `istoreos-app-filter.md`；审计全空只是排除了代理，不等于找到真凶。
- 第 7 项出现 `Section openclash specifies unreachable path '/var/etc/openclash.include', ignoring section` 是**无害残留**：fw4 自己会忽略，只要同一份输出末尾是 `Ruleset passes nftables check.` 且退出码 0，就**不要**去删那个 uci 段（删它要 `fw4 reload`，风险大于收益 —— 遵守「只加不动」）。

## 二、证明外网侧没问题（关键：路由器自己的 curl 不走 forward 链）

```sh
for u in https://www.baidu.com https://www.bilibili.com https://mirrors.aliyun.com; do
  curl -s -o /dev/null -m 12 --noproxy '*' \
    -w "$u → %{http_code} DNS:%{time_namelookup}s 连接:%{time_connect}s 总:%{time_total}s\n" "$u"
done
ping -c 20 -q 203.0.113.1        # 用 203.0.113.1；联通 DNS 203.0.113.1 屏蔽 ICMP，ping 不通≠坏
```

**判读**：`time_connect` 0.02–0.05s、`time_starttransfer` < 0.2s → 外网和 DNS 都健康，问题在**客户端到路由器这一段**，别再去改 WAN。

> 注意：从路由器发起 curl 不经过 `forward` 链。所以「路由器测速快」不能证明客户端路径没问题；要对比就从一台 LAN 客户端再测一遍。

## 三、「下载一动不动」的头号嫌疑：IPv6 只关了一半

用户说「IPv6 没用了，我关了」通常只关了 WAN6，LAN 侧这三样还在跑，必须一起关：

```sh
# 查：客户端是不是还拿着全局 IPv6
ip -6 neigh show dev br-lan | grep -c '2408:'        # >0 = 客户端还有 IPv6
ip -6 addr show dev br-lan | grep 'scope global'
ip -6 route show default                            # 空 = 路由器没有 IPv6 出口
ps | grep '[o]dhcpd'                                # 还活着 = 还在发 RA
uci -q get dhcp.lan.ra                              # 未设置 = 默认 server = 发 RA
```

**机理**：odhcpd 继续发 RA → 客户端（尤其 iOS/Android）装上一條 IPv6 默认路由 → App 自带 DoH/加密 DNS **绕过** dnsmasq 的 `filter_aaaa` 拿到 AAAA → 先试 IPv6 → 路由器无 IPv6 出口 → 连接一直挂着 → **表现为「下载一动不动」，而不是立刻报错**。

**修（只动 dhcp，不动 network，避免 network restart 断网）**：
```sh
mkdir -p /root/net-bak-$(date +%Y%m%d-%H%M%S) && cp /etc/config/dhcp /root/net-bak-*/ 
uci set dhcp.lan.ra='disabled'
uci set dhcp.lan.dhcpv6='disabled'
uci set dhcp.lan.ndp='disabled'
uci commit dhcp
/etc/init.d/odhcpd restart
# 验证 IPv4 没被带倒：dnsmasq 仍在 :67、ping 客户端 0% loss、curl baidu 200
```
回滚：`uci set dhcp.lan.ra='server'; uci set dhcp.lan.dhcpv6='server'; uci delete dhcp.lan.ndp; uci commit dhcp; /etc/init.d/odhcpd restart`

**别用 `network restart` 去删 br-lan 的 IPv6 地址** —— 会瞬断整栋网，且没必要：RA 一停，客户端的默认路由在 router lifetime（默认 1800s）内自然过期。

## 四、fake-ip vs redir-host（用户问「我觉得 fake-ip 好」时）

**结论：fake-ip 更好，用户是对的。** 但要说清机理，而不是附和。

| | fake-ip | redir-host |
|---|---|---|
| 匹配依据 | **域名**（返回 198.18.x.x 假 IP，Clash 反查域名） | **真实 IP**（先解析再拿 IP 匹配） |
| 首包额外开销 | 无 | 每个新域名多一次真实 DNS 往返 |
| CDN 域名（B站/腾讯/阿里） | 准 | **极易误判** —— 几百个 IP 共享，国内站被当成国外 → 绕出去走代理 → 卡 |
| 副作用 | `nslookup`/`dig` 看到 198.18.x.x（正常）；需给内网设备配 `fake-ip-filter` | 无假 IP 干扰 |

- `fake-ip-filter` 必须加：`*.lan`、`*.local`、`192.168.*`、`10.*`，以及内网自建服务域名（NAS/PVE/HA/门户），否则内网服务会被假 IP 劫持打不开。
- 关掉 IPv6 之后 fake-ip 的 AAAA 处理复杂度直接消失 —— 这套组合是「国内直连 + 国外走代理」最省心的配法。
- 模式只影响 OpenClash **开着**的时候。用户关了 Clash 时别急着改模式，先按第一、二节证明「卡与代理无关」。

## 五、顺手要查的两个独立问题（都会造成「网慢」的错觉）

1. **SQM/cake 把上行锁死**：`tc -s qdisc show dev pppoe-wan` 看 `bandwidth`。千兆/两千兆宽带上遗留一个 `upload='90000'` 的 SQM 会把上行砍到 90M。判读看 `overlimits`（高=在压制）与 `av_delay/pk_delay`（低=没拥塞，说明只是限速不是卡顿）。
2. **单口承载全部无线客户端**：`brctl showmacs br-lan` 会告诉你 AP/AC/手机全在哪一个网口。若 AP 与 PC/NAS 不在同一个物理口，且该口只有 1000Mb/s 而下面挂了 30 台设备，高峰期会互相拖；`/sys/class/net/<if>/speed` 逐口确认协商速率（**百兆口**优先怀疑）。
