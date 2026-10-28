# Xiaomi MiMo Token Plan API Architecture (May 2026)

## Two Separate Systems

MiMo has **two independent web properties** with different auth:

| System | URL | Auth | Purpose |
|--------|-----|------|---------|
| **Token Plan API** | `token-plan-cn.xiaomimimo.com` | API Key (`tp-*`) | OpenAI-compatible chat/completions proxy |
| **Platform Console** | `platform.xiaomimimo.com` | Xiaomi account login | API key management, quota/billing dashboard |

**They do not share auth.** The API key from the Token Plan cannot access the Platform Console API, and vice versa.

## Token Plan API — No Balance Endpoint

The `token-plan-cn.xiaomimimo.com` endpoint is a **pure OpenAI-compatible proxy**. It supports:
- `POST /v1/chat/completions` — model inference (works ✅)
- Everything else — **404 Not Found**

Endpoints tested and confirmed dead (all return 404):
```
/v1/dashboard/billing/subscription
/v1/dashboard/billing/usage
/v1/user/balance
/v1/subscription
/v1/usage
/v1/credits
/v1/balance
/v1/account/balance
/v1/api-key/usage
/v1/dashboard/usage
/api/v1/subscription
/api/v1/balance
/api/v1/usage
```

The chat completion response **does** include a `usage` field per-request:
```json
"usage": {
  "completion_tokens": 1,
  "prompt_tokens": 248,
  "total_tokens": 249,
  "completion_tokens_details": {"reasoning_tokens": 0},
  "prompt_tokens_details": {"cached_tokens": 192}
}
```
But this is per-request token count, not cumulative balance.

Response headers contain **no quota/balance fields** — only standard HTTP headers.

## Platform Console API — Requires Xiaomi Account Login

The management API at `platform.xiaomimimo.com` requires **Xiaomi account session cookies** (OAuth login via `account.xiaomi.com`). API keys are rejected with 401 + redirect to login page.

Endpoints tested (all return 401 with `loginUrl`):
```
/api/v1/api-keys
/api/v1/user/info
/api/v1/user/quota
/api/v1/token-plan/info
/api/v1/token-plan/quota
/api/v1/dashboard
```

Two endpoints (`/api/console/user-info`, `/api/console/quota`) return 200 but serve the SPA HTML shell, not JSON data — they're frontend routes, not API endpoints.

## Implications for Watchdog Scripts

**A programmatic quota watchdog is not possible** without:
1. Logging into the Xiaomi platform via browser (requires Xiaomi account credentials), OR
2. A future API endpoint from Xiaomi that accepts API key auth for balance queries

The existing `mimo_quota_watchdog.py` silently exits every run because all endpoints fail. It should either be:
- **Removed** if no balance API becomes available, OR
- **Replaced** with a browser-scraping approach (login → scrape control panel → extract numbers)

## MiMo Native Web Search (联网服务插件) — Investigated 2026.06.12

MiMo offers a "联网服务" (web search) plugin that can be enabled on the platform. Investigation findings:

### API Behavior

1. **`webSearchEnabled` parameter** — The API accepts this in the request body:
   ```python
   # Via extra_body in OpenAI SDK
   client.chat.completions.create(
       model='mimo-v2.5',
       messages=[...],
       extra_body={'webSearchEnabled': True}
   )
   # Or via raw requests
   requests.post(url, json={..., 'webSearchEnabled': True})
   ```

2. **`tools=[{"type": "web_search"}]` parameter** — If passed WITHOUT `webSearchEnabled: True`, the API returns:
   ```
   400: "web search tool found in the request body, but webSearchEnabled is false"
   ```
   This confirms the API recognizes the parameter name.

3. **Actual behavior** — Even with `webSearchEnabled: True`, the model responds "我无法联网搜索" and does NOT perform search. The model generates text saying it can't search rather than actually searching.

### Diagnosis

The plugin is recognized by the API (it accepts the parameter without error), but the model doesn't actually use it. Possible causes:
- Plugin may not be activated yet on the user's account (activation delay)
- May require a different model (e.g. `mimo-v2.5-pro` instead of `mimo-v2.5`)
- May require the API key to have search permissions explicitly granted
- May be a platform-side feature that's not yet fully deployed

**Status: NOT WORKING as of 2026.06.12.** Needs re-testing after account-level activation.

### Implications

- Hermes does NOT have a working `web_search` tool in sessions running on mimo-v2.5
- The `web` toolset shows "enabled" in `hermes tools list` but `web_search` is not in the available tools list
- For web search capability, alternatives are needed: Tavily, Brave, or browser automation
- The MiMo search plugin at ¥16/1000次 is cheap (¥0.016/次) but currently non-functional

## 2026.05.27 Credit Reset Notice

Per the platform banner: "MiMo-V2.5 系列 API 永久降价，最高降幅达 99%，Token Plan Credits 额度提升至 5-8 倍，有效期内已用 Credits 额度全量重置，于北京时间 2026.05.27 00:00 正式生效。"

This means existing users got a significant credit boost and usage reset. The pricing comparison doc should be updated to reflect the new credit multipliers.
