#!/bin/sh
# iPhone流量监控脚本 - BusyBox兼容版 (iStoreOS实测)
# 用法: iphone_monitor.sh start/stop/status
# 部署: scp -P 2222 iphone_monitor.sh root@192.0.2.10:/usr/bin/

TARGET_IP="${1:-192.0.2.10}"
LOG_DIR="/mnt/sata1-4/iphone_debug"
PID_DIR="/var/run"

start() {
    if [ -f "$PID_DIR/iphone_monitor.pid" ]; then
        PID=$(cat "$PID_DIR/iphone_monitor.pid")
        if kill -0 "$PID" 2>/dev/null; then
            echo "已在运行 (PID: $PID)"
            return 1
        fi
    fi

    mkdir -p "$LOG_DIR"
    rm -f "$PID_DIR"/iphone_monitor_*.pid

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 启动流量监控 [$TARGET_IP] -> $LOG_DIR"

    # 1. OpenClash TCP连接日志 (awk替代grep --line-buffered)
    tail -f -n0 /tmp/openclash.log 2>/dev/null | awk -v ip="$TARGET_IP" '$0~ip{print; fflush()}' > "$LOG_DIR/openclash_tcp.log" &
    echo $! > "$PID_DIR/iphone_monitor_oc.pid"

    # 2. OpenClash错误日志
    tail -f -n0 /tmp/openclash.log 2>/dev/null | awk -v ip="$TARGET_IP" '
        $0~ip && ($0~"error" || $0~"timeout" || $0~"reject" || $0~"fail" || $0~"dial") {
            print; fflush()
        }' > "$LOG_DIR/openclash_errors.log" &
    echo $! > "$PID_DIR/iphone_monitor_err.pid"

    # 3. QUIC拦截计数器监控 (每10秒检查)
    (
        PREV=0
        while true; do
            CURR=$(nft list ruleset 2>/dev/null | awk '/QUIC REJECT/{for(i=1;i<=NF;i++) if($(i-1)=="packets") print $i}')
            CURR=${CURR:-0}
            if [ "$CURR" != "$PREV" ] && [ "$PREV" != "0" ]; then
                DIFF=$((CURR - PREV))
                echo "[$(date '+%Y-%m-%d %H:%M:%S')] QUIC拦截: +${DIFF}包 (总计: $CURR)" >> "$LOG_DIR/nftables_quic.log"
            fi
            PREV=$CURR
            sleep 10
        done
    ) &
    echo $! > "$PID_DIR/iphone_monitor_nft.pid"

    # 4. DNS查询日志
    uci set dhcp.@dnsmasq[0].logqueries='1' 2>/dev/null
    uci commit dhcp 2>/dev/null
    /etc/init.d/dnsmasq restart 2>/dev/null
    sleep 2

    tail -f -n0 /tmp/log/dnsmasq.log 2>/dev/null | awk -v ip="$TARGET_IP" '$0~ip{print; fflush()}' > "$LOG_DIR/dns_queries.log" &
    echo $! > "$PID_DIR/iphone_monitor_dns.pid"

    tail -f -n0 /var/log/messages 2>/dev/null | awk '
        /dnsmasq/ && /query/ && /'"$TARGET_IP"'/ {
            print; fflush()
        }' >> "$LOG_DIR/dns_queries.log" &
    echo $! > "$PID_DIR/iphone_monitor_dns2.pid"

    # 5. tcpdump抓包 (HTTPS+QUIC，每小时轮转，保留6个文件=6小时)
    nohup tcpdump -i br-lan host "$TARGET_IP" and \( port 443 or port 80 \) \
        -w "$LOG_DIR/packets.pcap" -G 3600 -W 6 2>/dev/null &
    echo $! > "$PID_DIR/iphone_monitor_dump.pid"

    PIDS=$(cat "$PID_DIR"/iphone_monitor_*.pid 2>/dev/null | tr '\n' ' ')
    echo "$PIDS" > "$PID_DIR/iphone_monitor.pid"

    echo "监控已启动:"
    echo "  日志目录: $LOG_DIR"
    echo "  采集: TCP连接 / 错误 / QUIC拦截 / DNS / tcpdump"
    echo "  停止: iphone_monitor.sh stop"
}

stop() {
    if [ -f "$PID_DIR/iphone_monitor.pid" ]; then
        for f in "$PID_DIR"/iphone_monitor_*.pid; do
            [ -f "$f" ] && kill $(cat "$f") 2>/dev/null
        done
        rm -f "$PID_DIR"/iphone_monitor_*.pid "$PID_DIR/iphone_monitor.pid"
        echo "监控已停止"
    else
        echo "未在运行"
    fi

    uci delete dhcp.@dnsmasq[0].logqueries 2>/dev/null
    uci commit dhcp 2>/dev/null
    /etc/init.d/dnsmasq restart 2>/dev/null

    echo "日志保留在: $LOG_DIR"
}

status() {
    if [ -f "$PID_DIR/iphone_monitor.pid" ]; then
        echo "监控运行中"
        echo "日志:"
        ls -lh "$LOG_DIR" 2>/dev/null
    else
        echo "未在运行"
    fi
}

case "$1" in
    start)  shift; TARGET_IP="${1:-$TARGET_IP}"; start ;;
    stop)   stop ;;
    status) status ;;
    *)      echo "用法: $0 {start [IP]|stop|status}" ;;
esac
