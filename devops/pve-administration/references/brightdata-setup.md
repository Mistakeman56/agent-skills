# Bright Data MCP 接入指南

## 已配置状态

- **状态**: ✅ 已接入、已测试、工作中
- **Token**: `42d87708-1193-4cf0-9dd7-201794e2653f`
- **配置位置**: `~/.hermes/config.yaml` → `mcp_servers.brightdata`
- **免费额度**: 5000 次/月 (Rapid Mode)
- **超时设置**: 120s

## 可用工具

| 工具名 | 功能 | 说明 |
|--------|------|------|
| `search_engine` | Web 搜索 | Google 级别搜索质量，支持中文 |
| `scrape_as_markdown` | 网页抓取 | 任意 URL → 干净 Markdown |
| `discover` | AI 排序搜索 | 基于意图的深度搜索 |
| `search_engine_batch` | 批量搜索 | 多关键词并发搜索 |
| `scrape_batch` | 批量抓取 | 多 URL 并发抓取 |

## 网络可达性

| 域名 | 用途 | 国内直连 | 备注 |
|------|------|:--:|------|
| `mcp.brightdata.com` | MCP API 端点 | ✅ | 不经过 Cloudflare 防护 |
| `api.brightdata.com` | REST API | ✅ | 不经过 Cloudflare 防护 |
| `brightdata.com` | 注册/登录网站 | ❌ | Cloudflare 托管，需浏览器代理访问 |

## 注册流程

1. 用户浏览器设代理 `192.0.2.10:7890`
2. 访问 `brightdata.com` → 注册 → Google OAuth 登录
3. 创建 API token（选 **Web Unlocker** 类型）
4. 拿到 token 后填入 config.yaml
5. 重启 Hermes → 自动发现 `mcp_brightdata_*` 工具

## 故障排查

### 工具调用超时（120s）
- 第一次调用可能冷启动，重试即可
- 复杂查询可能超过 30s，timeout 设 120s 是合理的

### "No valid session ID"
- Hermes 的 MCP 客户端应该自动处理 Streamable HTTP session
- 如果持续出现，检查 `pip install --upgrade mcp` 确保 SDK 版本支持 Streamable HTTP

### Token 失效
- 登录 brightdata.com（浏览器设代理）→ Dashboard → API Tokens → 重新生成
