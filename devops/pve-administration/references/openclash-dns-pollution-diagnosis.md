# OpenClash 域名超时：区分 DNS 污染 vs clash 配置问题（2026-09 实测）

## 场景
用户报告"路由器/某设备访问某个国内域名（如 miwifi.com）超时"，但其他国内域名正常。
典型：`/tmp/openclash.log` 报 `dial DIRECT (match RuleSet/ChinaMax) xxx.com:443 error: dial tcp IP1:443: i/o timeout; dial tcp IP2:443: i/o timeout`。
家里几十个米家设备依赖小米服务器，这类超时会影响智能家居联动。

## 诊断框架（按顺序，避免误判）

### 0. 先排除"clash 把国内都代理了"
```bash
curl -s --connect-timeout 4 -o /dev/null -w "baidu HTTP:%{http_code} 连接:%{time_connect}s\n" https://www.baidu.com
```
- HTTP:200 + 连接 0.06s → 国内直连正常，**排除**整个网络被代理/路由坏了 → 问题锁定在**特定域名/IP**
- HTTP:000 → 是国内整体被劫持，不是单域名问题（走 openclash-dns-mode-decision 或 MATCH 检查）

### 1. ⚠️ 关键反直觉洞察：curl 打裸 IP 测连通性是"假阴性"
这是最坑的一步。**对 HTTPS 域名打裸 IP（`curl https://203.0.113.1`）几乎必然返回 HTTP:000**——
因为 HTTPS 需要带正确 SNI + 匹配证书，裸 IP 连**任何**网站都会失败（连百度的裸 IP 都失败）。
**不要用裸 IP 的 HTTP:000 判断"网络不通"！**

```bash
# ❌ 错误的对比（会误判为网络问题）
curl -s https://203.0.113.1   # HTTP:000 —— 这是 SNI/证书问题，不是网络不通！
# ✅ 正确的对比（域名+SNI）
curl -s https://www.baidu.com   # HTTP:200 —— 走 clash 直连正常
curl -s https://目标域名          # HTTP:000 —— 真问题
curl -s --resolve 目标域名:443:IP https://目标域名   # 指定IP+SNI，测目标IP是否真通
```

### 2. 确诊 DNS 污染：双重对比法
DNS 污染 = 路由器 DNS 解析出**被污染/不可达的 IP**（尤其运营商线路到该 IP 被拦截），而干净 resolver 解析出**正常 IP**。

**对比 A：不同 resolver 的解析结果**
```bash
# 路由器本地 DNS 给的 IP
nslookup miwifi.com 2>&1 | grep Address        # 可能给: 203.0.113.1 / 203.0.113.1

# 从 Hermes 服务器（不同网络出口）用干净 resolver
# Python: requests.get("https://dns.google/resolve?name=miwifi.com&type=A")
# Google DNS 可能给: 203.0.113.1 / 203.0.113.1  ← 和路由器 DNS 给的完全不同 = 被污染
```

**对比 B：用不同网络出口测"被污染 IP 是否真不可达"**
```bash
# 从路由器 curl 被污染 IP（走SNI）→ 超时
curl -s --resolve 目标域名:443:203.0.113.1 https://目标域名   # HTTP:000 超时

# 从 Hermes 服务器（广域网出口）测同一 IP 的 443
# Python: socket.create_connection(("203.0.113.1", 443), timeout=5) → 成功！
# 从外部能连、从路由器连不上 = 该 IP 在运营商路径被拦截；而它根本不是正常 IP
```

**判定：** 路由器 DNS 给出的 IP ≠ 干净 resolver 给出的 IP，且该 IP 从别的出口能连、从本路由器的 WAN 连不上 → **DNS 污染**（本运营商到此 IP 的 443 被拦），不是 clash 问题、不是路由问题、不是该域名挂了。

### 3. 顺带验证"设备真正依赖的服务器域名"是否健康
```bash
# 米家设备真正连的 API 域名（不是 miwifi.com）——从别的出口测
requests.get("https://api.io.mi.com", verify=False)  # HTTP 404 = 服务器活着（404 是正常路由层响应）
# 注意：HTTPS 服务返回 404 证明 TCP/TLS 通了；连接级失败才是不通
```

## 关键结论
1. **`curl` 打裸 IP 的 HTTP:000 是 SNI 假象，不是网络不通** —— 这是本次排查最省时间的洞察。
2. **对比 DNS resolver 结果 + 跨出口测 IP** = 确诊 DNS 污染的可靠方法。
3. 确诊污染后，修复方向是**给该域名固定正确 IP 走直连**（hosts/规则），或**换干净 DNS 源**——但正确 IP 可能变动，需先确认当前有效值再动手。**不要**猜一个 IP 就写死。

## 工具提示（iStoreOS BusyBox）
- `nc -z -w` **不支持**，busybox nc 只认 `nc IP PORT`（且测试结果不可靠，见下）
- busybox nc 测试结果经常全"FAIL"（与 curl 结果矛盾），**别信 nc，用 curl 裁决**
- 路由器无 python3，需爬多行 JSON 时把文件 scp 到有完整工具链的机器处理
- `diff` 等工具缺失，需对比时 scp 到 PVE/本机
