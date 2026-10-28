---
name: lan-offline-triage
description: Use when 内网设备离线/ping 不通（摄像头、NAS、IoT）——路由器侧取证定层，再修消费端。
---

# 内网设备离线排查（路由器取证优先）

> 相邻类：**外网服务/PT 站连通性**（连接性为否、入站端口、公网 IP 变动、分流错位）→ 见 `pt-connectivity-triage`。

## 铁律（每次适用）
- **去路由器看，别在消费端空转**：米家 App / HA / go2rtc 只告诉你「它觉得离线」；是谁、何时、断在哪一层，只有路由侧数据（ARP/DHCP/logread）能回答。消费端用来确认症状，不用来找根因。
- **先确认有线还是 WiFi 再选证据源**：有线 → ARP/租约/交换机；WiFi → 锐捷 AC `staList`。别默认去查 AC 的 WiFi 客户端表——有线设备根本不在那儿。
- **锚点是消费端配置里的真实 IP**（go2rtc yaml 的 `@<ip>`、did），不是 HA 实体名里的数字：实体名是创建时的快照，IP 漂了它不改。

## 取证（一条 stdin 脚本打完）
入口：`ssh -p2222 root@192.0.2.10 'sh -s' < /tmp/x.sh`（busybox sh；无 `timeout` 命令；`scp -P2222` 不可用 → 脚本走 stdin）

1. **ping + ARP 分层**：`ping -c3 -W1 <ip>`；`grep "^<ip> " /proc/net/arp` → flag `0x0`/MAC 全零 = 连 L2 都没响应 = **物理层**（断电/网线/交换机口）。
2. **租约认设备**：`grep <ip> /tmp/dhcp.leases`，hostname 带型号（`isa_camera_cw501`、`chuangmi_camera_81ac1`）直接对上是哪台。
3. **死亡时刻**：`logread | grep -E '<MAC>|<IP>'` 最后一条 `DHCPACK` = 设备最后一次活着的时间点。**logread 是环形缓冲（本机十几小时量级），尽早查**，晚了只剩租约到期时间可反推。
4. **范围测试**（定单点还是成片）：`for ip in $(awk '{print $3}' /tmp/dhcp.leases); do ping -c1 -W1 -q $ip >/dev/null 2>&1 || echo DEAD $ip; done` → 死 2/37 = 单点；死一片 = 交换机/上联/整段断电。**手机类随机 MAC 设备 ping 不到是常态（休眠/离家），先排除再报数**。
5. **排除「换了 IP」**：全 /24 `ping` 扫一遍灌 ARP，再按设备 MAC 全表搜 → 扫不到 = 真不在网，不是漂了。
6. 交换机嫌疑：先 ping 交换机自己的管理 IP（整机活着但端口/供电坏是常见形态），`nmap -Pn -p 21,22,23,80,443,445,8080` 探管理面（H3C 默认常全关，读不到端口状态就只能物理查）。

## 定性表
| 证据 | 层 | 动作 |
|---|---|---|
| ARP `0x0` + 全网扫不到 MAC（+同秒多台一起断） | 物理层 | 交用户三步：交换机断电 10s 重启 → 查水晶头进水/氧化 → 查电源适配器 |
| 链路通 + 流源 `401` | **先查源 IP 是否指到正确设备**，别先怀疑密码/token | 见下「消费端修 IP」 |
| 链路通 + `i/o timeout` | IP 已对、设备真没回来 / 设备应用层挂 | 等物理修复或查设备侧 |
| 两台设备秒级同时断 | 共享的东西坏了：同一交换机/同一插排/同一供电 | 别逐台查 |

## 修复（设备没回来时先修「回来后能自动恢复」的链路）
1. **静态 DHCP 保留**（根治 IP 漂移）：
   `cp /etc/config/dhcp /etc/config/dhcp.bak.$(date +%Y%m%d%H%M%S)` → `uci add dhcp host` + `uci set dhcp.@host[-1].{enabled='1',mac='..',ip='..',name='..'}` 每台一条 → `uci commit dhcp` → `/etc/init.d/dnsmasq restart`。
   读回用 `uci show dhcp | grep '@host\['` —— **字段名是 `@host[N]`，grep `dhcp.host.*` 会匹配不到，空输出 ≠ 没写进去**。
2. **消费端改源 IP**：go2rtc 配方（备份/diff/restart/逐路 frame.jpeg 验证）见 `home-assistant-admin/references/go2rtc-streams.md`。
3. **动路由配置后必验三件套**：`nslookup baidu.com`（DNS）+ `ping -c1 203.0.113.1`（WAN）+ OpenClash 存活（`/etc/init.d/openclash status`；勿 `pgrep -f mihomo`，本机二进制叫 `clash`，恒返回空会误判，见 `openclash-user-guide` 本机纪律）——dnsmasq 重启最容易顺手带出 DNS/代理暗伤。
4. **错误语义变化 = 修对了**：`401`（源 IP 指向错误）→ `i/o timeout`（IP 对了、设备还没回来）→ 设备回电后消费端出帧才闭环。
