#!/bin/sh
# 家网「卡了 / 慢了」一键状态取证（**只读**，不改任何配置）
#
# 为什么需要它：见 references/home-network-outage-forensics.md 的「测量陷阱」。
# 一句话 —— ①和②必须分开测（路由器本机 curl 不走透明代理）；瞬时快照不算证据，nft 累计 counter 才算。
#
# 用法（scp 到路由器后在本机跑）：
#   scp -P 2222 net-layer-probe.sh root@<router>:/tmp/
#   ssh -p 2222 root@<router> 'CLASH_SECRET=xxx sh /tmp/net-layer-probe.sh'
# CLASH_SECRET 可省略：①②③④⑤⑥⑦ 仍会跑完，只是不查代理组/规则/日志。

SECRET="${CLASH_SECRET:-}"
API="http://127.0.0.1:9090"
WAN="pppoe-wan"

if [ ! -e "/sys/class/net/$WAN/statistics/rx_bytes" ]; then
  WAN="eth0"
  echo "  (pppoe-wan 不存在，改用 eth0 采样)"
fi

echo "════ ① 出口直连（--noproxy 明确绕代理）════"
curl -s --noproxy '*' -o /dev/null -m 10 -w "  百度    %{http_code} / %{time_total}s\n" https://www.baidu.com/

echo ""
echo "════ ② 代理链路（必须经代理端口；路由器本机 curl 不走透明代理）════"
curl -s -o /dev/null -m 12 -x http://127.0.0.1:7890 -w "  google  %{http_code} / %{time_total}s   （期望 204）\n" https://www.google.com/generate_204
curl -s -o /dev/null -m 12 -x http://127.0.0.1:7890 -w "  youtube %{http_code} / %{time_total}s   （期望 200）\n" https://www.youtube.com/

echo ""
echo "════ ③ 软路由负载（排除硬件瓶颈）════"
cat /proc/loadavg
free -m 2>/dev/null | head -2
echo "  （load 长期 <0.5 且内存有余 = 路由器不是瓶颈）"

echo ""
echo "════ ④ WAN 实时吞吐（采样 5s）════"
r1=$(cat /sys/class/net/$WAN/statistics/rx_bytes 2>/dev/null)
t1=$(cat /sys/class/net/$WAN/statistics/tx_bytes 2>/dev/null)
sleep 5
r2=$(cat /sys/class/net/$WAN/statistics/rx_bytes 2>/dev/null)
t2=$(cat /sys/class/net/$WAN/statistics/tx_bytes 2>/dev/null)
echo "  下载 $(( (r2-r1)*8/5/1000000 )) Mbps    上传 $(( (t2-t1)*8/5/1000000 )) Mbps"
echo "  （远低于线路上限 = 链路空闲，别拿「带宽被占满」当解释）"

echo ""
echo "════ ⑤ nft 关键规则 + 累计 counter（路径活没活，看这个）════"
nft list ruleset 2>/dev/null | grep -E 'QUIC REJECT|SNIFF|tproxy ip to|DNS Hijack' | head -10
echo "  （QUIC REJECT = udp dport 443 ip daddr != @china_ip_route：只打非中国真实 IP）"
echo "  （counter 在涨 = 该路径在承载流量；为 0 才值得怀疑）"

echo ""
echo "════ ⑥ OpenClash 关键开关 ════"
uci show openclash 2>/dev/null | grep -E 'enable_udp_proxy|disable_udp_quic|enable_redirect_dns|fakeip|enable_tun'
echo "  （uci 改了 ≠ 生效：这些要 reload 才落地，会变成「已提交未生效」的哑弹）"

echo ""
echo "════ ⑦ DNS 分流抽样 ════"
for d in www.baidu.com aweme.snssdk.com www.google.com; do
  echo "  $d → $(nslookup $d 127.0.0.1 2>/dev/null | grep -A1 'Name:' | grep Address | tail -1 | awk '{print $2}')"
done
echo "  （国内域名期望真 IP；被墙域名期望 198.18.x.x）"
echo "  （国内域名也拿到 198.18.x.x = 走了 fake-ip；需要时加 fake-ip-filter 让它直连）"

if [ -n "$SECRET" ]; then
  echo ""
  echo "════ ⑧ 代理组 / 规则 / 日志（需要 CLASH_SECRET）════"
  curl -s -m 10 -H "Authorization: Bearer $SECRET" "$API/proxies/Auto" | tr ',' '\n' | grep -E '"now"|"alive"' | head -4
  echo -n "  规则总数: "
  curl -s -m 10 -H "Authorization: Bearer $SECRET" "$API/rules" | grep -o '"type":"[A-Za-z]*"' | wc -l
  echo "  最近日志:"
  tail -8 /tmp/openclash.log 2>/dev/null | sed 's/^/    /'
else
  echo ""
  echo "════ ⑧ 跳过（未提供 CLASH_SECRET）════"
fi

echo ""
echo "════ ⑨ 怎么读这份结果 ════"
echo "  ① 通 = 出口健康；② 通 = 代理链路健康。"
echo "  两边都通、面板/内网测速也都正常，却在某个 App 里卡 →"
echo "  别再改代理配置，转 references/openclash-douyin-tiktok-ruleset.md 的「三层都做完仍卡」一节，"
echo "  最后用「手机 Wi-Fi vs 手机流量」的对照实验交给用户定界。"
