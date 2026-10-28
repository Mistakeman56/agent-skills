# MCP Web Scraping 工具替代矩阵

当 webclaw（或同类工具）因 fake-IP / SSRF 防护无法工作时，按以下优先级替换。

## 推荐度排序

### ⭐⭐⭐⭐⭐ mcp_fetch_fetch（已内置，首选）
- **类型**: Hermes 内置 MCP 工具，零安装
- **用法**: `mcp_fetch_fetch(url="https://...", max_length=5000)`
- **代理**: 走系统 HTTP_PROXY 代理，不做 DNS 层 IP 校验
- **优势**: 无 fake-IP 冲突，已部署可用，返回 clean text
- **实测**: GitHub、Rust Blog、Hacker News（部分）等外网站点均通
- **限制**: robots.txt 限制的站点（如 news.ycombinator.com）会拒绝

### ⭐⭐⭐ Jina Reader（⚠️ 中国不通）
- **类型**: HTTP API，免费
- **用法**: `curl "https://r.jina.ai/https://目标URL"` → 返回 LLM 优化的 markdown
- **⚠️ 致命问题**: `r.jina.ai` 托管在 Cloudflare（203.0.113.1, 203.0.113.1），**SSRDOG 机场代理节点被 Cloudflare 拒绝 TLS 握手**，从中国无法访问
- **本地 MCP**: `jina-mcp-tools`（npm）两条内部路径：优先直连 → 回退 `r.jina.ai`，回退路径不可用
- **自部署**: 需 Docker + Puppeteer（headless Chrome），资源消耗大
- **结论**: 当前环境下不可用，仅当有非 Cloudflare 代理或自部署时考虑

### ⭐⭐⭐ Firecrawl MCP (⭐6263)
- **类型**: 云 SaaS + 可自部署
- **官方 MCP**: `firecrawl/firecrawl-mcp-server`
- **免费**: 500 credits/月
- **功能**: scrape → clean markdown, crawl → 整站爬取, search → 网页搜索
- **代理**: 云服务自带出口，无需本地代理
- **自部署**: 可通过 Docker 部署 `firecrawl/firecrawl`（需要 Redis + Playwright）

### ⭐⭐⭐ open-websearch (已部署)
- **已在 LXC 200 运行**
- **fetch 能力**: 走代理 OK，适合快速抓取
- **限制**: 内容提取不如 webclaw/Jina 干净

### ⭐⭐⭐ Browserbase MCP
- **类型**: 云无头浏览器
- **优势**: JS 渲染，过反爬
- **劣势**: 需 API key，付费

### ⭐⭐ Puppeteer MCP
- **类型**: 自部署无头 Chrome
- **优势**: 完全本地控制，JS 渲染
- **劣势**: 同理 fake-IP 坑；需要 Chrome 运行时，资源消耗大

### ⭐⭐⭐⭐⭐ Bright Data MCP (⭐2,355) — 最强免费方案但需翻墙注册

- **类型**: Cloud MCP（搜索 + 抓取 + 反封锁 一体化）
- **npm**: `@brightdata/mcp` v2.9.5（内部含 Playwright）
- **免费层**: **5000 次/月**（超过其他所有免费 API 的 5-10 倍）
- **免费工具**: `search_engine` (Google 质量搜索), `scrape_as_markdown` (任意网页→Markdown), `discover` (AI 排序深度搜索), `search_engine_batch`, `scrape_batch`
- **反封锁**: 企业级 Web Unlocker（7200 万 IP 池），不触发验证码，不被限速
- **接入**: 托管模式 URL `https://mcp.brightdata.com/mcp?token=YOUR_TOKEN` 零安装；本地 `npx @brightdata/mcp`
- **Cloudflare 阻断问题**: brightdata.com 网站本身托管在 Cloudflare，从中国直连极慢。注册需要 Google OAuth（React SPA），**无法用 curl 自动化**。用户必须给浏览器设代理 `192.0.2.10:7890` 才能完成注册。
- **结论**: 功能上碾压所有免费方案（5000次/月 vs 竞品 500-1000次），但注册门槛高。一旦拿到 token，是 Hermes 搜索/抓取的首选工具。

## 决策树

```
需要抓外网网页 (GFW 后)
  ├─ 只需提取内容 → mcp_fetch_fetch (内置，最快)
  ├─ 需要搜索+抓取 → open-websearch 搜索 + mcp_fetch_fetch 抓取
  ├─ 需要整站爬取 → Firecrawl (云) 或自部署 Jina Reader (需 Docker)
  ├─ 需要 JS 渲染 → Browserbase (云) 或 Puppeteer + redir-host
  └─ 不想依赖云服务 → mcp_fetch_fetch 或自部署 Jina Reader
```

## 当前环境实测结果 (2026-05-10)

| 工具 | GitHub | Rust Blog | HN | Google | 说明 |
|------|:--:|:--:|:--:|:--:|------|
| mcp_fetch_fetch | ✅ | ✅ | ❌ | ✅ | robots.txt 拒 HN，其余通 |
| open-websearch fetch | ❌ | ❌ | — | — | fake-IP 冲突 |
| Jina (r.jina.ai) | ❌ | ❌ | ❌ | ❌ | Cloudflare 拒绝 TLS |
| webclaw | ❌ | ❌ | — | — | 已删除，fake-IP 冲突 |
