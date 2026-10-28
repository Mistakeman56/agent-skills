#!/bin/sh
# 宽带/链路吞吐采样（iStoreOS 路由器，纯 sh + awk，不需 python3）
#
# 用法：scp 到路由器后执行
#   scp -P 2222 wan-throughput-sample.sh root@192.0.2.10:/tmp/
#   ssh -p 2222 root@192.0.2.10 'sh /tmp/wan-throughput-sample.sh 10; rm -f /tmp/wan-throughput-sample.sh'
# 参数：采样轮数（每轮 2 秒），默认 10 = 20 秒
#
# 输出：各口协商速率 / br-lan 成员 / 分口实时吞吐(Mbps) / CPU与中断 / flowtable 状态

N=${1:-10}

IFACES="pppoe-wan eth0 eth1 eth2 eth3"

speed_of() {
    p=/sys/class/net/$1
    [ -d "$p" ] || return
    sp=$(cat $p/speed 2>/dev/null)
    [ -z "$sp" ] && sp="-"
    echo "  $1: operstate=$(cat $p/operstate 2>/dev/null) carrier=$(cat $p/carrier 2>/dev/null) ${sp}Mb/s duplex=$(cat $p/duplex 2>/dev/null)"
}

# 采一轮：$1=接口  $2=轮数
probe() {
    IF=$1; RND=$2
    prev=$(grep " $IF" /proc/net/dev 2>/dev/null | awk '{print $2+0, $10+0}')
    [ -z "$prev" ] && { echo "  $IF: 未找到，跳过"; return; }
    echo "  --- $IF ---"
    i=1
    while [ "$i" -le "$RND" ]; do
        sleep 2
        cur=$(grep " $IF" /proc/net/dev 2>/dev/null | awk '{print $2+0, $10+0}')
        prx=$(echo "$prev" | cut -d' ' -f1); ptx=$(echo "$prev" | cut -d' ' -f2)
        crx=$(echo "$cur"  | cut -d' ' -f1); ctx=$(echo "$cur"  | cut -d' ' -f2)
        # bytes/2s -> Mbps: bytes * 8 / 2 / 1e6 = bytes * 4 / 1e6
        rx=$(awk "BEGIN{printf \"%.1f\", ($crx-$prx)*8/2000000}")
        tx=$(awk "BEGIN{printf \"%.1f\", ($ctx-$ptx)*8/2000000}")
        echo "    +$((i*2))s  下行 ${rx} Mbps   上行 ${tx} Mbps"
        prev=$cur
        i=$((i+1))
    done
}

echo "════ 1. 各口协商速率 ════"
for x in 0 1 2 3 4 5; do speed_of eth$x; done
speed_of pppoe-wan
echo "  pppoe-wan mtu: $(cat /sys/class/net/pppoe-wan/mtu 2>/dev/null)"
echo "  WAN IP: $(ip -4 addr show pppoe-wan 2>/dev/null | grep -o 'inet [0-9.]*' | head -1)"

echo ""
echo "════ 2. br-lan 成员 ════"
ls /sys/class/net/br-lan/brif/ 2>/dev/null | sed 's/^/  /'

echo ""
echo "════ 3. 分口实时吞吐（每口 $N 轮 ×2s）════"
for IF in $IFACES; do
    probe "$IF" "$N"
done

echo ""
echo "════ 4. CPU / 中断 ════"
top -bn1 2>/dev/null | grep -E "^%?Cpu|^CPU:" | head -3 | sed 's/^/  /'
grep -E "eth[0-9]|pppoe" /proc/interrupts 2>/dev/null | sed 's/^/  /'

echo ""
echo "════ 5. offload 状态 ════"
lsmod 2>/dev/null | grep -i offload | sed 's/^/  /' || echo "  (无 offload 模块)"
if nft list ruleset 2>/dev/null | grep -q flowtable; then
    echo "  flowtable: 已配置"
else
    echo "  flowtable: 空 —— software flow offload 没接上"
fi
uci show firewall 2>/dev/null | grep -iE "offload|fullcone" | sed 's/^/  /'

echo ""
echo "════ 6. 提示 ════"
 echo "  · 数字一路下降时先确认负载是否已结束/换档，别读成限速"
 echo "  · 各口差不多 → LAN 不是瓶颈 → 查代理用户态转发（openclash-fakeip-throughput-penalty.md）"
 echo "  · 协商速率只代表这一跳能力，不等于套餐带宽"
