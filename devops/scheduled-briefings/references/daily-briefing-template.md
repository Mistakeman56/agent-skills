# Daily Briefing Prompt Template

This is the full prompt template used for the user's morning briefing on Weixin.

## Prompt Text

```
今天是 {{ strftime("%Y年%m月%d日 %A") }}，现在早上8点，请为我生成一份每日早报，分三个板块，用中文呈现。使用 markdown 格式，注意在微信中展示友好，段落简洁清晰。

### 板块一：Hermes 项目更新
搜索 GitHub 上 `nousresearch/hermes-agent` 仓库最近一天的 commits、issues 和 PR 情况，挑重要的说。

### 板块二：GitHub 今日热榜
搜索 GitHub Trending，列出今天最热门的 3-5 个项目（language 不限），每个项目一句话简介。

### 板块三：科技新闻
搜索今天值得关注的科技新闻或 AI 行业动态，挑 2-3 条最有意思的。

语气轻松但不浮夸，像在跟朋友分享。最后加一句鼓励的话或者小幽默，开启美好的一天～
```

## Cron Job Configuration

```yaml
name: 每日早报：Hermes更新+GitHub热门+新闻
schedule: 0 0 * * *    # 8:00 AM Beijing time (UTC 00:00)
deliver: origin         # Send to current chat (Weixin/WeCom)
repeat: forever
```

## Content Generation Rules

When generating the briefing:
- **Length**: GitHub trending 3-5 items max; Tech news 2-3 items max
- **Style**: Relaxed, like sharing with a friend; not exaggerated news-anchor style
- **Closing**: Always end with an encouraging sentence or small humor
- **WeChat-friendly**: Short paragraphs (2-3 lines), use emojis sparingly for section breaks

## Data Gathering Fallback Chain

Cron sessions may not have the expected MCP tools. Use this priority order:

### 1. Hermes Project Updates
- **Primary**: GitHub REST API via terminal (`curl -s "https://api.github.com/repos/nousresearch/hermes-agent/issues?state=all&sort=updated&direction=desc&per_page=10"`) — see `references/github-rest-api-fallbacks.md`
- **Fallback**: `browser_navigate` to `https://github.com/nousresearch/hermes-agent/commits/main` and `.../pulls`
- **Last resort**: GitHub MCP (if available)

⚠️ **Parsing**: Use `python3 -c "import json,sys; json.load(sys.stdin)"` within terminal, or prefer `execute_code` tool with `from hermes_tools import terminal, json_parse` for complex multi-line processing.

### 2. GitHub Trending
- **Primary (proven)**: BrightData scrape — `mcp_brightdata_scrape_as_markdown url="https://github.com/trending"` — returns structured text with repo names, descriptions, stars
- **Fallback 1**: `browser_navigate` to `https://github.com/trending` — extract from rendered page snapshot
- **Fallback 2**: GitHub Search API (`q=created:>{3_days_ago}&sort=stars&order=desc&per_page=5`)

**Parse from BrightData markdown output**: Look for lines matching `owner / repo` pattern (repo name), following paragraph (description), and lines containing "stars today" (velocity).

### 3. Tech News
- **Primary (for AI-specific news)**: BrightData search for AI news sites — `mcp_brightdata_search_engine query="AI news today {date}"` — finds published daily AI roundups from sites like buildfastwithai.com
- **Fallback 1 (proven reliable)**: TechCrunch RSS feed — `curl -s --noproxy '*' -L 'https://www.techcrunch.com/feed/'` — parse titles with `re.findall(r'<title><!\[CDATA\[(.*?)\]\]></title>', content)` (returns 8-10 recent articles, no auth, no rate limit, works in restricted environments where HN APIs are blocked)
- **Fallback 2**: HN Algolia API — `curl -s 'https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=15'`
- **Last resort**: Official HN Firebase API (⚠️ may be blocked in some environments — ConnectionRefusedError on Firebase endpoints)

### Proven REST API Example (2026-05-25)

When both GitHub MCP and `gh` CLI were unreachable, this exact sequence worked:

```bash
# 1. Issues + PRs (one endpoint, sorted by update time)
curl -s "https://api.github.com/repos/nousresearch/hermes-agent/issues?state=all&sort=updated&direction=desc&per_page=10"

# 2. PRs only (cleaner for PR-specific info)
curl -s "https://api.github.com/repos/nousresearch/hermes-agent/pulls?state=all&sort=updated&direction=desc&per_page=10"

# 3. Commits
curl -s "https://api.github.com/repos/nousresearch/hermes-agent/commits?per_page=10"
```

Parse each with `python3 -c` — output fits within 50KB terminal cap for these endpoints.

## REST API Examples

### Hermes Agent (GitHub REST API)
```bash
# Commits
curl -s "https://api.github.com/repos/NousResearch/hermes-agent/commits?per_page=10"
# Issues/PRs
curl -s "https://api.github.com/repos/NousResearch/hermes-agent/issues?state=all&sort=updated&direction=desc&per_page=5"
# Smarter: Search API with date + type filter (preferred)
curl -s "https://api.github.com/search/issues?q=repo:nousresearch/hermes-agent+updated:>=2026-05-18&sort=updated&order=desc&per_page=10"
```

Recommended parsing approach (inside `execute_code`):
```python
from hermes_tools import terminal, json_parse
import json

# Issues & PRs via Search API
r = terminal('curl -s "https://api.github.com/search/issues?q=repo:nousresearch/hermes-agent+updated:>=2026-05-18&sort=updated&order=desc&per_page=10"')
data = json_parse(r['output'])
for item in data['items']:
    print(f"#{item['number']} {item['title']} ({item['state']})")

# Commits
r2 = terminal('curl -s "https://api.github.com/repos/NousResearch/hermes-agent/commits?per_page=10"')
commits = json_parse(r2['output'])
for c in commits[:10]:
    print(f"{c['sha'][:7]} {c['commit']['author']['name']}: {c['commit']['message'].split(chr(10))[0]}")
```

### GitHub Trending (Browser navigation)
```bash
curl -s "https://api.github.com/search/repositories?q=created:>$(date -d '3 days ago' +%Y-%m-%d)&sort=stars&order=desc&per_page=5"
```

### Tech News (Hacker News)
```bash
# Algolia API — front page in one call (PREFERRED)
curl -s 'https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=15'

# Single-call redirect wrapper
curl -s "https://api.hackerwebapp.com/news" | python3 -m json.tool

# Official API (two calls — last resort)
curl -s "https://hacker-news.firebaseio.com/v0/topstories.json"
curl -s "https://hacker-news.firebaseio.com/v0/item/{id}.json"
```

## Tool Pitfalls

- **openwebsearch MCP**: Its `search` tool only accepts `searchMode` values `request` / `auto` / `playwright`. Passing `news` or other strings causes immediate input validation errors.
- **GitHub skill**: May be missing from the skill library. Do not rely on it being available in cron sessions. If the cron prompt lists `github` as a skill to load and it's missing, the session will show a warning but can still proceed with REST API or browser fallbacks.
- **GitHub API truncation**: `terminal("curl ...")` output is capped at 50KB. For large search result sets, the JSON may be truncated and fail to parse. Prefer `execute_code`+`json_parse()` or pipe through `python3 -c` in-shell to select only needed fields before printing.
- **Bash quoting in cron**: inline `python3 -c` with f-strings, `chr(10)`, or curly braces will cause bash syntax errors. Use `execute_code` for any non-trivial Python processing.
- **🐍 urllib.request ignores `--noproxy` (2026-07-12)**: When `HTTPS_PROXY` points to a dead proxy, `curl --noproxy '*'` works but Python's `urllib.request.urlopen()` still tries the proxy → `ConnectionRefusedError`. **Fix**: use `subprocess.run(['curl', '-s', '--noproxy', '*', url])` instead of `urllib.request.urlopen(url)` in any Python code. Applies to HN API calls, RSS fetching, and all HTTP from execute_code.
