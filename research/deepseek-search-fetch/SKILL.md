---
name: deepseek-search-fetch
description: "Use when 要中文网页搜索或抓网页正文。ds-web CLI。"
version: 1.0.0
author: Hermes Agent
platforms: [linux]
metadata:
  hermes:
    tags: [search, fetch, deepseek, chinese-web, rag]
---

# DeepSeek 自研搜索 / 抓取引擎

DeepSeek 官方的 Search / Fetch API。**不是软件，不用安装**——纯云端 JSON 接口，用同一个 `DEEPSEEK_API_KEY`（`https://api.deepseek.com`）即可调用。

本机已封装为 `ds-web` CLI（`~/.hermes/bin/ds-web` → `/usr/local/bin/ds-web`），**不注册成 Hermes 工具**，因此不占每轮 API 调用的工具 schema token，用 `terminal` 按需调用。

## 何时用 / 何时不用

**默认搜索走 `web_search`（Exa）**——用户指令，且 Exa 每月 $10 免费额度从不累积，实测月用量只占 10%，用不完。
**默认抓取也走 `web_extract`（Exa `/contents`，$1/1k 页）**——Exa 有抓取功能，中文页面实测很干净。

`ds-web` 是**兜底与补充**，不是首选：

| 场景 | 用 |
|---|---|
| 一般搜索（中英文都行） | `web_search`（Exa）✅ 默认 |
| 一般网页抓正文 | `web_extract`（Exa）✅ 默认 |
| Exa 抓取超时/返回空/报 inaccessible | **`ds-web fetch`** 兜底 ✅ |
| Exa 搜索无结果或结果弱 | **`ds-web search`** 兜底 ✅ |
| 中文政策/分数线/本地资讯/电商，Exa 不中 | `ds-web search`（`site:` 语法准）✅ |
| 知乎 / 微信公众号直接推文 / 需登录页 | **两者都不行** → 用 `browser_exec` 真浏览器 |
| 英文研究、论文、GitHub、语义检索 | `web_search`（Exa）明显更强 |

### 实测对比（2026-10-23）

| 页面 | Exa `/contents` | DeepSeek `/fetch` |
|---|---|---|
| 某民族大学官网 | ✅ 完整含日期 | ✅ 完整，耗时 5275 ms |
| DeepSeek 文档 | ✅ 完整含表格 | ✅ 完整，耗时 239 ms |
| 知乎回答 | ❌ inaccessible | ❌ 404 |
| 微信公众号 | ❌ inaccessible | ❌ 只返回“环境异常，请验证” |

**结论**：普通网页两者相当；知乎/微信是目标站反爬，两边都不能用，必须上 `browser_exec`。Exa 抓取价格 `$1/1k 页`，$10 月度额度等于 **10000 页**，月用量约 50 页，占 0.5%，**没有必要省**。

## 用法

```bash
# 基本搜索（默认 10 条）
ds-web search "某民族大学 085404 复试分数线" --count 5

# 同时拿正文
ds-web search "关键词" --count 3 --content

# 抓单个网页为 Markdown
ds-web fetch "https://example.com/article"

# 原始 JSON（程序化处理）
ds-web search "q" --json
```

支持搜索语法，直接写进 query：`site:github.com`、`-site:xxx.com`、`"精确短语"`、`-排除词`、`lang:zh,en`、`after:2025`、`before:2026-06`。

## 定价（官方文档核实）

| API | 计费 | 价格 |
|---|---|---|
| Search | 每 1,000 次**成功**请求 | 5 元（$0.75） |
| Fetch | 每 1,000 次**成功**请求 | 5 元（$0.75） |

即 **0.005 元/次**。只有 HTTP 200 且产生结果才计费（Search 需 `results` 非空，Fetch 需返回正文）；失败、无结果、超时**不计费**。`count` 不影响价格——一次请求返回 1 条还是 50 条同样收费，**所以宁可选大 count**。

限速（账号级）：Search 100 QPS / Fetch 25 QPS，独立额度。Fetch 另有按目标域名的 QPS 限制。

## 坑

- **Fetch 返回的 markdown 带多余转义**（`\/` `\#` `\-` `\|` `\:`）。CLI 已用 `_unescape_md()` 清理；直接调原始 API 需自己处理。
- **`need_content: false` 时 `content` 未必为空**——文档写"恒为空字符串"，实测某些查询仍返回正文。不要依赖它来省钱。
- **`ds-web ... | head` 会报 BrokenPipeError**——Python 写 stdout 时管道已关。无害，用 `2>/dev/null` 屏蔽或写文件再读。
- **余额接口精度只有 2 位小数**（`GET https://api.deepseek.com/user/balance`），几十次调用看不出扣费，别用它验证单次计费。
- **2026-11-01 起**，通过 DeepSeek Harness / Claude Code / Codex 使用 DeepSeek API 时，Server 端工具调用访问到的 Search/Fetch 将开始按次收费（此前免费）。本机是直连 REST，不受这条影响。

## 返回字段要点

- `rerank_score` 0–3，**≥1.5 = 优质结果**
- `authority` 0–4（-1 未知），**≥3 = 极权威**
- `snippet` 100–200 字符（前端展示用）
- `summary` 600–800 字符（**给模型读这个**）
- `date` UTC RFC3339，`site_name` / `site_icon` 可能为 null

CLI 输出已把 `优质`/`权威` 标成 tag，并优先打印 `summary`。
