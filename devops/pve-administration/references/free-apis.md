# 免费 API 资源 — 增加 Hermes 搜索/信息获取能力

> 来源: [public-apis/public-apis](https://github.com/public-apis/public-apis) ⭐433,778  
> 筛选原则: 免费层足够日常使用、无需信用卡、能从中国通过代理访问

## 🔥 零门槛（无需 API key 或极易获取）

| API | 分类 | 免费额度 | 认证 | 用途 |
|-----|------|:--:|:--:|------|
| **Open-Meteo** | Weather | 10000次/天 | **无** | 全球天气预报 |
| **arXiv** | Science | 无限制 | **无** | 学术论文搜索 |
| **Quotable** | Quotes | 无限制 | **无** | 名人名言 |
| **Open Library** | Books | 无限制 | **无** | 图书搜索 |
| **ExchangeRate-API** | Currency | 1500次/月 | apiKey | 汇率转换 |
| **Spaceflight News** | News | 无限制 | **无** | 航天新闻 |
| **Numbers** | Fun | 无限制 | **无** | 数字趣味事实 |

## 📰 新闻类（注册即用）

| API | 免费额度 | 认证 | 特点 |
|-----|:--:|:--:|------|
| **GNews** | 100次/天 | apiKey | 全球新闻搜索，多语言 |
| **Currents** | 600次/天 | apiKey | 实时+历史新闻，多语言 |
| **Mediastack** | 500次/月 | apiKey | 实时新闻 & 博客 |
| **NewsAPI** | 500次/天(dev) | apiKey | 全球新闻头条 |
| **TheNews** | 免费层 | apiKey | 聚合头条 JSON API |

## 🌐 网页抓取 + 搜索（突破反爬）

### 🥇 Bright Data MCP — 已接入 ✅
- **免费层**: **5000 次/月**，搜索 + Markdown 抓取 + AI 排序发现 + 反封锁一体化
- **MCP 原生**: Hermes `config.yaml` 直接 URL 接入，无 wrapper
- **直连可用**: `mcp.brightdata.com` 和 `api.brightdata.com` 不经过 Cloudflare，国内直连无需代理
- **注册**: `brightdata.com` 网站本身托管在 Cloudflare，需浏览器设代理 `192.0.2.10:7890` 完成 Google OAuth 注册。注册后拿 token 即可。
- **备选新闻 API 不再需要** → Bright Data `search_engine` 已覆盖实时新闻搜索（已验证中文搜索结果质量）

### 🥈 其他（免费层远不如 Bright Data）

| API | 免费额度 | 亮点 |
|-----|:--:|------|
| **ScrapingAnt** | 1000次/月 | 无头 Chrome + JS 渲染 |
| **ScrapingDog** | 1000次/月 | 代理 API + JS 渲染 |
| **ZenRows** | 1000次/月 | 自动绕过反爬 + 代理轮换 |
| **WebScraping.AI** | 500次/月 | 内置代理 + JS 渲染 |
| **serpstack** | 100次/月 | Google 搜索结果 JSON |
| **ProxyCrawl** | 1000次/月 | 爬虫代理 |

## 🛠 实用工具

| API | 用途 |
|-----|------|
| **Microlink.io** | 从任何 URL 提取结构化数据（免费） |
| **RSS to JSON** | RSS feed 转 JSON |
| **IPLogs** | 免费检测 VPN/代理/Tor IP |
| **Countries** | ISO 国家代码/货币查询 |

## 💡 接入策略

```
✅ 已接入: Bright Data MCP → 搜索 + 抓取 + 反封锁（5000次/月）
📋 建议补充: Open-Meteo (天气) + arXiv (学术) + ExchangeRate-API (汇率)
📰 新闻: Bright Data search_engine 已覆盖，无需单独接 GNews/Currents 等
```

## ⚠️ 注意事项

- **Bright Data MCP 直连可用**，不需要走软路由代理。其他外网 API 可能需要代理。
- 免费层有速率限制，日常使用足够，批量场景需升级
- 部分 API 注册后获取 key 即可，无需信用卡
- 优先选 `CORS: Yes` 的 API（可从浏览器端调用）
