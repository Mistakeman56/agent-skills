#!/bin/sh
# 10台互森设备监控 - MAC自动发现版
# 部署到 iStoreOS: scp -P 2222 devmon-script-mac-discovery.sh root@192.0.2.10:/usr/bin/devmon.sh
# 需要先在路由器上创建 nftables 表和链（见 istoreos-network-monitoring.md）

DATADIR="/tmp/devmon"
mkdir -p "$DATADIR"

NOW=$(date +%s)
TODAY=$(date +%Y-%m-%d)
TIMESTR=$(date +%H:%M:%S)

# 设备MAC地址（硬件固定，不会变）
# 替换为你自己的设备 MAC
MACS="00:00:00:00:00:00 00:00:00:00:00:00 00:00:00:00:00:00 00:00:00:00:00:00 00:00:00:00:00:00 00:00:00:00:00:00 00:00:00:00:00:00 00:00:00:00:00:00 00:00:00:00:00:00 00:00:00:00:00:00"

# 从DHCP表查MAC对应的IP
# ⚠️ DHCP租约表字段: $1=expiry $2=MAC $3=IP $4=hostname $5=client-id
find_ip_by_mac() {
    local target_mac=$(echo "$1" | tr "A-F" "a-f")
    while IFS= read -r line; do
        mac=$(echo "$line" | awk '{print tolower($2)}')
        ip=$(echo "$line" | awk '{print $3}')
        if [ "$mac" = "$target_mac" ]; then
            echo "$ip"
            return 0
        fi
    done < /tmp/dhcp.leases
    return 1
}

# 确保nftables规则匹配当前IP（IP变了就自动更新）
ensure_rules() {
    nft list chain inet devmon ingress_monitor >/dev/null 2>&1 || \
        nft add chain inet devmon ingress_monitor "{ type filter hook ingress priority -15 ; policy accept ; }"
    nft list chain inet devmon postrouting_monitor >/dev/null 2>&1 || \
        nft add chain inet devmon postrouting_monitor "{ type filter hook postrouting priority -15 ; policy accept ; }"

    for mac in $MACS; do
        ip=$(find_ip_by_mac "$mac")
        [ -z "$ip" ] && continue
        ip_last=$(echo "$ip" | cut -d. -f4)

        nft list counter inet devmon "c_${ip_last}_up" >/dev/null 2>&1 || \
            nft add counter inet devmon "c_${ip_last}_up" 2>/dev/null
        nft list counter inet devmon "c_${ip_last}_down" >/dev/null 2>&1 || \
            nft add counter inet devmon "c_${ip_last}_down" 2>/dev/null

        nft list chain inet devmon ingress_monitor 2>/dev/null | grep -q "192.0.2.$ip_last" || \
            nft add rule inet devmon ingress_monitor ip saddr 192.0.2.$ip_last counter name "c_${ip_last}_up" 2>/dev/null
        nft list chain inet devmon postrouting_monitor 2>/dev/null | grep -q "192.0.2.$ip_last" || \
            nft add rule inet devmon postrouting_monitor ip daddr 192.0.2.$ip_last counter name "c_${ip_last}_down" 2>/dev/null
    done
}

ensure_rules

# 读取上次快照（计算差值用）
if [ -f "$DATADIR/counters.json" ]; then
    PREV_DATA=$(cat "$DATADIR/counters.json")
else
    PREV_DATA=""
fi

# 开始构建JSON
OUT="{\"ts\":$NOW,\"date\":\"$TODAY\",\"time\":\"$TIMESTR\",\"devices\":["
FIRST=1

for mac in $MACS; do
    ip=$(find_ip_by_mac "$mac")
    if [ -z "$ip" ]; then
        [ "$FIRST" -eq 1 ] && FIRST=0 || OUT="${OUT},"
        OUT="${OUT}{\"ip\":\"unknown\",\"mac\":\"$mac\",\"on\":0,\"tu\":0,\"td\":0,\"du\":0,\"dd\":0}"
        continue
    fi

    ip_last=$(echo "$ip" | cut -d. -f4)
    # BusyBox兼容：用 grep + awk 替代 grep -oP
    up=$(nft list counter inet devmon "c_${ip_last}_up" 2>/dev/null | grep "bytes" | awk "{print \$2}")
    down=$(nft list counter inet devmon "c_${ip_last}_down" 2>/dev/null | grep "bytes" | awk "{print \$2}")
    up=${up:-0}
    down=${down:-0}

    ping -c 1 -W 1 "$ip" >/dev/null 2>&1
    [ $? -eq 0 ] && online=1 || online=0

    prev_up=$(echo "$PREV_DATA" | grep -o "\"u${ip_last}\":[0-9]*" | cut -d: -f2)
    prev_down=$(echo "$PREV_DATA" | grep -o "\"d${ip_last}\":[0-9]*" | cut -d: -f2)
    prev_up=${prev_up:-0}
    prev_down=${prev_down:-0}

    du=$((up - prev_up))
    dd=$((down - prev_down))
    [ "$du" -lt 0 ] && du=0
    [ "$dd" -lt 0 ] && dd=0

    [ "$FIRST" -eq 1 ] && FIRST=0 || OUT="${OUT},"
    OUT="${OUT}{\"ip\":\"$ip\",\"mac\":\"$mac\",\"on\":${online},\"tu\":${up},\"td\":${down},\"du\":${du},\"dd\":${dd}}"
done

OUT="${OUT}]}"

# 保存计数器快照
SNAP="{"
FIRST=1
for mac in $MACS; do
    ip=$(find_ip_by_mac "$mac")
    [ -z "$ip" ] && continue
    ip_last=$(echo "$ip" | cut -d. -f4)
    up=$(nft list counter inet devmon "c_${ip_last}_up" 2>/dev/null | grep "bytes" | awk "{print \$2}")
    down=$(nft list counter inet devmon "c_${ip_last}_down" 2>/dev/null | grep "bytes" | awk "{print \$2}")
    [ "$FIRST" -eq 1 ] && FIRST=0 || SNAP="${SNAP},"
    SNAP="${SNAP}\"u${ip_last}\":${up:-0},\"d${ip_last}\":${down:-0}"
done
SNAP="${SNAP}}"
echo "$SNAP" > "$DATADIR/counters.json"

echo "$OUT" > "$DATADIR/latest.json"
echo "$OUT" >> "$DATADIR/log-${TODAY}.jsonl"

echo "$OUT"
