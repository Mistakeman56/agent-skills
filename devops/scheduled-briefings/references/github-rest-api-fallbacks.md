# GitHub REST API Fallbacks for Cron Briefings

When the GitHub MCP server is unreachable (e.g., "MCP server 'github' is unreachable after 3 consecutive failures"), use the GitHub REST API directly via `terminal("curl ...")` or `execute_code` + `from hermes_tools import terminal`.

## Why the REST API is reliable

- No auth required for public repos (rate limit: 60 req/hr for unauthenticated — more than enough for a once-daily cron)
- No MCP dependency, no Chrome dependency
- Returns structured JSON — easy to parse

## Endpoints Quick Reference

### 1. Issues (includes both issues AND pull requests)

```bash
curl -s "https://api.github.com/repos/{owner}/{repo}/issues?state=all&sort=updated&direction=desc&per_page=10"
```

Each item has: `number`, `title`, `state` (open/closed), `user.login`, `updated_at`, `created_at`, `pull_request` (present if it's a PR).

**To distinguish PRs from issues:** items that have a `pull_request` key are pull requests; items without it are issues.

### 2. Pull Requests (PRs only)

```bash
curl -s "https://api.github.com/repos/{owner}/{repo}/pulls?state=all&sort=updated&direction=desc&per_page=10"
```

Each item has: `number`, `title`, `state` (open/closed), `user.login`, `updated_at`, `created_at`, `merged_at` (if merged).

### 3. Commits

```bash
curl -s "https://api.github.com/repos/{owner}/{repo}/commits?per_page=10"
```

Each item has: `sha`, `commit.author.name`, `commit.author.date`, `commit.message` (first line is the subject).

### 4. Search API (recommended for date-filtered queries)

```bash
curl -s "https://api.github.com/search/issues?q=repo:{owner}/{repo}+updated:>={date}&sort=updated&order=desc&per_page=10"
```

- `date` format: `2026-05-25`
- Can filter by `+type:pr` or `+type:issue` to narrow results
- Single endpoint returns everything merged together

### 5. Trending (no MCP fallback)

```bash
curl -s "https://api.github.com/search/repositories?q=created:>2026-05-22&sort=stars&order=desc&per_page=5"
```

⚠️ This approximates trending by filtering repos created in the last 3 days sorted by stars. It's not true "stars/hour" trending, but good enough for a daily briefing.

## Parsing Pattern (execute_code preferred)

```python
from hermes_tools import terminal, json_parse

# Fetch issues/PRs
r = terminal('curl -s "https://api.github.com/repos/NousResearch/hermes-agent/issues?state=all&sort=updated&direction=desc&per_page=10"')
data = json_parse(r['output'])

for item in data:
    is_pr = 'pull_request' in item
    prefix = f"PR #{item['number']}" if is_pr else f"#{item['number']}"
    print(f"{prefix} [{item['state']}] {item['title']} ({item['updated_at'][:10]})")

# Fetch commits
r2 = terminal('curl -s "https://api.github.com/repos/NousResearch/hermes-agent/commits?per_page=5"')
commits = json_parse(r2['output'])

for c in commits:
    sha = c['sha'][:7]
    msg = c['commit']['message'].split(chr(10))[0]
    author = c['commit']['author']['name']
    date = c['commit']['author']['date'][:10]
    print(f"{sha} {msg} ({date}, {author})")
```

## Why NOT inline `python3 -c` in shell

```bash
# This WORKS for simple cases but frequently BREAKS:
curl -s "..." | python3 -c "
import json, sys
data = json.load(sys.stdin)
...
"
```

**Common failures:**
- Shell interprets single quotes inside f-strings → SyntaxError
- `chr(10)` newlines break the shell command string
- Curly braces in f-strings (`{item['key']}`) conflict with bash brace expansion
- Output truncated at 50KB cap → truncated JSON → parse failure

**Always prefer `execute_code` with the import-based `json_parse()` helper** for multi-line Python processing. Use inline `python3 -c` only for trivial single-line expressions.

## Example: Morning Briefing Data Flow

This is the actual flow that worked on 2026-05-25 (GitHub MCP unreachable):

1. `terminal("curl -s 'https://api.github.com/repos/nousresearch/hermes-agent/issues?...'")` → Get open/closed issues
2. `terminal("curl -s 'https://api.github.com/repos/nousresearch/hermes-agent/pulls?...'")` → Get PRs
3. `terminal("curl -s 'https://api.github.com/repos/nousresearch/hermes-agent/commits?per_page=5'")` → Get recent commits
4. Parse each with separate `python3 -c` JSON processing (each output is small enough)

This produced clean output with no MCP dependency.
