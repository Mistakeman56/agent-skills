# AI Agent Web 访问 — 行业技术方案

> 完整报告: `~/.hermes/hermes-agent/reports/how-ai-agents-access-web.md`

## 一句话总结

**没有人自己裸爬。** 全行业都用专用的云 API 服务（Firecrawl/Tavily/Exa）来突破反爬，这些服务背后是浏览器集群 + 住宅代理池 + CAPTCHA 解决。

## 核心玩家速查

| 服务 | 类型 | 定价 | 适用场景 | 从中国可用性 |
|------|------|:--:|------|:--:|
| **Firecrawl** | 全栈抓取 API | 免费层/付费 | 页面抓取、整站爬取、JS 渲染 | ✅ 云服务自带出口 |
| **Tavily** | AI 搜索 API | 免费 1000/月 | 实时搜索+内容提取，p50 180ms | ✅ 云服务自带出口 |
| **Exa** | 语义搜索 API | 免费层/付费 | 嵌入语义搜索（非关键词） | ✅ 云服务自带出口 |
| **Browserbase** | 浏览器即服务 | 付费 | 登录/填表/交互/验证码 | ✅ 云服务自带出口 |
| **Bright Data MCP** | 搜索+抓取+反封锁 MCP | 免费5000次/月 | 搜索/抓取/发现一体化，MCP 原生 | ✅ **直连可用** |
| **Jina Reader** | 免费读页 API | 免费 | LLM 优化的 markdown 提取 | ❌ Cloudflare 封锁 |
| **Puppeteer MCP** | 自部署浏览器 | 免费 | 本地 JS 渲染 | ⚠️ 需解决 fake-IP |

## 技术栈层级

```
L1: DNS/网络       ← 代理/隧道 (我们有 ✅)
L2: TLS 指纹       ← wreq/BoringSSL 伪装 (webclaw 有，其他没有)
L3: JS 渲染        ← Playwright/Puppeteer (我们缺 ❌)
L4: 浏览器指纹     ← 随机化 UA/分辨率/时区 (我们缺 ❌)
L5: IP 信誉        ← 住宅代理轮换 (机场 IP 信誉低 ⚠️)
L6: CAPTCHA        ← 自动识别 (我们缺 ❌)
L7: 内容解析       ← HTML → Markdown (我们有 ✅)
```

## 对 Hermes 的建议

1. **已接入**: Bright Data MCP — 搜索+抓取+反封锁一套，5000次/月免费，直连无需代理，MCP 原生。配置在 `~/.hermes/config.yaml` 的 `mcp_servers.brightdata`。
2. **备用搜索**: Tavily API（免费 1000次/月）如需不同搜索源
3. **自部署**: Firecrawl Docker 自建（需 Redis + Playwright）如需无限量抓取
4. **国内站深度访问**: 自建 Playwright + puppeteer-extra-stealth（低频需求）
