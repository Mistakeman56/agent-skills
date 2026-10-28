# 间歇性掉线 → 光猫(ONU)死机诊断（2026-08-19 实测）

场景延续 `router-wan-health-monitor.md`（v1 监控脚本见该文件）。本次断网事件坐实了决定性诊断逻辑，且把监控升级到 v2（持久化 + 光猫监测）。

## 决定性诊断逻辑：重启路由器无效 + 重启光猫生效 = 光猫/光链路问题

用户报"楼上啥也没动突然断网 → 重启路由器不好使 → 拔光猫重启才好"。判断链：
1. 断网时路由器还活着（SSH 能进）→ 问题在 WAN 上游
2. 重启路由器后仍不通 → **路由器不是病根**
3. 重启光猫（拔电重插）后恢复 → **光猫死机 / PON 光信号中断实锤**
4. 报联通话术："光猫频繁死机，重启光猫才能恢复" → 要求查光功率/换光猫

**⚠️ 先问用户是否手动重启过路由器！** 手动重启会把 uptime 归零 + WAN IP 变化，**伪造**一次 `PPPoE_RECONNECT` 证据。看到监控里 uptime 骤降/IP 变化，先确认不是人为操作（实测用户一句"刚才是把路由器重启了"让一次"抓到的重连"直接作废）。只有排除人为重启后的重连才算自动掉线。

**⚠️ 光猫管理 IP 探测：** 桥接模式下光猫不提供 DHCP/DNS，管理 IP 需逐个探测（本户 VSOL V2901Q = 192.0.2.10）。Web 80 端口可能 HTTP:000（管理面受限）但 ping 通——用 ping 做可达性检测：
```bash
for ip in 192.0.2.10 192.0.2.10 192.0.2.10 192.0.2.10 192.0.2.10; do ping -c1 -W1 $ip >/dev/null 2>&1 && echo "$ip 通"; done
```

## 监控 v2 升级要点（相对 v1）

- **数据存 `/etc/netmon`（flash 持久目录）而非 `/tmp`（tmpfs）**：v1 存 /tmp，用户一重启路由器日志全没，断网证据丢失。v2 已迁移，重启不丢。
- **新增光猫(onu)可达性检测**：每轮 ping 192.0.2.10，记录 `onu=yes/no`，从 yes→no 记 `ONU_LOST` 事件。
- **事件现场自动留痕**：检测到事件时把 logread 过滤 dnsmasq 后的系统日志 + pppoe-wan 接口状态写入 `crash_YYYYMMDD.log`。
- 路由器 logread 被 dnsmasq `log-queries=extra` 刷屏，抓现场必须 `grep -viE 'dnsmasq'` 过滤。

## Hermes 侧 no_agent cron 部署要点

- 脚本 `~/.hermes/scripts/check_netmon.py`：SSH 带 `BatchMode=yes`（无交互）、`-p` 紧跟 ssh 后；`cat` 不存在文件 rc=1 且 stderr 含 "No such file" → 视为空，否则误报 SSH 失败。
- cron create 默认 `repeat=once`——**创建 no_agent 循环任务后必须 update `repeat=0` / `every 30m` 才会 forever 循环**（实测踩坑：第一次创建出来是 once，改了才变 forever）。
- 健康时静默零输出（0 token），有异常事件才推送。
