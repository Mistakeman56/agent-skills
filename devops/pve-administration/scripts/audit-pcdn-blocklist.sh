#!/bin/sh
# 审计 PCDN 黑洞名单：把「名字像播放链路」的条目挑出来（这些不该被黑）
# 用途：每次改完黑洞清单后跑一遍。它拦的是「分类错误」这类静默故障 ——
#      这种错误不报错，只表现为用户某天突然说「XX 又卡了 / 直播黑屏」。
# 用法（在软路由上）：sh audit-pcdn-blocklist.sh

LIST=/etc/openclash/custom/openclash_custom_hosts.list

if [ ! -f "$LIST" ]; then
  echo "找不到 $LIST —— 这个脚本要在软路由上跑（OpenClash 的 custom hosts 列表）"
  exit 1
fi

# 无回答时不要回显 DNS 服务器那一行（BusyBox 会输出 Address: 127.0.0.1:53）
res() {
  nslookup "$1" 127.0.0.1 2>&1 | awk '/^Name:/{f=1} f&&/^Address/{a=$2} END{print (a=="" ? "(无解析)" : a)}'
}

echo "=== 黑洞总条数: $(grep -c '127.0.0.1' "$LIST") ==="
echo ""
echo "=== ⚠ 高危：名字含 live/rtmp/flv/pull/push/hls 且不含 p2p/peer/chunk 的条目 ==="
echo "    （这些是播放/推拉流链路，误黑 = 直播黑屏、短视频卡）"
grep -nEi "live|rtmp|flv|pull|push|hls" "$LIST" | grep -viE "p2p|peer|chunk" || echo "   ✓ 无 —— 名单里没有播放链路域名"
echo ""
echo "=== 应当命中：含 p2p/peer/chunk/stun 的条目数 ==="
grep -cEi "p2p|peer|chunk|stun" "$LIST"
echo ""
echo "=== 抽查 PCDN 家族（期望 127.0.0.1）==="
for d in p2p.douyucdn.cn www.ppio.com cdn.xycdn.com test.onething.com; do
  printf "  %-24s %s\n" "$d" "$(res "$d")"
done
echo ""
echo "=== 播放链路对照（必须回真实 IP，出现 127.0.0.1 就是误伤）==="
for d in www.douyin.com v3-web.douyinvod.com www.bilibili.com pull-hs-f5-hot.flive.douyincdn.com; do
  printf "  %-42s %s\n" "$d" "$(res "$d")"
done
echo ""
echo "=== 连通性（改完必须还能上网）==="
curl -s -o /dev/null -m 12 -w "  baidu HTTP=%{http_code}  %{time_total}s\n" https://www.baidu.com
