# Moonshot/Kimi Quota Endpoints Reference

Discovered across sessions. Moonshot operates **three separate quota systems** that do not share endpoints.

---

## 1. Cash Balance (API Key ✅)

**Endpoint**: `GET https://api.moonshot.cn/v1/users/me/balance`

**Headers**:
```
Authorization: Bearer {api_key}
```

**Response**:
```json
{
  "code": 0,
  "data": {
    "available_balance": 15.77193,
    "voucher_balance": 0,
    "cash_balance": 15.77193
  },
  "scode": "0x0",
  "status": true
}
```

**Fields**:
- `available_balance` — 余额（现金+代金券）
- `cash_balance` — 纯现金
- `voucher_balance` — 代金券

---

## 2. Organization Token Quotas (API Key ✅)

**Endpoint**: `GET https://api.moonshot.cn/v1/users/me`

**Headers**:
```
Authorization: Bearer {api_key}
```

**Response** (trimmed to relevant fields):
```json
{
  "code": 0,
  "data": {
    "organization": {
      "id": "org-xxx",
      "max_concurrency": 3,
      "max_request_per_minute": 20,
      "max_token_per_minute": 500000,
      "max_token_per_day": 1500000,
      "max_token_quota": 7885965
    },
    "organization_usage": {
      "cur_concurrency": 1,
      "cur_request_per_minute": 5,
      "cur_token_per_minute": 36087,
      "cur_token_per_day": 777272,
      "cur_token_usage": 88188
    },
    "project": {
      "id": "proj-xxx"
    },
    "project_usage": {},
    "user": {
      "id": "xxx",
      "user_group_id": "free",
      "max_concurrency": 0,
      "max_request_per_minute": 0,
      "max_token_per_minute": 0,
      "max_token_per_day": 0,
      "max_token_quota": 0
    },
    "user_group_id": "free"
  }
}
```

**Key fields for monitoring**:
| Field | Meaning | Typical Free-Tier Value |
|-------|---------|------------------------|
| `organization.max_token_per_day` | Daily token ceiling | 1,500,000 |
| `organization.max_token_quota` | Total token quota | ~7,885,965 |
| `organization.max_request_per_minute` | RPM limit | 20 |
| `organization.max_concurrency` | Concurrent request limit | 3 |
| `organization_usage.cur_token_per_day` | Today's token consumption | varies |
| `organization_usage.cur_token_usage` | Total usage (lifetime?) | varies |
| `organization_usage.cur_request_per_minute` | Current RPM | varies |
| `organization_usage.cur_concurrency` | Current concurrency | varies |

**Note**: `user.*` limits are all `0` for free-tier; the actual limits live under `organization.*`.

---

## 3. Kimi Code Console Web Quotas (API Key ❌, Web Login Required)

**Endpoint**: Various under `https://www.kimi.com/api/*`

**Authentication**: Session cookies from browser login. API key returns `auth.token.invalid`.

**Observed UI labels** (from user screenshots):
- "本周用量" (This Week's Usage) — ~7-day cycle, shown with percentage + progress bar + "X 小时后重置"
- "频限明细" (Rate Limit Details) — ~5-hour cycle, shown with percentage + progress bar + "X 小时后重置"

**Attempted endpoints** (all returned errors or auth failures with API key):
- `GET /api/chat/credit` → `auth.token.invalid`
- `GET /api/billing/credit` → `internal.error`
- `GET /api/subscription` → `internal.error`
- `GET /api/code/quota` → `internal.error`
- `GET /api/code/credit` → `internal.error`
- `GET /api/membership/quota` → `internal.error`
- `GET /api/membership/credit` → `internal.error`

**How to discover the real endpoint**:
1. User logs into `https://www.kimi.com/code/console`
2. Open DevTools → Network tab
3. Refresh page
4. Look for requests containing `quota`, `usage`, `credit`, `rights`
5. Report URL + request headers (cookies) + response JSON

**Known subscription tiers** (from marketing page):
- Andante: ¥39/mo
- Moderato: ¥79/mo — "Weekly refreshed usage quotas"
- Allegretto: ¥159/mo
- Allegro: ¥559/mo

---

## Summary: Which Endpoint for Which Use Case?

| User Says | Use Endpoint | Notes |
|-----------|-------------|-------|
| "API 余额" / "cash" / "钱" | `/v1/users/me/balance` | Straightforward |
| "token 额度" / "每天限制" / "RPM" | `/v1/users/me` | Org-level rate limits |
| "Code 额度" / "本周用量" / "频限明细" | Web-only — need user to抓包 | API key cannot access |
