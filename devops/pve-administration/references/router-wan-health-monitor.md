# 路由器 WAN 健康监控（间歇性掉线取证）

场景：用户报"网速测起来挺快但游戏一卡一卡、过会儿直接掉线又恢复"，且现场排查（连续 ping、tcpdump、PPPoE 检查）全部正常——**因为测试窗口撞上了稳定期**。此时不要反复现场排查，部署守株待兔式监控，等下次掉线留痕。

## 部署（2026-08-19 已在用户路由器落地）

### 1. 路由器侧 netmon.sh（每 2 分钟 cron）

部署到 `/usr/bin/netmon.sh`（iStoreOS 无 python3，纯 sh 脚本）：

```sh
#!/bin/sh
# netmon.sh - 周期性掉线监控 (部署于路由器 /usr/bin/netmon.sh)
# 每2分钟由cron执行，记录网络健康数据，检测掉线/丢包事件
LOG="/tmp/netmon.log"
STATE="/tmp/netmon_wan_uptime"
EVENT_LOG="/tmp/netmon_events.log"

NOW=$(date '+%Y-%m-%d %H:%M:%S')

# 1. PPPoE uptime（掉线重连会变小）
WAN_UP=$(ifstatus wan 2>/dev/null | grep -o '"uptime": [0-9]*' | awk '{print $2}')
[ -z "$WAN_UP" ] && WAN_UP=0

# 2. WAN IP（重拨会变）
WAN_IP=$(ifstatus wan 2>/dev/null | grep -o '"address": "[0-9.]*"' | head -1 | awk -F'"' '{print $4}')

# 3. 丢包/延迟（3个ping包，轻量）
PING_RESULT=$(ping -c 3 -W 2 203.0.113.1 2>/dev/null | grep -E 'packet loss|min/avg/max')
PING_LOSS=$(echo "$PING_RESULT" | grep -oE '[0-9]+% packet loss' | grep -oE '^[0-9]+')
PING_AVG=$(echo "$PING_RESULT" | grep -oE 'min/avg/max[ =/0-9.]+' | grep -oE '/[0-9.]+/' | tr -d '/')
[ -z "$PING_LOSS" ] && PING_LOSS="-1"
[ -z "$PING_AVG" ] && PING_AVG="-1"

# 4. 负载
LOAD=$(cat /proc/loadavg | awk '{print $1}')
# 5. conntrack
CT=$(cat /proc/sys/net/netfilter/nf_conntrack_count 2>/dev/null)

# ========== 事件检测 ==========
EVENT=""
# 检测PPPoE重连: 上次uptime > 本次uptime 且上次>0
PREV_UP=0
[ -f "$STATE" ] && PREV_UP=$(cat "$STATE" 2>/dev/null)
if [ "$PREV_UP" -gt 0 ] && [ "$WAN_UP" -lt "$PREV_UP" ]; then
    EVENT="PPPoE_RECONNECT prev_uptime=${PREV_UP}s now_uptime=${WAN_UP}s ip=${WAN_IP}"
    echo "$NOW $EVENT" >> "$EVENT_LOG"
fi
echo "$WAN_UP" > "$STATE"

# 检测丢包
if [ "$PING_LOSS" != "-1" ] && [ "$PING_LOSS" -gt 0 ]; then
    EVENT="${EVENT:+$EVENT; }PACKET_LOSS ${PING_LOSS}% avg=${PING_AVG}ms"
    echo "$NOW $EVENT" >> "$EVENT_LOG"
fi

# 检测延迟飙升
if [ "$PING_AVG" != "-1" ]; then
    AVG_INT=$(echo "$PING_AVG" | cut -d. -f1)
    if [ "$AVG_INT" -gt 200 ] 2>/dev/null; then
        EVENT="${EVENT:+$EVENT; }HIGH_LATENCY ${PING_AVG}ms"
        echo "$NOW $EVENT" >> "$EVENT_LOG"
    fi
fi

# ========== 记录 ==========
echo "$NOW uptime=${WAN_UP}s ip=${WAN_IP} loss=${PING_LOSS}% avg=${PING_AVG}ms load=${LOAD} ct=${CT}${EVENT:+ EVENT:$EVENT}" >> "$LOG"

# 保持日志大小
tail -3000 "$LOG" > "${LOG}.tmp" 2>/dev/null && mv "${LOG}.tmp" "$LOG"
```

部署命令：
```bash
scp -P 2222 netmon.sh root@192.0.2.10:/usr/bin/netmon.sh
ssh -p 2222 root@192.0.2.10 "chmod +x /usr/bin/netmon.sh; echo '*/2 * * * * /usr/bin/netmon.sh >/dev/null 2>&1' >> /etc/crontabs/root"
```

### 2. Hermes 侧 check_netmon.py（每 30 分钟 no_agent cron）

存 `~/.hermes/scripts/check_netmon.py`，创建 no_agent cron（`every 30m`，脚本名 `check_netmon.py`）——**健康时静默零输出，有异常事件才推送**，用户不被打扰、不耗 token。

```python
#!/usr/bin/env python3
"""路由器网络健康检查 - 读取 /tmp/netmon.log 和 /tmp/netmon_events.log
发现异常事件(PPPoE重连/丢包/高延迟)时输出告警；正常时静默。"""
import subprocess, sys, re

ROUTER = "root@192.0.2.10"
PORT = "2222"

def ssh_cat(path):
    try:
        r = subprocess.run(
            ["ssh", "-p", PORT, "-o", "ConnectTimeout=8", "-o",
             "StrictHostKeyChecking=no", "-o", "BatchMode=yes",
             ROUTER, "cat", path],
            capture_output=True, text=True, timeout=25)
        # rc=1 且 stderr 含 No such file = 文件不存在，视为空
        if r.returncode != 0 and "No such file" in r.stderr:
            return ""
        return r.stdout if r.returncode == 0 else None
    except Exception:
        return None

events = ssh_cat("/tmp/netmon_events.log")
if events is None:
    print("⚠️ 路由器SSH连接失败，无法读取监控日志")
    sys.exit(0)

event_lines = [l for l in events.strip().splitlines() if l.strip()]
if event_lines:
    print("🚨 路由器网络异常事件：")
    for l in event_lines[-8:]:
        print(l)
    sys.exit(0)

log = ssh_cat("/tmp/netmon.log")
if log:
    lines = [l for l in log.strip().splitlines() if l.strip()]
    if lines:
        latest = lines[-1]
        m = re.search(r"loss=([0-9-]+)%", latest)
        if m and m.group(1) not in ("0", "-1"):
            print(f"⚠️ 路由器当前丢包异常：{latest}")
            sys.exit(0)
sys.exit(0)
```

## 掉线后如何定位

| 事件 | 含义 | 指向 |
|------|------|------|
| `PPPoE_RECONNECT prev_uptime=X now_uptime=Y` | 掉线重连 | 光猫/运营商线路断 → 找联通 |
| `PACKET_LOSS >0%` 且 uptime 正常 | 线路抖动 | 光功率波动/OLT 问题 → 查光猫 |
| `HIGH_LATENCY >200ms` | 路径劣化 | 运营商路由/游戏服务器 |
| 一切正常但游戏卡 | 无 WAN 异常 | 设备侧/游戏服务器路径 → 查 PC、代理劫持（`references/openclash-game-direct-rules.md`） |

## 坑

- **测试窗口撞上稳定期是常态**：用户说"刚才掉线"时你连测 100 次 ping 可能全通——不要下"没问题"结论，挂监控等下次。
- Hermes cron no_agent 脚本的 SSH 必须带 `BatchMode=yes`（无交互），且 `-p` 紧跟 ssh 后。
- `cat` 不存在的文件返回 rc=1，脚本要识别 "No such file" 视为空，否则误报 SSH 失败。
- 路由器日志在 `/tmp`（tmpfs），重启路由器会清空——监控重启后重新积累，属正常。
