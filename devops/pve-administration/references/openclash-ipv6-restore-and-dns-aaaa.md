# OpenClash IPv6 恢复 + DNS AAAA 下发（零泄漏设计）

> 目标：恢复 iStoreOS 家宽 IPv6、让国内 CDN 走本地 v6 节点，同时做到「OpenClash 不接管 v6 流量」
>「国外域名零 v6 泄漏」「防火墙 nftables 零改动」。实测收益：拉流节点 RTT 从 25~34ms（外地）降到 9.7ms（本地）。

## 一、三个开关各管一件事（别搞混）

| 位置 | 值 | 含义 |
|---|---|---|
| `9.1.yaml` **顶层** `ipv6:` | **false** | mihomo 不处理 v6 流量 → **v6 直连不走代理 = 零泄漏** |
| `9.1.yaml` **dns 段内** `ipv6:` | **true** | DNS **返回 AAAA**（设备才能拿到 v6 地址）|
| `uci openclash.config.ipv6_dns` | `1` | 持久化上面那条（**不设则重启后被改回 0**，必设）|
| `uci openclash.config.ipv6_enable` | **0** | OpenClash 的 v6 总开关 = 「不接管 v6」→ 保持 0（否则它会用 ip6tables mangle 做 v6 透明代理）|
| `uci openclash.config.filter_aaaa_dns` | `0` | AAAA 过滤关 |

**验证零泄漏**：`curl -H "$(cat hdr)" 'http://127.0.0.1:9090/dns/query?name=www.google.com&type=AAAA'`
→ 返回 **`2001::1`（死地址）** = mihomo 故意不给国外真 v6，而国内域名返回真实 `2408:`。

## 二、内网 v6 打通的必改点（iStoreOS/OpenWrt）

```sh
# ★★★ 最关键：wan6 必须挂在 @wan 上（PPPoE 占了 eth0，挂 eth0 永远拿不到前缀）
uci set network.wan6.device='@wan'; uci set network.wan6.auto='1'
uci set network.wan.ipv6='1'
uci set network.lan.ip6assign='64'
uci set dhcp.lan.ra='server'; uci set dhcp.lan.dhcpv6='server'
uci set dhcp.@dnsmasq[0].filter_aaaa='0'
sed -i 's/^net.ipv6.conf.br-lan.disable_ipv6=1/#&/' /etc/sysctl.conf   # 该行是早前为收口手工加的
```
判定成功：`ifconfig pppoe-wan | grep inet6` 见 `2408:` 全局地址 + `ifstatus wan6` 见 `"delegation": true`
+ `ip -6 addr show br-lan` 见委派前缀 + `ping6 2400:3200::1` 通。
**wan6 没配 `@wan` 的症状**：`ps | grep odhcp6c` 无进程、netifd 日志有 `wan6 has link connectivity` 却拿不到地址。

## 三、DDNS 只发 IPv4（铁律）

家宽 v6 **前缀会变**（重播即换）—— 把 v6 写进公网 AAAA = 域名间歇性解析到废地址 = **门户间歇性打不开**。
`~/.hermes/scripts/ddns-sync.py` 因此只同步 A 记录，并**主动 DeleteDomainRecord 清理所有 AAAA**
（历史脚本会留下 `@`/子域的残留 AAAA，改造后首次运行必须真的删干净并复查 `nslookup -type=AAAA` 返回 No answer）。

## 四、`nameserver-policy`（国内域名用运营商 DNS，纠正 CDN 调度）

- 持久化文件：`/etc/openclash/custom/openclash_custom_domain_dns_policy.list`（映射 mihomo `nameserver-policy`）
  - 内容：`"geosite:cn"` + 具体 CDN 显式域名 → 本地运营商 DNS
  - **只列运营商 DNS，不要同时列阿里/腾讯**（mihomo 并行查询，谁快谁赢 → CDN 调度被公共 DNS 的地理视角带偏）
- 判据：同一域名两个 DNS 应答对比（外地节点 25ms vs 本地 2.5ms 即坐实）
- **dnsmasq 层的 `/域名/IP` 不要配**：OpenClash 启动会重写 `dhcp.@dnsmasq[0].server`，自加条目会被清空

## 五、坑

1. **busybox sed `i\` 带 `\n` 会改写内容** → 用 `awk` + `getline l < "/tmp/insert.txt"`。
2. **awk/YAML 插入点必须是「键的正下方」**：列表键与其 `xxx-mode:` 后继键**不相邻**（中间隔着其它键），
   插到后继键前 = 在映射里冒出序列项 → `yaml: line N: did not find expected key`（报错行号还会跑到块首的块键上）。
3. **curl 的 `-H "... Bearer *** """` 三连引号**会闭合后又开一个 → `unterminated quoted string`；
   且**把 token 写进工具调用文本会被掩码层替换成 `***`** → 在目标机上用 `awk` 从配置文件现场生成 header 文件，再 `-H "$(cat hdr)"`。
4. **mihomo API 的 `?token=` 查询参数不被这个 alpha 版接受（401）** → 走 header。
5. **`nslookup -type=AAAA` 对 CNAME 链可能返回空** → 用 `curl .../dns/query?type=AAAA` 或 `ping6 域名` 证实。
6. **mihomo `-t` 必须带 `-d /etc/openclash`**（否则报 `path is not subpath of home directory`）；
   **`PUT /configs` 204 = 配置被接受，400 = YAML 没过校验** → 先 `-t` 再 reload。
7. **改运行时配置文件先 restore、每改一步验一次**（restore → edit A → test → edit B → test），谁让 YAML 破的当场就知道。

## 六、回滚

- 路由器 uci/sysctl：`/root/v6-enable-<ts>/rollback.sh`（恢复 /etc/config + sysctl + reload）
- OpenClash 运行时：改动前先 `cp -a 9.1.yaml /root/oc-v6dns-<ts>/9.1.yaml.bak`（同族备份目录沿用 `oc-*` 命名）
- 热重载：生成 header 后 `curl -X PUT -H "$(cat /tmp/hdr.txt)" 'http://127.0.0.1:9090/configs?force=true' --data-binary @/tmp/rc.json`，期望 HTTP=204

## 七、遗留风险（如实记录）

`ipv6_dns=1` 后，OpenClash **下次启动**会走到 `/etc/init.d/openclash` 里 `ipv6_dns -eq 1 && ip6tables …` 的分支
—— 只涉及 **ip6tables(v6) 的 DNS 劫持**，**不碰 nftables(v4)**，但属「动防火墙」范畴 → **重启 OpenClash 前先跟用户确认**。
`ipv6_enable=0` 保证 OpenClash 不做 v6 透明代理（v6 仍直连）。
