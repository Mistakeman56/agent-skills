# SSRDOG 节点延迟测试（大连联通实测数据）

## 背景

2026-05-22 对家中 OpenClash（SSRDOG 机场）的节点进行了全面延迟和可达性测试，为 APTV 到货做准备。

## 认证发现

OpenClash 7890 mixed-port 需要 Basic Auth。正确的认证方式是 `http://Clash:hrFM183F@192.0.2.10:7890`。

找到认证信息的方法：
```bash
ssh root@192.0.2.10 "uci show openclash | grep -E 'password|secret|auth'"
```

Dashboard API 在 9090 端口，用 Bearer token `<PASSWORD>` 访问。

## 节点测试方法

```bash
# 用 Dashboard API 测特定节点延迟
curl -s -H "Authorization: Bearer <PASSWORD>" \
  "http://192.0.2.10:9090/proxies/$(python3 -c \"import urllib.parse; print(urllib.parse.quote('🇯🇵 Japan丨01'))\")/delay?timeout=5000&url=https%3A%2F%2Fwww.gstatic.com%2Fgenerate_204"

# 批量测试
for i in 1 2 3 4 5; do
  node="🇯🇵 Japan丨0${i}"
  encoded=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$node'))")
  curl -s -H "Authorization: Bearer <PASSWORD>" \
    "http://192.0.2.10:9090/proxies/$encoded/delay?timeout=5000&url=https%3A%2F%2Fwww.gstatic.com%2Fgenerate_204"
done
```

## 实测数据

### 各区域节点延迟

| 地区 | 节点 | 延迟(ms) | 状态 |
|------|------|:--------:|:----:|
| 🇯🇵 日本 | Japan丨01 | 68-70 | ✅ 最优 |
| 🇯🇵 日本 | Japan丨03 | 70-78 | ✅ 良好 |
| 🇯🇵 日本 | Japan丨04 | 69-88 | ✅ 可用 |
| 🇯🇵 日本 | Japan丨02 | 278-287 | ⚠️ 偏高 |
| 🇯🇵 日本 | Japan丨05 | 272-291 | ⚠️ 偏高 |
| 🇭🇰 香港 | Hong Kong丨02 | 108 | ✅ 可用 |
| 🇭🇰 香港 | Hong Kong丨03 | 73 | ✅ 良好 |
| 🇭🇰 香港 | Hong Kong丨04 | 84 | ✅ 可用 |
| 🇭🇰 香港 | Hong Kong丨05 | 85 | ✅ 可用 |
| 🇭🇰 香港 | Hong Kong丨01 | ERR | ❌ 错误 |
| 🇸🇬 新加坡 | Singapore丨01 | 65 | ✅ 最佳延迟 |
| 🇺🇸 美国 | United States丨01 | 81 | ✅ 可用 |
| 🇰🇷 韩国 | South Korea丨01 | 70 | ✅ 可用 |
| Auto 组 | 自动选择 | 72 | ✅ 自动选日本 |

### 代理出口检测

| 检测站 | 出口IP | 说明 |
|--------|--------|------|
| ip.sb | 203.0.113.1 | 国内IP（规则直连） |
| ifconfig.me | 203.0.113.1 | 国内IP（规则直连） |
| httpbin.org/ip | 203.0.113.1 | 国内IP（规则直连） |
| icanhazip.com | 203.0.113.1 | 国内IP（规则直连） |

**关键认知：** 出口显示国内IP但 Google/YouTube/ChatGPT 全部能通（200响应）——这是 Clash 规则分流正常的表现。代理出口检测站被 Clash 规则匹配为直连，真正的翻墙流量通过规则匹配（YouTube→SSRDOG组→日本节点）走代理。

### YouTube 实测

| 指标 | 值 |
|------|:---:|
| HTTP 状态 | 200 |
| 响应时间 | ~1.1-2.1s |
| CDN | Google 全球 CDN（alt-svc: h3） |

### IPTV 源验证

使用 203.0.113.1:808/hls 作为主力源，CCTV1-16 全部可达，延迟~0.2s。

之前使用的 203.0.113.1:9901 源已失效。

## 结论

1. 日本节点（Japan丨01, 68ms）是综合最优选择
2. Auto 组自动选择日本节点，无需手动切换
3. 新加坡节点延迟最低（65ms），可作为 YouTube 4K 时的备选
4. 代理总体质量良好，适合 APTV 观看直播
