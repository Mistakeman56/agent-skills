#!/bin/sh
# 准确检测设备在线状态（对比nftables计数器差值）
# 用法: check_device_online.sh [路由器IP] [MAC地址列表]
# 示例: check_device_online.sh 192.0.2.10 "00:00:00:00:00:00 00:00:00:00:00:00"

ROUTER="${1:-192.0.2.10}"
SSH_PORT=2222
MACS="${2:-00:00:00:00:00:00 00:00:00:00:00:00 00:00:00:00:00:00 00:00:00:00:00:00 00:00:00:00:00:00 00:00:00:00:00:00 00:00:00:00:00:00 00:00:00:00:00:00 00:00:00:00:00:00 00:00:00:00:00:00}"

echo "=== 设备在线状态检测 (nftables计数器对比法) ==="
echo "路由器: $ROUTER"
echo "检测间隔: 5秒"
echo ""

# 第一次读取计数器
echo "[1/3] 读取初始计数器..."
SNAP1=$(ssh -p $SSH_PORT -o StrictHostKeyChecking=no -o ConnectTimeout=5 root@$ROUTER "
for mac in $MACS; do
  line=\$(cat /tmp/dhcp.leases | grep \"\$mac\")
  ip=\$(echo \$line | awk '{print \$3}')
  [ -z \"\$ip\" ] && continue
  ip_last=\$(echo \$ip | cut -d. -f4)
  up=\$(nft list counter inet devmon \"c_\${ip_last}_up\" 2>/dev/null | grep bytes | awk '{print \$2}')
  down=\$(nft list counter inet devmon \"c_\${ip_last}_down\" 2>/dev/null | grep bytes | awk '{print \$2}')
  echo \"\$ip_last \${up:-0} \${down:-0}\"
done
" 2>/dev/null)

echo "[2/3] 等待5秒..."
sleep 5

echo "[3/3] 读取第二次计数器并对比..."
ssh -p $SSH_PORT -o StrictHostKeyChecking=no -o ConnectTimeout=5 root@$ROUTER "
for mac in \$MACS; do
  line=\$(cat /tmp/dhcp.leases | grep \"\$mac\")
  ip=\$(echo \$line | awk '{print \$3}')
  [ -z \"\$ip\" ] && { echo \"\$mac  UNKNOWN  无DHCP租约\"; continue; }
  ip_last=\$(echo \$ip | cut -d. -f4)
  up=\$(nft list counter inet devmon \"c_\${ip_last}_up\" 2>/dev/null | grep bytes | awk '{print \$2}')
  down=\$(nft list counter inet devmon \"c_\${ip_last}_down\" 2>/dev/null | grep bytes | awk '{print \$2}')
  up=\${up:-0}; down=\${down:-0}
  
  # ping检测
  ping -c 1 -W 1 \$ip >/dev/null 2>&1 && ping_ok=1 || ping_ok=0
  
  # ARP状态
  arp_state=\$(ip neigh show | grep \"\$ip \" | awk '{print \$NF}')
  
  echo \"\$ip  ping=\$ping_ok  arp=\$arp_state  up=\$up  down=\$down\"
done
" 2>/dev/null

echo ""
echo "判断逻辑:"
echo "  ping通 + 流量增长 = 真在线"
echo "  ping通 + 流量不变 = 假在线（DHCP/ARP缓存，设备已断电）"
echo "  ping不通 = 真离线"
