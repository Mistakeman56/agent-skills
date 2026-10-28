# 网络测速工具故障 vs 真实带宽（2026-08-19 实测证据链）

场景：用户报"下行测速不到 1M、上行 80M 正常、波动极大（1000M↔0.4M）"，且 OpenClash 已关闭、光猫已重启。最终结论：**宽带/链路/路由器全正常，是 speedtest 工具自身故障**。

## 完整排查证据表

| 测试 | 结果 | 结论 |
|---|---|---|
| 路由器 curl 清华源 38MB | 33-39 MB/s（267Mbps+）连续6次零波动 | 链路正常 |
| 路由器 curl 华为云 | 17 MB/s（140Mbps） | 正常 |
| 路由器 ping 阿里 DNS 203.0.113.1 | 100/100 通，18ms，抖动 0.148ms | 零丢包 |
| PPPoE uptime | 稳定增长（3242s→3466s 无重连） | 连接稳定 |
| conntrack | 1424/262144 未满 | 正常 |
| 防火墙/nftables | 无残留 789x 劫持、无 QoS 限速 | 干净 |
| PC wegame 下载 | **100MB/s+**（用户实测） | 千兆满速 |
| **路由器 speedtest CLI** | **0.3-0.6M 下载 / 90M 上行** | ❌ 工具故障 |

## 根因：speedtest CLI 配置获取失败 + 坏服务器选择

1. `speedtest` 启动时报 `Configuration - Timeout was reached` / `Cannot retrieve configuration document` → 从 Ookla API 获取服务器列表失败
2. 只剩本地缓存的一个坏服务器 **JSQY - Suzhou (id 16204)**，实际 IP `203.0.113.1` = **腾讯云香港**
3. 该服务器 8080/443 测速端口从联通网络**连不通**（80 端口通，返回 404）
4. speedtest 一直选它 → 下载 0.36M，但上行走通 → 90M
5. IPv6 陷阱：`curl -6 https://www.speedtest.net` HTTP:000（0.02s 即失败），IPv4 通 → speedtest 优先 IPv6 时配置获取必挂

## 另一个常见假象：跨运营商 QoS

- 联通宽带测到**移动** speedtest 服务器（如 203.0.113.1）：下行被掐到 <1M，上行正常
- 不是设备问题，是联通→移动跨网 QoS
- 解法：选同运营商服务器，或用国内镜像/游戏下载实测

## 正确验证命令（路由器 iStoreOS 上）

```bash
# 多源镜像测速（清华最快，华为/阿里次之）
curl -s --noproxy '*' -o /dev/null -w '%{speed_download}\n' http://mirrors.tuna.tsinghua.edu.cn/ubuntu/ls-lR.gz
curl -s --noproxy '*' -o /dev/null -w '%{speed_download}\n' http://mirrors.huaweicloud.com/ubuntu/ls-lR.gz
curl -s --noproxy '*' -o /dev/null -w '%{speed_download}\n' http://mirrors.aliyun.com/ubuntu/ls-lR.gz

# 连续采样看波动（每5秒一次）
for i in 1 2 3 4 5 6; do
  V=$(curl -s --noproxy '*' -m 5 -o /dev/null -w '%{speed_download}' http://mirrors.tuna.tsinghua.edu.cn/ubuntu/ls-lR.gz)
  echo "[$(date +%H:%M:%S)] $V B/s"
  sleep 5
done

# 测速服务器实际连通性（8080 是 speedtest 默认测速端口）
curl -s --noproxy '*' -m 5 -o /dev/null -w 'HTTP:%{http_code} 速度:%{speed_download}B/s\n' \
  'http://<server-ip>:8080/speedtest/random350x350.jpg'
# HTTP:000 = 测速端口不通 → 该服务器不可用，别让它当测速结果

# 用户侧铁证：wegame/Steam 下载、联通官方 https://speed.10010.com
```

## 用户偏好（本次实测）

- 用户最终用 wegame 下载 100MB/s 判定"网络没问题"，明确说"先不管路由器了 我终端能有网就行"——**测速工具显示慢时，先多源验证真实带宽，再下"网络坏了"的结论**
- 用户报"波动大/卡顿"时优先看游戏 UDP 连接（conntrack UNREPLIED / sport=7892 代理劫持），别只看 ICMP ping
- 间歇性问题：测试窗口可能撞上稳定期，别急着说"没问题"，建议挂监控等下次掉线取证

## 关联

- Tailscale MagicDNS 接管路由器 DNS 的修复（同一会话发现）：`tailscale set --accept-dns=false`，详见 SKILL.md 对应 pitfall
- 游戏流量被代理劫持的完整排查：`references/openclash-game-direct-rules.md`
