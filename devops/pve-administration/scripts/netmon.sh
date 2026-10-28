#!/bin/sh
# netmon.sh v2 - 周期性掉线/带宽波动监控 (部署于路由器 /usr/bin/netmon.sh, iStoreOS)
# 每2分钟由cron执行。数据存 /etc/netmon/ 持久目录，路由器重启不丢。
# 检测到掉线/重连/带宽骤降时自动抓取现场证据(logread/接口状态)留痕。
# 部署: scp 到路由器 /usr/bin/netmon.sh + chmod +x + cron: */2 * * * * /usr/bin/netmon.sh >/dev/null 2>&1
DATADIR="/etc/netmon"
mkdir -p "$DATADIR"
LOG="$DATADIR/netmon.log"
STATE="$DATADIR/state"
EVENT_LOG="$DATADIR/events.log"

NOW=$(date '+%Y-%m-%d %H:%M:%S')

# 1. PPPoE uptime（掉线重连会变小）
WAN_UP=$(ifstatus wan 2>/dev/null | grep -o '"uptime": [0-9]*' | awk '{print $2}')
[ -z "$WAN_UP" ] && WAN_UP=0

# 2. WAN IP
WAN_IP=$(ifstatus wan 2>/dev/null | grep -o '"address": "[0-9.]*"' | head -1 | awk -F'"' '{print $4}')

# 3. 丢包/延迟
PING_RESULT=$(ping -c 3 -W 2 203.0.113.1 2>/dev/null | grep -E 'packet loss|min/avg/max')
PING_LOSS=$(echo "$PING_RESULT" | grep -oE '[0-9]+% packet loss' | grep -oE '^[0-9]+')
PING_AVG=$(echo "$PING_RESULT" | grep -oE 'min/avg/max[ =/0-9.]+' | grep -oE '/[0-9.]+/' | tr -d '/')
[ -z "$PING_LOSS" ] && PING_LOSS="-1"
[ -z "$PING_AVG" ] && PING_AVG="-1"

# 4. 负载 & conntrack
LOAD=$(cat /proc/loadavg | awk '{print $1}')
CT=$(cat /proc/sys/net/netfilter/nf_conntrack_count 2>/dev/null)

# 5. 光猫可达性 (桥接模式下常见管理IP 192.0.2.10; 用 ping 确认)
ONU_OK=$(ping -c 1 -W 1 192.0.2.10 >/dev/null 2>&1 && echo yes || echo no)

# 6. 带宽采样（华为云大文件4秒, 测下行带宽波动）——v1 缺这个, 漏掉了真正的病根
BW=$(curl -s --noproxy '*' -m 4 -o /dev/null -w '%{speed_download}' 'http://mirrors.huaweicloud.com/ubuntu/ls-lR.gz' 2>/dev/null)
[ -z "$BW" ] && BW=0
BW_MB=$(awk "BEGIN{printf \"%.1f\", $BW/1048576}")

# ========== 事件检测 ==========
EVENT=""
# PPPoE重连: 上次uptime > 本次uptime 且上次>0
PREV_UP=0
[ -f "$STATE" ] && PREV_UP=$(cat "$STATE" 2>/dev/null)
if [ "$PREV_UP" -gt 0 ] && [ "$WAN_UP" -lt "$PREV_UP" ]; then
    EVENT="PPPoE_RECONNECT prev=${PREV_UP}s now=${WAN_UP}s ip=${WAN_IP}"
fi
echo "$WAN_UP" > "$STATE"

# 丢包
if [ "$PING_LOSS" != "-1" ] && [ "$PING_LOSS" -gt 0 ]; then
    EVENT="${EVENT:+$EVENT; }PACKET_LOSS ${PING_LOSS}% avg=${PING_AVG}ms"
fi

# 高延迟
if [ "$PING_AVG" != "-1" ]; then
    AVG_INT=$(echo "$PING_AVG" | cut -d. -f1)
    if [ "$AVG_INT" -gt 200 ] 2>/dev/null; then
        EVENT="${EVENT:+$EVENT; }HIGH_LATENCY ${PING_AVG}ms"
    fi
fi

# 带宽骤降（<2MB/s 视为异常，正常应>5MB/s）——v1 缺这个, 漏掉了真正的病根
if [ "$BW" -gt 0 ] 2>/dev/null; then
    BW_INT=$(echo "$BW" | cut -d. -f1)
    if [ "$BW_INT" -lt 2097152 ] 2>/dev/null; then
        EVENT="${EVENT:+$EVENT; }BANDWIDTH_DROP ${BW_MB}MB/s"
    fi
fi

# 光猫失联(之前可达现在不可达)
PREV_ONU=""
[ -f "$DATADIR/onu_state" ] && PREV_ONU=$(cat "$DATADIR/onu_state" 2>/dev/null)
if [ "$PREV_ONU" = "yes" ] && [ "$ONU_OK" = "no" ]; then
    EVENT="${EVENT:+$EVENT; }ONU_LOST"
fi
echo "$ONU_OK" > "$DATADIR/onu_state"

# ========== 记录 ==========
echo "$NOW uptime=${WAN_UP}s ip=${WAN_IP} loss=${PING_LOSS}% avg=${PING_AVG}ms bw=${BW_MB}MB/s load=${LOAD} ct=${CT} onu=${ONU_OK}${EVENT:+ EVENT:$EVENT}" >> "$LOG"

# 有事件 → 追加到事件日志 + 抓现场
if [ -n "$EVENT" ]; then
    echo "$NOW EVENT: $EVENT" >> "$EVENT_LOG"
    {
        echo "--- $NOW $EVENT ---"
        logread 2>/dev/null | grep -viE 'dnsmasq|ilinkai|weixin' | tail -15
        ip addr show pppoe-wan 2>/dev/null | grep -E 'inet|state'
    } >> "$DATADIR/crash_$(date +%Y%m%d).log" 2>/dev/null
fi

# 保持日志大小
tail -5000 "$LOG" > "${LOG}.tmp" 2>/dev/null && mv "${LOG}.tmp" "$LOG"
