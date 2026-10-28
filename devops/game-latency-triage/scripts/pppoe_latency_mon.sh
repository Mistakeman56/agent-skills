#!/bin/sh
# 路由器侧（OpenWrt/busybox）对局延迟采样。
# 用法：heredoc 灌到路由器 /root/ 下，chmod +x，然后 /etc/crontabs/root 加一行
#   * * * * * /root/pppoe_latency_mon.sh
# 幂等：pidfile + kill -0，cron 每分钟拉起也只保留一个实例。
#
# 采集内容（仅当该 PC 有 UDP 活动时才写，避免空转写盘）：
#   cake pk_delay/av_delay/backlog、pppoe tx_bytes、网关/游戏服 RTT、PC 的 UDP 会话
# 日志：/tmp/lol_mon.log（>2MB 自动截断到尾部 800KB）

PC_IP=${PC_IP:-192.0.2.10}
GAME_IP=${GAME_IP:-203.0.113.1}   # 对局服 IP，打一局后从五元组里取真实值
INTERVAL=${INTERVAL:-5}
LOG=${LOG:-/tmp/lol_mon.log}
PIDF=${PIDF:-/tmp/lol_mon.pid}

[ -f "$PIDF" ] && kill -0 "$(cat "$PIDF")" 2>/dev/null && exit 0
echo $$ > "$PIDF"

IF=pppoe-wan
[ -d "/sys/class/net/$IF" ] || IF=$(ip route show default | awk '{print $5; exit}')
GWM=$(ip route show default | awk '{print $3; exit}')

while true; do
  TS=$(date '+%m-%d %H:%M:%S')
  # 只看 dport>=5000 的 UDP（对局端口），排除 53/1900/3478 等噪声
  G=$(awk -v ip="$PC_IP" '/udp/ && index($0, "src=" ip) {for(i=1;i<=NF;i++) if($i ~ /^dport=/){split($i,a,"="); if(a[2]+0>=5000) print}}' \
        /proc/net/nf_conntrack 2>/dev/null | head -5)
  if [ -n "$G" ]; then
    D=$(tc -s qdisc show dev "$IF" 2>/dev/null | awk '/pk_delay|av_delay|backlog/{printf "%s=%s ",$1,$2}')
    TX=$(cat "/sys/class/net/$IF/statistics/tx_bytes" 2>/dev/null)
    PG=$(ping -c 1 -W 1 "$GWM" 2>/dev/null | awk -F'time=' '/time=/{split($2,a," ");print a[1]}')
    P1=$(ping -c 1 -W 1 "$GAME_IP" 2>/dev/null | awk -F'time=' '/time=/{split($2,a," ");print a[1]}')
    echo "### $TS tx=$TX gw=${PG}ms game=${P1}ms $D" >> "$LOG"
    echo "$G" | sed 's/^/    /' >> "$LOG"
  fi
  SZ=$(wc -c < "$LOG" 2>/dev/null || echo 0)
  [ "$SZ" -gt 2000000 ] && tail -c 800000 "$LOG" > "$LOG.n" && mv "$LOG.n" "$LOG"
  sleep "$INTERVAL"
done
