#!/bin/sh
# 路由器侧并行抖动/丢包取证（busybox 兼容）
# 用法: N=40 sh lat_jitter_check.sh 203.0.113.1 203.0.113.1
#      不给参数时只测 PPPoE 对端网关
# 注意: busybox ping 的 -i 只接受整数秒，不要写 0.2
OUT=/tmp/lat_check.txt
N=${N:-40}
INT=${INT:-1}
[ $# -gt 0 ] || set -- $(ip route show default | awk '{print $3; exit}')
: > $OUT
for ip in "$@"; do
  ( ping -c "$N" -i "$INT" -W 1 "$ip" 2>/dev/null > /tmp/lat_"$ip".raw ) &
done
wait
{
  printf '%-18s %-6s %-6s %-7s %-24s %s\n' 目标 发送 收到 丢包 '最小/平均/最大(ms)' '抖动(相邻差均值,ms)'
  for ip in "$@"; do
    f=/tmp/lat_"$ip".raw
    rtt=$(sed -n 's#.*round-trip min/avg/max = \(.*\) ms.*#\1#p' "$f" 2>/dev/null)
    loss=$(sed -n 's#.*, \([0-9]*\)% packet loss.*#\1#p' "$f" 2>/dev/null)
    recv=$(grep -c 'time=' "$f" 2>/dev/null)
    jit=$(grep -o 'time=[0-9.]*' "$f" 2>/dev/null | cut -d= -f2 | awk '{if(NR>1){d=$1-p; if(d<0)d=-d; s+=d; n++} p=$1} END{if(n>0) printf "%.2f", s/n}')
    [ -n "$jit" ] || jit=n/a
    printf '%-18s %-6s %-6s %-7s %-24s %s\n' "$ip" "$N" "${recv:-0}" "${loss:-?}%" "${rtt:-无响应}" "$jit"
  done
} | tee -a $OUT
