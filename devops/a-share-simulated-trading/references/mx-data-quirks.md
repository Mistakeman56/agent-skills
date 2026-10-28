# Eastmoney MX MCP Data Quirks

Issues discovered through real usage of the eastmoney MX MCP tools.

## mx_data: 688525 (科创板) Returns Empty

**Symptom:** Querying 佰维存储 (688525) with `mx_data(toolQuery="佰维存储 688525 最新价 涨跌幅 主力资金")` returns `searchDataResultDTO: {}` — no data.

**Workaround:** Query by specific date:
```
mx_data(toolQuery="佰维存储 688525 收盘价 2026年5月15日")
```
This returns the close price. Note: you lose the detailed level-2 flow data (大单/小单 etc.) with this approach.

**Likely cause:** The MX backend's auto-date-range resolution may fail for some stocks (especially less-liquid or high-price stocks on 科创板). Specifying an explicit date range resolves it.

## mx_stock_simulator_summary: positions_overview False Positive Error

**Symptom:** `mx_stock_simulator_summary()` returns:
```json
"positions_overview": {
    "available": false,
    "position_count": null,
    "total_market_value_yuan": null,
    "error_hint": "持仓查询失败，未返回有效数据。"
}
```

**But the data is actually there** in `raw.positions.response.data.posList`. The summary wrapper's aggregation/algebra logic failed to parse the nested JSON correctly, but the underlying API call (`positions`) succeeded with HTTP 200.

**Fix:** Always parse `raw.positions.response.data` directly when `positions_overview` shows `available: false`:
```
raw.positions.response.data.posList  → actual positions data
raw.positions.response.data.totalAssets → total value (in 厘/1000)
raw.positions.response.data.availBalance → available balance
```

## mx_data Tool Response Truncation

**Symptom:** Complex `mx_data` queries (index lookups, multi-stock fund flow data) produce responses exceeding 60K-160K+ characters. The runtime truncates with: `[Truncated: tool response was XX,XXX chars. Full output could not be saved to sandbox.]`

**Impact:** You lose key data fields from the truncated portion.

**Mitigation:**
1. **Split queries** — query each stock individually rather than bundling
2. **Narrow scope** — be more specific in `toolQuery` about which fields you need
3. **Prioritize** — run critical queries (positions/balance) first before heavy analytical ones
4. **Re-query** — if data was truncated, retry with a narrower focus on just the missing field

## mx_stock_simulator_orders: Status Codes

Orders returned by `mx_stock_simulator_orders()` use these status codes:

| Field | Value | Meaning |
|-------|-------|---------|
| status=4 | Completed | Fully traded (all count filled), historical. Not pending. |
| status=9 | Cancelled | Order was withdrawn before full fill. No longer active. |
| type=5 | direction marker | Use with `drt`: drt=1=Buy, drt=2=Sell |
| dbStatus=200 | Normal completion | Order went through as expected |
| dbStatus=203 | Partially filled then cancelled | Some shares traded, rest cancelled (部成已撤). tradeCount > 0 but < count. |
| dbStatus=204 | Fully cancelled | 0 shares traded, entire order cancelled (已撤). tradeCount=0. |

**To find currently active (pending/unfilled) orders:** Filter for `status == 2` (pending). Status 4 = done, status 9 = cancelled. If no orders have `status == 2`, there are zero pending orders.

**To find cancelled orders:** status=9. Check dbStatus to distinguish partial-fill (203) from full-cancel (204).

**Understanding order history:** The `includeHistory=false` mode shows recent orders only. Set `includeHistory=true` to pull full order history. Paginate via `pageNo`/`pageSize` in either mode.

## Price Restoration via costPriceDec/priceDec

The API returns prices as raw integers with a decimal precision field:

```
costPrice: 36697, costPriceDec: 3 → 36.697元
costPrice: 317981, costPriceDec: 3 → 317.98元
price: 3591, priceDec: 2 → 35.91元
```

Use `mx_price_restore(price, priceDec)` to get the real price. Or calculate manually: `real_price = price / (10 ** priceDec)`.

## Tool Response Structure

All MX tools return a unified structure:
```
{
  "result": "JSON string of: {
    endpoint: URL,
    request: {...},
    response: {code, message, data: { ... }},
    success_hint: bool,
    error_hint: string|null
  }"
}
```

The `result` is a serialized JSON string — you must parse it with `JSON.parse()` before accessing fields.

## Extracting Data from Persisted Large Outputs (2026-08-05 verified)

`mx_data` / `mx_search` / `mx_select_stock` regularly return 50-150KB responses (every field carries its full metadata). Hermes persists these to `/tmp/hermes-results/call_*.txt` and shows only a preview. **Do NOT read the whole file** — parse it with `execute_code` and print only the key tables. This compressed a 98KB 佰维存储 response and a 154KB 中际旭创 response down to a few lines each.

**Parsing recipe (double-encoded JSON):**
```python
import json, re
content = open("/tmp/hermes-results/call_XXXX.txt").read()
outer = json.loads(re.search(r'\{.*\}', content, re.DOTALL).group(0))  # strip <untrusted_tool_result> wrapper
inner = json.loads(outer["result"])  # result is a JSON *string* — parse twice

# mx_data / mx_select_stock path:
tables = inner["response"]["data"]["data"]["searchDataResultDTO"]["dataTableDTOList"]
for t in tables[:6]:
    name_map = t.get("nameMap", {})          # indicator code -> Chinese name
    print(t.get("entityName"), t["table"].get("headName"))  # entity + date columns
    for k, v in t["table"].items():
        if k != "headName":
            print(f"  {name_map.get(k, k)}: {v}")

# mx_search path (news/announcements):
articles = inner["response"]["data"]["data"]["llmSearchResponse"]["data"]
for a in articles:
    print(a.get("date"), a.get("informationType"), a.get("title"))
# informationType: NOTICE=公告, INV_NEWS=新闻, REPORT=研报, WECHAT=自媒体

# mx_select_stock path: the screener table is pre-rendered markdown:
print(inner["response"]["data"]["data"]["partialResults"])  # |序号|代码|名称|...|主力净额|...|
```

**mx_data table field codes** (from `nameMap`, useful for quick greps):
| Code | Meaning | Code | Meaning |
|------|---------|------|---------|
| 326865 | 涨跌幅 | 325898 | 收盘价 |
| 326269 | 开盘价 | 327663 | 超大单流出 |
| 327521 | 大单流入 | 327806 | 大单流出 |
| 327886 | 中单流入 | 327812 | 中单流出 |
| 327907 | 小单流入 | 327917 | 小单流出 |
| 100000000006404 | (区间)主力净流入 | 100000000021528 | (区间)超大单净流入 |

## A+H Dual-Listing: mx_data Returns BOTH Markets (2026-08-05)

For companies dual-listed in A-shares and Hong Kong (e.g. 中际旭创 300308.SZ / 03308.HK, 药明康德), `mx_data` returns **two tables in one response** — one per market, each with its own currency unit (元 vs 港元). Quoting "中际旭创 300308 最新行情" returned the A股 table (300308.SZ) AND the H股 table (03308.HK).

**Always filter by `entityName` / `code` suffix before reading prices:**
```python
for t in tables:
    entity = t.get("entityName", "")
    if ".SZ" in entity or ".SH" in entity:   # A-share table only
        # ... extract quote data
```
Failure to filter can silently mix HKD prices (e.g. 1177港元) into A-share analysis. H股 data is still useful as a cross-check (e.g. 03308.HK +17% on 8/4 confirmed the A股 +13.24% move).

## Stale Holdings in Cron Prompt (recurring)

The 8/5 cron prompt listed "巨化股份2000股, 佰维存储600股" but the API showed 6 holdings with no 巨化 (sold 5/29) and 佰维 at 700 shares. This is the third confirmed recurrence. Always trust `mx_stock_simulator_summary` raw data over the prompt baseline, and explicitly note the discrepancy in the report (the analysis reads as more credible when the mismatch is called out).
