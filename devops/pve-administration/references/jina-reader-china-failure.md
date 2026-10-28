# Jina Reader 中国不可用 — 故障记录

日期: 2026-05-10
环境: LXC 200, 软路由 OpenClash SSRDOG 机场 (日本节点), fake-IP 模式

## 故障链

```
1. jina-mcp-tools 调用 r.jina.ai
2. r.jina.ai DNS → Clash fake-IP 198.18.0.106
3. 走 HTTPS_PROXY 代理隧道 (CONNECT r.jina.ai:443)
4. 代理隧道建立成功 (HTTP/1.1 200 Connection established)
5. TLS Client Hello 发出
6. SSL_ERROR_SYSCALL — Cloudflare 拒绝连接
```

## r.jina.ai 真实信息

- 托管: Cloudflare
- 真实 IP: 203.0.113.1, 203.0.113.1, 203.0.113.1
- 通过 Google DNS 验证: `curl "https://dns.google/resolve?name=r.jina.ai&type=A"`
- 从软路由器本身也无法连接（说明不是 LXC 问题，是机场被 Cloudflare 封）

## jina-mcp-tools 内部路径

源码 (src/reader.ts):
1. 先尝试 `Accept: text/markdown` 直连目标站 → 大多数站点不支持
2. 失败后 POST `https://r.jina.ai/` (硬编码) → 被 Cloudflare 拦截
3. 无自定义 endpoint 配置项

## 自部署可行性

Jina Reader 开源 (github.com/jina-ai/reader, ⭐10781):
- 需要 Docker + docker compose
- 依赖 Puppeteer (headless Chrome) → 资源消耗大
- LXC 200 可能扛不住，建议放软路由 (J4125) 或 PVE 另建 VM

## 验证过的替代方案

| 方案 | 状态 | 备注 |
|------|:--:|------|
| mcp_fetch_fetch | ✅ 可用 | 走 HTTP 代理，无 fake-IP 冲突 |
| Firecrawl MCP (云) | ✅ 理论可用 | 需 API key，云出口不受 GFW 影响 |
| 自部署 Jina | ⚠️ 待评估 | 需 Docker 资源 |
| open-websearch fetch | ❌ | fake-IP 冲突 |

## 教训

在 GFW + Cloudflare 双重封锁下：
1. 任何托管在 Cloudflare 的外部 API 都应先做连通性测试再集成
2. 不要假设"免费 API = 一定可用"
3. 自部署方案比云方案更可控（但需要资源）
4. 失败后立即止损，不要反复重试——浪费 token
