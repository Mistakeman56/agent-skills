---
name: scheduled-briefings
description: Set up automated recurring cron jobs that deliver multi-source daily briefings (GitHub trending, news, project updates) to the user's chat.
---

# Scheduled Briefings

Create cron jobs that aggregate information from multiple sources and deliver them on a schedule (e.g., daily at 9 AM).

## Trigger Conditions

Use when the user asks for:
- "每天早上/每周给我推送..."
- "设个定时任务，每天 X 点..."
- "弄个每日简报/早报..."
- Any request to set up recurring information delivery

## Key Pattern: The Self-Contained Prompt

Cron jobs run in a fresh Hermes session with **no conversation context**. The prompt must be fully self-contained.

### Structure

```
今天/现在是 {{ strftime("%Y年%m月%d日 %A") }}，请生成一份...

## 板块一：XXX
- 用工具A获取XXX
- 如果不可用，用工具B替代

## 板块二：XXX
- 用工具C获取YYY
- 列出前N条

## 要求
- 用中文呈现，微信友好，段落简洁
- 每个板块不能留空，有替代方案
- 开头加一句问候
```
  
### Template Reference

See `references/daily-briefing-template.md` for the full reusable prompt template used for the user's daily 9 AM briefing (Hermes updates + GitHub trending + domestic/international news).

## Key Data Sources (REST API Fallbacks)

When MCP tools are unavailable, use these reliable REST API alternatives. See `references/github-rest-api-fallbacks.md` for full endpoint reference and parsing patterns.

### GitHub Project Updates (Hermes Agent, etc.)

**Recommended approach: Use `execute_code` + `terminal()` with Python parsing inside execute_code**

The `execute_code` tool handles JSON parsing natively and avoids bash quoting issues. Data is fetched via `terminal(command="curl ...")` inside the Python script.

```python
from hermes_tools import terminal
import json

# Issues & PRs via Search API (filters by type and date range)
r = terminal("curl -s 'https://api.github.com/search/issues?q=repo:{owner}/{repo}+updated:>={date}&sort=updated&order=desc&per_page=10'")
data = json.loads(r['output'])
for item in data.get('items', []):
    print(f"#{item['number']} {item['title']} ({item['state']})")

# Commits
r2 = terminal("curl -s 'https://api.github.com/repos/{owner}/{repo}/commits?per_page=10&since={date}T00:00:00Z'")
commits = json.loads(r2['output'])
for c in commits[:10]:
    print(f"{c['sha'][:7]} {c['commit']['author']['name']}: {c['commit']['message'].split(chr(10))[0]}")
```

**Why `execute_code` is preferred over shell `python3 -c`:**

- Shell inline `python3 -c "..."` with f-strings and complex expressions **frequently hits bash quoting errors** (especially with single quotes in f-strings, `chr(10)` newlines, or curly braces)
- `execute_code` runs in a proper Python environment where `from hermes_tools import ...` works, and you can handle errors without bash escaping
- Also avoids GitHub API response truncation (50KB stdout cap on `terminal()` is handled by `execute_code`)

#### Legacy shell approach (works for simple cases)

```bash
# Events (last 24h activity)
curl -s "https://api.github.com/repos/{owner}/{repo}/events?per_page=30"

# Commits
curl -s "https://api.github.com/repos/{owner}/{repo}/commits?per_page=10"

# Issues & PRs (sorted by recent)
curl -s "https://api.github.com/repos/{owner}/{repo}/issues?state=all&sort=updated&direction=desc&per_page=5"

# Closed/merged PRs
curl -s "https://api.github.com/repos/{owner}/{repo}/pulls?state=closed&per_page=5&sort=updated&direction=desc"
```

Parse with `python3 -c "import json, sys; data = json.load(sys.stdin)"`.

⚠️ **Bash quoting trap**: When using inline `python3 -c` with complex f-strings inside the shell command string, you'll hit syntax errors from bash interpreting quotes. Always prefer `execute_code` for multi-line or complex Python processing of API results.

### GitHub Trending (No MCP Fallback)

**Option A: BrightData scrape (most reliable — proven in production)**

Use `mcp_brightdata_scrape_as_markdown` with `url="https://github.com/trending"` — renders the full trending page including repo names, descriptions, star counts, and daily velocity as clean markdown text. Works when both MCP and browser tools are unavailable.

Parse the markdown text for:
- Repo names (lines matching `owner / repo` pattern)
- Descriptions (following lines)
- Star counts and "N stars today" velocity

**Option B: Browser navigation (reliable when available)**
If `browser_navigate` is available, navigate to `https://github.com/trending?since=daily` and extract the repo list from the rendered page snapshot/accessibility tree. This avoids HTML parsing fragility because the browser renders the DOM.

The snapshot returns structured `<article>` elements with:
- `heading` with repo name like `owner / repo`
- `paragraph` with description
- `link "star N"` with star count
- `StaticText "N stars today"` showing daily velocity

Parse from the browser_snapshot text — no need for vision or JS evaluation.

**Option C: Search API**
If browser tools are unavailable, use the **Search API** with a recent date filter:
```python
curl -s "https://api.github.com/search/repositories?q=created:>{3_days_ago}&sort=stars&order=desc&per_page=10"
```
⚠️ This returns repos by creation velocity, not true "trending" (stars/hour). Acceptable when MCP trending tools are absent.

**Option D: Direct curl + regex (validated 2026-08)**

Pure curl parsing of `https://github.com/trending?since=daily` DOES work with the right selectors. Ready-to-run: `scripts/fetch_trending.py` (curl `--noproxy '*'` + stdlib only). The patterns that survive HTML drift:

- Split into blocks: `<article class="Box-row">(.*?)</article>` (re.S flag)
- **Repo link comes from the `<h2>` anchor, NOT the first href in the block** — a `sponsors/<login>` button link appears EARLIER in the article HTML, so `re.findall(r'href="/([^/"]+/[^/"]+)"', block)` returns `sponsors/lyogavin` instead of `lyogavin/airllm`. Correct: `<h2[^>]*>\s*<a[^>]*href="/([^"]+)"` then filter out any repo starting with `sponsors/`.
- Description: `<p[^>]*class="col-9[^"]*"[^>]*>\s*(.*?)\s*</p>` → strip tags + collapse whitespace
- Language: `itemprop="programmingLanguage">([^<]+)<`
- Stars today: `([\d,.]+k?)\s+stars`

If parsing yields 0 articles, the HTML structure drifted again — re-inspect the current page before switching to browser/Search API.

### Tech News — Dedicated AI News Sites (Preferred for AI-specific stories)

#### buildfastwithai.com (Best for AI industry news)

This site publishes daily AI news roundups with 11-13 stories per day, including detailed financial analysis (funding rounds, IPO filings), product launches, regulatory developments, and model releases. Content is well-structured, markdown-accessible via BrightData scrape.

**How to use:** Search for the latest daily roundup. URLs follow pattern like `https://www.buildfastwithai.com/blogs/ai-news-today-may-24-2026`. To find the latest, search BrightData or Google for `"AI News Today"` with the current date.

**Why prefer this over Hacker News for the briefing:**
- AI-specific coverage (not general tech)
- Includes financial data (valuations, revenue, IPO timelines)
- Easily readable via BrightData scrape — no auth wall

#### 中文科技/AI 新闻: eastmoney-mx mx_search + IT之家 RSS (实测 2026-08)

For Chinese-language AI/tech news, two zero-config sources work well:

- **eastmoney-mx `mx_search`** (MCP tool): natural-language query like `今天人工智能 AI 大模型 最新动态 科技新闻` returns dated (YYYY-MM-DD HH:MM), sourced (财联社 / 界面新闻 / 人民日报海外版 / 券商研报), content-rich results — each item carries `title`, a substantial `content` excerpt, and `jumpUrl` to the original article. Ideal for picking 2-3 interesting stories with real substance. Note: results skew financial (券商周报 etc.), so pair it with a general feed for breadth.
- **IT之家 RSS** (`curl -s --noproxy '*' https://www.ithome.com/rss/`): stable full-day feed, `item` titles + `pubDate` (GMT). Parse with `xml.etree.ElementTree`, keep items from the last 24h. Good for general tech headline scanning.

Both worked without API keys or auth. Use when BrightData / HN are unavailable or for Chinese-language coverage.

### BrightData Tools: Known Failure Modes

The BrightData MCP tools (`search_engine`, `discover`, `scrape_as_markdown`) each have failure patterns worth knowing.

| Tool | Failure Mode | Frequency | Fallback |
|------|-------------|-----------|----------|
| `search_engine` | `Unexpected non-JSON response from Bright Data for search_engine` | Occasionally on `google` engine | Switch to `discover` tool (same query, different engine) |
| `search_engine` | Empty result / no output | Common when query terms are too generic (e.g., just "AI news") | Use more specific queries with date constraints |
| `scrape_as_markdown` | Returned empty string `""` for a known-accessible URL | Common on news sites (TechCrunch, Ars Technica, Reuters, The Verge) | Use `discover` to find specific article links, or navigate with browser instead |
| `discover` | All good — most reliable tool | Rare issues | Best general fallback |

**Rule of thumb:** When building a cron prompt that relies on BrightData, always include a fallback path. If one BrightData tool fails, try another. If all BrightData tools fail for a particular source, fall back to HN Algolia API or browser navigation.

### Hacker News Sources (Fallback)

#### Algolia API (Front Page in One Call — Preferred)

Returns the current front page with titles, URLs, points, comment counts, and authors in a **single call**:

```bash
curl -s 'https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=15'
```

Parsing in Python (use subprocess+curl, NOT urllib — see proxy pitfall below):
```python
import json, subprocess
r = subprocess.run(
    ['curl', '-s', '--noproxy', '*', 'https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=15'],
    capture_output=True, text=True
)
data = json.loads(r.stdout)
for hit in data['hits']:
    print(f"[{hit['points']} pts] {hit['title']}")
```

No auth, no rate limiting. See `references/hacker-news-algolia-api.md` for full details, response format, and pitfall notes.

#### Single-call Redirect Wrapper (Fallback)

```bash
curl -s "https://api.hackerwebapp.com/news" | python3 -m json.tool
```

Returns titles, URLs, points, comments, `time_ago` strings (instead of timestamps). Same underlying data.

#### Official Firebase API (Last Resort — Two Calls Per Story)

```python
# Step 1: Get top story IDs
curl -s "https://hacker-news.firebaseio.com/v0/topstories.json?print=pretty"

# Step 2: Fetch each story individually (N calls for N stories)
curl -s "https://hacker-news.firebaseio.com/v0/item/{story_id}.json?print=pretty"
```

**AI-specific filtering:** After fetching top stories, filter client-side by title keywords (AI/LLM/robot/ML/model).

### WeChat-friendly Formatting
- Keep paragraphs to 2-3 lines max
- Use emojis sparingly for visual breaks
- Code blocks with backticks render fine in WeChat
- Bold section headers help scanning

## Content Generation Guidelines

When generating the briefing content itself (not just setting up the cron), follow these user preferences:

### Structure (3 sections)
1. **Project Updates** — Recent commits, releases, and active issues/PRs for the target repo
2. **GitHub Trending** — 3-5 hottest repos today, one-sentence intro each
3. **Tech News** — 2-3 most interesting tech/AI stories

### Tone & Style
- **Relaxed but not exaggerated** — like sharing with a friend, not a news anchor
- **Chinese language** — 用中文呈现
- **Concise** — short paragraphs, no walls of text
- **Closing** — end with an encouraging sentence or small humor to start the day

### Length Control
- GitHub Trending: 3-5 items max, not Top 10
- Tech News: 2-3 items max, pick the most interesting ones
- Each item: 1 sentence intro, avoid long summaries

## Timezone Handling

**Critical**: Hermes servers typically run in UTC. Chinese users (UTC+8) need schedule adjustment.

**Pre-check**: BEFORE creating any cron job, run `date +%Z` to verify the server timezone, and `date` to see current time. If the server says UTC but your user is in Beijing/Shanghai timezone, convert ALL times.

| User's local time | UTC cron expression |
|---|---|
| 9:00 AM (北京) | `0 1 * * *` |
| **8:30 AM (北京)** | **`30 0 * * *`** |
| 8:00 AM (北京) | `0 0 * * *` |
| **7:00 AM (北京)** | **`0 23 * * *`** (前一天的 UTC) |
| 7:00 PM (北京) | `0 11 * * *` |

**工作日限定:** 标准 cron 用 `0-4` (周日~周四 UTC) = 周一~周五北京时：
- 北京周一~周五 7AM = UTC 周日~周四 23:00 → `0 23 * * 0-4`

Formula: **UTC = 北京时间 - 8小时**. 北京 7:00 = UTC 前一天 23:00.
验证: `date +%Z && timedatectl status | grep "Time zone"`

## Delivery to Third Party (不是推送给本人)

当简报目标不是当前对话用户（如推送给家人）时：

**不要用 `deliver` 参数** — 推送对象的 bot 会话与本机 Hermes 网关的 bot 不同，直接 deliver 发不到对方微信。

**正确做法（V3 架构，当前方案）：用 SQLite 发送队列**

1. 在 cron prompt 中指示 agent 将内容写入 SQLite 的 `send_queue` 表
2. 第三方有一个独立的中继进程（mom_bot_relay.py）持续消费队列并发送
3. relay 使用独立的持久 HTTP 会话（与收消息共享同一个 aiohttp session）

写入方法（Python）：
```bash
python3 -c "
from mom_bot_db import *
db = get_db()
db.execute('INSERT INTO send_queue (text, created_at) VALUES (?, ?)',
  ('早安消息内容', datetime.now().isoformat()))
db.commit()
db.close()
"
```

详见 `references/mom-morning-briefing.md` 和 mom-memory skill 的 V3 架构说明。

### 旧版 JSONL 方案（已废弃，但可能仍有遗留任务使用）

```bash
echo '{"text": "消息内容"}' >> ~/.hermes/mom_send_queue.jsonl
```

## No-Agent 监控（看门狗模式）

对于需要**定期检查、变化才推送**的监控场景（余额、状态、价格等），用 no_agent 脚本 + cron 实现零 LLM 成本的看门狗：

```bash
hermes cron create "余额监控" \
  --schedule "every 30m" \
  --script "watchdog.py" \
  --no-agent --deliver origin
```

关键逻辑：脚本内做值比较 + 文件缓存，变化才 stdout，不变静默退出。cron 只把非空 stdout 推送给用户。

详见 `references/no-agent-watchdog.md`。

## 盯变化（`monitor_script`，有变化才唤醒 agent）

当需求是「**常驻挂着、闲着不烧 token，但变化后要 agent 判断/加工**」时用 `monitor_script`，
不要用 `no_agent`（脚本没有判断力）。用户明确表达过这个偏好。

- 纪律、骨架、调度陷阱（`30m` 会被当成一次性任务，必须写 `every 30m`）→ `references/monitor-script-zero-token.md`
- 盯**模型仓**（Hugging Face / Civitai：新基座、量化、LoRA、无审查变体）→ `references/model-registry-watching.md`

## Using MCP Tools in Cron Briefings

Cron jobs have access to all configured MCP tools — **but only if `enabled_toolsets` is not blocking them**.

### ⚠️ CRITICAL: enabled_toolsets blocks MCP tools

MCP tools (eastmoney, amap, simple-rag, etc.) are **not** part of any named toolset like `"web"` or `"terminal"`. They are loaded separately from config.yaml's `mcp_servers` section.

**If you set `enabled_toolsets: ["web"]` or `["web", "terminal"]` on a cron job, ALL MCP tools will be invisible to that cron session.** The job will run, fail to find MCP tools, and produce a broken result — with no obvious error message.

**Fix:** To give a cron job access to MCP tools, either:
1. **Omit `enabled_toolsets` entirely** (loads all default tools + MCP) — best when the job legitimately needs web + file + MCP
2. **Set `enabled_toolsets: []`** (explicitly no restriction) — same effect as omitting
3. Only set `enabled_toolsets` when you are certain the cron needs exactly those toolsets and NO MCP tools

**Example — correct for MCP-dependent crons:**
```python
# This cron needs eastmoney MCP → NO enabled_toolsets restriction
hermes cron create "A股盘前分析" \\
  --schedule "30 0 * * 1-5" \\
  --deliver weixin
# No --toolsets flag at all
```

**Example — MCP not needed, safe to restrict:**
```python
# This cron only needs web tools → safe to restrict
hermes cron create "每日早报" \\
  --schedule "0 0 * * *" \\
  --deliver weixin \\
  --toolsets web
# Only web tools loaded, much leaner
```

### When MCP tools are available

Cron sessions automatically discover registered MCP tools:

- **天气:** 用 Amap MCP (`mcp_amap_maps_weather`) 获取城市实时天气
- **路况:** 用 BrightData search_engine (NOT fetch/Baidu) 搜索实时交通信息
- **地图:** 用 Amap 查位置、规划路线
- **搜索:** 用 BrightData (`mcp_brightdata_brightdata_invoke_tool` with `search_engine`) 进行网络搜索 — 比 fetch/Baidu 更可靠，可绕过 robots.txt 限制返回结构化结果。**用户明确要求:** "你用那个bright搜，别用百度"
- **文档:** 用 Context7 查技术文档
- **交易:** 用 eastmoney MX MCP 查行情/交易

在 cron prompt 中直接写工具名即可（如 `使用 eastmoney-mx 的 mx_stock_simulator_balance 查询持仓`），cron session 会自动发现已注册的 MCP 工具。

Load the relevant skill(s) that the cron prompt will need access to:
- `github` — if the prompt uses GitHub MCP (releases, commits, trending)
- `mcp` — if the prompt relies on specific MCP tools

⚠️ **Skills may be missing**: If a listed skill (e.g. `github`) is not found in the library, the cron job will still run but the agent must use fallback methods (browser navigation or REST API) instead of skill-dependent tools.

## 审计现有 Cron Job 的 Token 消耗

用户通常关心的不是理论值，而是**实际在跑的任务烧了多少 token**。

### 审计方法

```bash
# 1. 列出所有 cron jobs
hermes cron list
# 2. 查看每个任务的输出文件大小
ls -la ~/.hermes/cron/output/<job_id>/
# 3. 检查文件大小 → 估算输出 token（约 4 chars = 1 token）
# 4. 区分三类任务
```

### 三类任务 & 消耗特征

| 类型 | 特征 | Token 消耗 |
|------|------|------------|
| **全 Agent 跑** | 加载 skill + MCP 工具 + 多轮调用 | **~5-12K tokens/次** 大（输入含工具描述） |
| **no_agent 脚本** | `no_agent: true`，纯 Python 脚本 | **0 tokens** 🆓 |
| **失败但仍在跑** | 发不出去但 LLM 照样跑完 | **照烧不误** ⚠️ |

### 实际 token 估算方法

- 看输出文件大小（`ls -la ~/.hermes/cron/output/<job_id>/`）
- 输出大小 ≈ 1/4 的 token 数（中文约 1.5 chars/token）
- 输入消耗 ≈ 输出消耗 × 2~5 倍（含系统提示 + skill + 工具调用结果）
- **no_agent 脚本** = 零 LLM 消耗，只看脚本自身 API 调用开销

### Token 省钱 checklist

- [ ] 高频任务（< 5分钟）是否可改为 no_agent 脚本？
- [ ] 是否有任务失败还在徒劳跑？→ 先修好或暂停
- [ ] 妈妈日报等发给第三方的任务 → 检查是否有限频/发不出去的问题
- [ ] 日报内容是否可以精简？（去掉八字、新闻等非核心板块）

## API Provider Monitoring (Provider-Specific Sub-Pattern)

Cron jobs that monitor API provider balances, quotas, and rate limits using lightweight **no-agent watchdog scripts**. These are specialized briefing cron jobs that use the `no_agent` pattern documented in `references/no-agent-watchdog.md`.

### When to Use

Trigger on: "监控API余额", "额度监控", "余额看门狗", provider-specific balance checks (DeepSeek, Moonshot, OpenAI, etc.)

### Base Pattern

1. Python script queries provider API balance/quota endpoint
2. Compares with cached value in `~/.hermes/.last_{provider}_{metric}`
3. Only stdout + update cache when value changes
4. Cron job with `--no-agent` delivers stdout to chat — **zero LLM token cost**

### Visual Progress Bars (Emoji)

User preference: Use emoji-based visual progress bars to show quota consumption.

```python
def emoji_bar(used: float, total: float, width: int = 10) -> str:
    \"\"\"Return an emoji progress bar.\"\"\"
    if total <= 0:
        return \"🟦\" * width + \" ❓\"
    ratio = min(used / total, 1.0)
    filled = int(ratio * width)
    empty = width - filled
    bar = \"🟦\" * filled + \"⬜\" * empty
    pct = ratio * 100
    if pct >= 90:
        bar += \" 🔴\"
    elif pct >= 70:
        bar += \" 🟡\"
    else:
        bar += \" 🟢\"
    return f\"{bar}  {used:.1f}/{total:.1f} ({pct:.0f}%)\"
```

### Color Coding Convention

| Range | Indicator | Meaning |
|-------|-----------|---------|
| 0-69% | 🟢 | Healthy |
| 70-89% | 🟡 | Warning |
| 90-100% | 🔴 | Critical / Depleted |

### Provider Endpoint Quick Reference

| Provider | Endpoint | Auth | What it returns |
|----------|----------|------|-----------------|
| **DeepSeek** | `GET /user/balance` | `Authorization: Bearer {key}` | `balance_infos[].total_balance/topped_up_balance/granted_balance` |
| **Moonshot (cash)** | `GET /v1/users/me/balance` | `Authorization: Bearer {key}` | `data.available_balance/cash_balance/voucher_balance` |
| **Moonshot (org quotas)** | `GET /v1/users/me` | `Authorization: Bearer {key}` | `organization.max_token_per_day/max_token_quota`, `organization_usage.cur_*` |

### ⚠️ Moonshot Has THREE Separate Quota Systems

| System | Endpoint | What It Tracks | Accessible Via |
|--------|----------|---------------|----------------|
| Cash Balance | `GET /v1/users/me/balance` | ¥ cash / voucher balance | API key ✅ |
| Organization Token Quotas | `GET /v1/users/me` | `max_token_per_day`, `max_token_quota`, RPM, concurrency | API key ✅ |
| Kimi Code Console Web Quotas | `kimi.com/api/*` (web-only) | "本周用量" (~7d), "频限明细" (~5h) | Web login state ONLY ❌ |

**The API key CANNOT access kimi.com web endpoints.** Web quotas require session cookies from a browser login. See `references/moonshot-quota-endpoints.md` for full details.

### ⚠️ Script Reads config.yaml → Regex Must Be Exact

A common bug: the watchdog script parses `~/.hermes/config.yaml` to find the API key. If `custom_providers` exists in the same file with its own `api_key:` fields, a loose regex will match the WRONG key.

**Real failure (2026-05-18):** Script used `r'model:.*?api_key:\s*([^\n]+)'` with `re.DOTALL`, matched the first `api_key` in `custom_providers` (Kimi key) instead of the `model:` section's DeepSeek key → 401 error.

**Fix:** Use anchored multiline regex:
```python
match = re.search(r'^model:\s*\n\s+api_key:\s*(\S+)', content, re.MULTILINE)
```

**Test before deploying:**
```bash
python3 -c "
import re
with open('~/.hermes/config.yaml') as f:
    c = f.read()
m = re.search(r'^model:\s*\n\s+api_key:\s*(\S+)', c, re.MULTILINE)
print('KEY:', m.group(1)[:10] + '...' if m else 'NOT FOUND')
"
```

### Creating the Cron Job

```bash
hermes cron create "Kimi 余额监控" \
  --schedule "every 60m" \
  --script "kimi_balance_watchdog.py" \
  --no-agent \
  --deliver origin
```

### Template Scripts

- `templates/api-balance-watchdog.py` — Cash balance monitor with emoji progress bar
- `templates/api-quota-watchdog.py` — Organization token quota monitor (rate limits, daily usage)

### Pitfalls

- **Moonshot API ≠ Moonshot web quotas** — the API balance endpoint knows nothing about free conversation credits
- **Cache file collisions** — use provider-specific cache names (`.last_deepseek_balance`, `.last_kimi_balance`)
- **First run always alerts** — no cache exists yet, so script will always output on first execution
- **JSON key changes** — provider APIs occasionally rename fields. Wrap parsing in try/except
- **Rate limiting on the balance endpoint itself** — some providers rate-limit even balance queries; space out cron frequency
- **API Key parsing** — extract from `~/.hermes/config.yaml` using regex; never hardcode keys in scripts

### ⚠️ Weixin iLink 发送限流：任务成功但用户没收到

**现象：** cron job 日志显示 `last_status: ok`，cron session 中生成了完整内容，但用户没在微信上收到。

**根因：** Weixin iLink Bot API 有发送频率限制。当多个 cron 任务在相近时间尝试发送消息时（如日报 8:00 + 余额监控 8:00/9:00），会触发 iLink 的 rate limit，消息被丢弃。

**日志特征：**
```
delivery error: Weixin send failed: iLink sendmessage rate limited: ret=-2 errcode=None errmsg=rate limited
```

**修复：分散 cron 发送时间，避免碰撞。** 注意几个发送微信的任务：
- 每日日报（8:00 UTC+8 发送）
- A股盘前分析（8:30 UTC+8 发送）
- DeepSeek 余额监控（每小时发送一次）

**碰撞场景：** 余额监控每小时整点发送 + 日报8:00 = 早上8点整两个任务同时试图发到同一微信 → 触发限流 → 日报和余额都发不出去。

**方案：**
1. 余额监控改为半点（:30）发送 → 与日报 8:00 错开
2. 如果还有多个发微信的 cron，错开到不同分钟（如 8:00、8:15、8:45）
3. 如果已经出现连续多天收不到的情况，手动 `send_message` 补发一次最新内容

**注意：** iLink 限流是时间窗口机制——限流后等几分钟自然恢复。不是永久封禁。

### 手动补发流程（Cron投递失败后的恢复步骤）

当用户说"我早报呢"/ "早报呢" / "日报没收到"时，**先补发再解释**：

1. **查 cron 列表** → `cronjob(action='list')` 找到目标任务，记录 `job_id`
2. **读输出文件** → `ls ~/.hermes/cron/output/{job_id}/` 找最近的 `.md` 文件
3. **提取正文** → 文件格式为 `## Response` 之后的内容才是实际早报。用 `read_file` 读取，跳过 header/prompt/metadata 部分
4. **直接发送** → `send_message(action='send', message=<正文内容>)` 补发给用户
5. **报告原因** → 告诉用户是限流/撞车导致的，以及你已经改了什么（如错开时间）

⚠️ **顺序很重要！** 用户说"早报呢"时最想看到的是早报内容，不是原因分析。**先把内容发出去，再说为什么没收到。** 如果先解释原因再发内容，用户会觉得你在推诿。

**常见限流场景：**
- 早报(8:00) + A股盘前(8:30) 同时发微信 → 间隔太短触发限流
- 余额监控整点 + 日报整点 → 碰撞

**修复方法：** 把冲突任务错开至少15分钟（如日报7:45，A股8:30）。

## Pitfalls

- **🔥 ALWAYS verify cron schedule timezone BEFORE creating**: Do NOT write `0 0 * * *` thinking it's midnight UTC and call it "8:00 Beijing". That's correct if you mean UTC midnight → 8AM Beijing. But if you're half-awake and pick `0 0 * * *` thinking it's local midnight, you're wrong. **Always run `date +%Z && date` first** to confirm the server timezone, then compute: `Beijing_time = UTC_time + 8h`. Write the cron expression AFTER verifying, not before.

  **Rule**: When a user says "早上8点发" and the server is in UTC, ALWAYS use `0 0 * * *` (8AM = midnight UTC). When the user says "凌晨12点发" and the server is UTC... that's `0 16 * * *` (midnight Beijing = 4PM UTC). **When in doubt, convert explicitly using a known-good formula rather than guessing.**

- **Time zone**: Always check server timezone (`date +%Z`). Defaulting to "0 9 * * *" gives 5 PM Beijing time.
- **Tool availability**: The cron session may not have the same tools as your current session. Include fallback tools in the prompt.
- **Delivery origin**: Set `deliver: "origin"` to send back to the current chat (Weixin/WeCom). If omitted, may default to CLI stdout.
- **Prompt length**: Cron prompts must be self-sufficient—write out tool names, fallback strategies, and formatting instructions explicitly.
- **Repeat**: Always set `repeat: "forever"` for daily/weekly jobs, or the job may run only once.
- **🔥 Token cost: High-frequency crons with full toolkits drain API balance**\n  - 每1分钟 cron + 212 MCP工具 = ~42K tokens/次 ≈ ¥18.5/天（实测！）\n  - **Always restrict `enabled_toolsets` on frequent cron jobs — BUT only when MCP tools are NOT needed**\n  - ⚠️ **MCP caveat:** Setting `enabled_toolsets` to any value (even `["web","terminal","file"]`) **blocks all MCP tools**. MCP tools are not part of any named toolset. If your cron needs MCP tools (eastmoney, amap, simple-rag, etc.), omit `enabled_toolsets` entirely.\n  - 只暴露该 job 需要的工具
  - 每5分钟 vs 每1分钟 = 80% 调用量减少
  - 纯检查类 cron（检查新消息、余额、状态）优先用 `no_agent` 模式 + 脚本，零 LLM 成本
  - DeepSeek V4 Flash 定价: 输入 $0.14/1M, 输出 $0.28/1M
  - 系统提示 + 工具描述是最大 token 消耗源，远大于实际业务逻辑
- **🌙 睡眠时段暂停与分批次恢复**: 用户睡觉时暂停全部 cron 省 token，但不同的任务触发时间不同。见 `references/sleep-schedule-pause-resume.md` 了解如何设置分批次恢复（如妈妈日报需 6:00 恢复赶 7:00 的班次，其余任务 8:00 恢复）。
- **⏰ 恢复时间必须早于任务触发时间！** 如果 8:00 的任务在 8:00 才恢复，它已经错过了窗口期。恢复 cron 的调度时间应比目标任务早至少 **5 分钟**（如 7:55 恢复 8:00 的每日早报）。
- **📊 GitHub Trending 页面解析**: HTML 结构会漂移（如 sponsor 按钮在 h2 前出现），裸用 `re.findall(r'href="/[^/"]+/[^/"]+"')` 会抓到 `sponsors/...` 链接。优先用 `browser_navigate` 渲染提取；必须纯 curl 时用 validated 正则（见 "GitHub Trending" 一节 Option D / `scripts/fetch_trending.py`），解析结果为 0 时先重新检查当前 HTML 结构再换方案。
- **🕐 GitHub commits `since=` 按 committer date 过滤，不是 author date**: `GET /repos/{owner}/{repo}/commits?since={date}T00:00:00Z` 会返回 author date 早很多的 commit（rebase/merge 后的 commit 常见）。做"昨天更新"简报时务必在客户端再按日期过滤一次，否则会把 3 周前的提交当成新提交报给用户。
- **📊 GitHub Search API 返回数据可能被截断**: `terminal("curl ...")` 的输出上限是 **50KB**。对于 `search/repositories?q=...` 这种返回大量项目列表的请求，50KB 通常不够容纳完整 JSON，传给 `json.loads()` 会报 `Expecting ',' delimiter` 或 `Invalid control character` 错误。**解决方法**：(a) 终端内用 `python3 -c` 提前解析并只打印你需要的数据；(b) 使用 `execute_code` 内的 `terminal()` 调用 + Python 解析 (`json_parse` 函数可处理控制字符)；(c) 或者用 `browser_navigate` 到 trending 页面读取渲染后的内容。
- **🔍 openwebsearch MCP 参数陷阱**: 该 MCP 的 `search` 工具 `searchMode` 字段只接受 `request` / `auto` / `playwright` 三个枚举值，**不接受 `news`**。传错值会导致 `Invalid enum value` 错误且连续重试会触发 loop warning。
- **🌐 零依赖新闻源优先级**: (1) **RSS feeds**（如 TechCrunch `https://www.techcrunch.com/feed/`）— 最稳定，无需 API Key，无速率限制，curl 直接抓取即可；(2) **HN Algolia API** — JSON 结构稳定，但部分环境可能被屏蔽（ConnectionRefusedError）；(3) **HN Firebase API** — 最不可靠，每个 story 需单独请求，且经常被屏蔽。**建议：cron prompt 中将 RSS 作为首选 fallback，HN 作为备选。**

- **🐍 Python `urllib.request` 不感知 `--noproxy` / 代理绕过（2026-07-12 实测）**: 当 `HTTPS_PROXY` 环境变量指向一个不可达的代理（如 Clash 宕机），`curl --noproxy '*'` 可以正常工作，但 Python 标准库的 `urllib.request.urlopen()` 仍然会尝试连接代理并报 `ConnectionRefusedError`。**影响范围**：任何在 `execute_code` 中用 `urllib.request` 或 `requests`（未显式传 `proxies={}`）获取外部 URL 的场景。**修复方法**：在 Python 中用 `subprocess.run(['curl', '-s', '--noproxy', '*', url])` 代替 `urllib.request.urlopen(url)`，或者设置 `NO_PROXY='*'` 环境变量后再调用 urllib。**验证方式**：如果 `curl --noproxy '*'` 能通但 Python urllib 报 ConnectionRefused，就是这个问题。适用于 Hacker News Firebase API、RSS feed 抓取等所有需要从 Python 脚本中发 HTTP 请求的场景。**所有 Python 代码示例中的 `urllib.request.urlopen` 调用都应替换为 subprocess+curl 模式。**
- **🔁 切换全局主模型后必须 `hermes cron resnap <job_id>` 所有启用任务**：cron 任务带 **creation-snapshot model**（创建时拍的模型快照），**不跟随全局新默认**。全局 `model.default` / `model.base_url` 一换，旧快照的模型名配新 endpoint 会直接 `HTTP 400: Unsupported model` → 任务静默失败、并把错误推给用户。日志特征：`running on creation-snapshot model 'X' (global default is now 'Y')`。修复用 `hermes cron resnap <id>`（保持不钉死、以后自动跟随）；要钉死则 `hermes cron edit <id> --model <值>`。**换完模型只跑 `hermes config set` 是不够的 —— 必须逐个 `hermes cron run <id>` 实跑验证一次再收工。**
