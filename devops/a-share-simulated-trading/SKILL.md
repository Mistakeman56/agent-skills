---
name: a-share-simulated-trading
description: Set up and operate A-share (Chinese stock market) simulated trading via the eastmoney MX MCP server. Covers MCP installation, cron job creation for market analysis, trade execution, and strategy formulation accounting for A-share quirks.
license: Proprietary. LICENSE.txt has complete terms
platforms: [linux]
---

# A-Share Simulated Trading

Set up a simulated trading account using the 东方财富妙想 (Eastmoney MX) MCP server, create cron-based market analysis, and execute trades via the simulation platform.

## When to Use

Use this skill when the user asks to:
- Set up stock trading simulation / 模拟盘
- Install a stock trading MCP
- Create a stock market watch / cron-based market monitoring
- Execute simulated buy/sell orders
- "炒股" or "操盘" related requests
- Any combination of MCP + cron + stock market
- Buy Hong Kong stocks (港股, like Xiaomi 01810) — see `references/hk-stock-trading-guide.md`
- Open a stock trading account / ask about 开户 routes — see `references/a-share-account-opening-guide.md`
- Research Xiaomi concept stocks / 小米产业链A股 — see `references/xiaomi-supply-chain-stocks.md`
- Ask about stable growth stocks / 白马股 / 核心资产 — see `references/a-share-core-assets.md`
- Analyze optical module stocks (光模块) — see `references/2026-05-19-光模块分析.md`
- Build a portfolio allocation (e.g., 70/30 split between concept stocks and defensive core assets)
- Discuss AI/energy investment thesis (AI needing electricity, energy concept stocks) — see `references/ai-energy-thesis.md`
- Set up multi-agent AI workflows for automated trading analysis — see `references/multi-agent-trading-workflow.md`
- Compare GPU options for AI inference (NVIDIA vs AMD vs Intel) — see `references/multi-agent-trading-workflow.md`

## Prerequisites

1. **MX_APIKEY** — Register at https://marketing.dfcfs.com/views/finskillshub/indexIoMv0EzE, click "立即领取" to get an API key (free, new users get 5000 quota)
2. **Bind simulated account** — Visit https://dl.dfcfs.com/m/itc4 to bind a trading account after getting the key
3. **Server timezone** — Must be Asia/Shanghai for correct cron scheduling: `timedatectl set-timezone Asia/Shanghai`

## MCP Installation

### Install from source

```bash
git clone https://github.com/jm12138/eastmoney-mx-finance-mcp-server.git /tmp/eastmoney-mcp
# All deps (mcp, httpx, typer) are typically already in the Hermes venv
# Use --no-deps to skip network-dependent install
~/.hermes/hermes-agent/venv/bin/pip install /tmp/eastmoney-mcp --no-deps -q
```

### Verify installation

```bash
~/.hermes/hermes-agent/venv/bin/eastmoney-mx-finance-mcp-server --help
# Should show: "Usage: eastmoney-mx-finance-mcp-server [sse|stdio]"
```

### Config.yaml entry

Add to `~/.hermes/config.yaml` under `mcp_servers:`:

```yaml
  eastmoney-mx:
    command: ~/.hermes/hermes-agent/venv/bin/eastmoney-mx-finance-mcp-server
    args:
    - stdio
    env:
      MX_APIKEY: "your-api-key-here"
    timeout: 30
```

### Available Tools

| Tool | Function |
|------|----------|
| `mx_search(query)` | Search news/research/reports |
| `mx_data(toolQuery)` | Financial data queries (quotes, fundamentals, technicals) |
| `mx_select_stock(keyword)` | Smart stock screening by natural language |
| `mx_selfselect_get()` | Query watchlist |
| `mx_selfselect_manage(query)` | Add/remove watchlist items |
| `mx_stock_simulator_balance()` | Check account balance (amounts in 厘 = 1/1000 元) |
| `mx_stock_simulator_positions()` | Query positions |
| `mx_stock_simulator_summary()` | Combined balance + positions overview |
| `mx_stock_simulator_trade(type, stockCode, quantity, useMarketPrice, price)` | Place simulated buy/sell orders |
| `mx_stock_simulator_cancel(orderNo, cancelAll)` | Cancel orders |
| `mx_stock_simulator_orders(pageNo, pageSize, includeHistory)` | Order history |
| `mx_amount_li_to_yuan(amount_li)` | Convert 厘 to 元 (÷ 1000) |
| `mx_price_restore(price, priceDec)` | Restore real price from raw data |

## Cron Job Patterns

### ⚠️ First Rule: Check If Market Is Open

Before running ANY analysis or trade, check the current day/time:
- A-share opens Mon-Fri 9:30-15:00 (Beijing time)
- If today is Saturday/Sunday → skip analysis, say "今天休市"
- If Chinese holiday (元旦/春节/清明/五一/端午/中秋/国庆) → skip
- Use `date +%u` (1=Mon, 7=Sun) or `mcp_time_time_invoke_tool` to verify day of week

### Market Analysis Cron (8:30 AM Beijing, Enhanced)

Creates a daily pre-market briefing with account status + market news + trading recommendations.

**Schedule:** `30 0 * * 1-5` (8:30 AM Beijing = 00:30 UTC, weekdays)

**⚠️ Timezone critical:** `30 8 * * 1-5` runs at 8:30 UTC = 16:30 Beijing time. Always convert: Beijing time - 8 hours = UTC.

**⚠️ enabled_toolsets blocks MCP:** If you set `--toolsets web` when creating this cron, the eastmoney MCP tools will be **invisible** to the cron session. Always omit `--toolsets` for crons that need MCP tools.

**Before creating, verify:**
```bash
# Check if any existing cron has enabled_toolsets that would block MCP
hermes cron list | grep -A3 enabled_toolsets
```

**Prompt structure (enhanced):**
```
现在是北京时间8:30，A股9:30开盘。你是A股模拟盘操盘手，账户名"Hermes2232"（模拟组合3384852，初始100万）。

## 第零步：确认是否开盘
如果是周末或节假日 → 说"今天休市，不分析"并退出。

## 第一步：检查账户
使用 mx_stock_simulator_summary 查看总资产、可用资金、持仓明细、盈亏。
使用 mx_stock_simulator_orders 检查未成交委托。

## 第二步：查询持仓个股行情与资讯
使用 mx_data 查持仓股最新价、涨跌幅、主力资金流向。
使用 mx_search 搜持仓股的最新公告/新闻/研报。

## 第三步：大盘环境扫描
使用 mx_data 查大盘指数（上证、深证、创业板）走势。
使用 mx_search 搜索"今日A股热点板块 盘前"、"周末重大财经新闻"。

## 第四步：热点概念与资金流向
使用 mx_select_stock 搜索"今日涨幅居前板块"、"主力资金净流入板块"。
使用 mx_search 搜索"周末市场消息 利好板块"、"本周A股策略观点"。

## 第五步：综合分析与操作建议
**盘前分析 | 2026年X月X日 周一**
📊 **大盘环境：** [上证/深证/创业板状态]
🔥 **周末热点：** [重大消息面]
📈 **持仓分析：** 逐只分析走势判断 + 操作建议（持有/加仓/减仓/止损）
💡 **今日关注：** 值得关注的个股/板块
🎯 **今日策略：** 明确的买入/卖出/持有计划，含目标价、止损位
```

### One-Shot Trade Execution Cron

For automated trade execution at a specific time:

```bash
hermes cron create "执行买入" --schedule "35 1 * * 1-5" --repeat once --deliver weixin
```

Prompt should:
1. Check market trends at T+5 minutes (enough to see direction)
2. Place market order if conditions met
3. Report buy price, quantity, remaining balance, stop-loss level

## A-Share Market Characteristics

### Known Irrationalities (Critical for Strategy)

A-shares have unique behavioral patterns that pure fundamental analysis misses:

- **Concept speculation (概念炒作):** Stocks can jump based on name similarity, word association, or memes rather than fundamentals. Example: Trump's state dinner featured 椰树牌 mineral water → ST椰岛 (unrelated company sharing "椰") hit daily limit up.
- **Policy-driven volatility:** Government announcements (央行, 国常会, sector policies) trigger broad moves
- **Retail investor herding:** ~80% of trading volume is retail; trends can overshoot wildly
- **Information asymmetry:** News moves markets faster than in developed markets

### Strategy Adaptation

Pure fundamental analysis is insufficient. Use a three-layer approach:

1. **Fundamental filter (基本面打底):** Screen for reasonable PE/PB, positive earnings, decent market cap (¥100亿+), active trading volume
2. **Concept tracking (概念追踪):** Monitor hot sectors, policy catalysts, news-driven momentum
3. **Technical timing (技术面择时):** Entry/exit timing based on volume, price action, support/resistance

### Valuation Methodology: 3-Year PE/PB Percentile

The most powerful valuation tool for A-share stock analysis is the **3-year historical percentile** for PE and PB. Eastmoney's mx_data tool returns `3年市盈率历史百分位` and `3年市净率PB历史百分位` for any stock.

**Interpretation:**

| Percentile | Meaning | Action |
|:----------:|:--------|:-------|
| **< 10%** 🟢 | **Near historical low** — stock is significantly undervalued relative to own history | Strong buy signal if thesis intact |
| **10-40%** 🟡 | Below average — reasonable entry | Buy on dips |
| **40-60%** ⚪ | Fair value — neutral | Hold / wait |
| **60-80%** 🟠 | Above average — premium pricing | Consider partial exit |
| **> 80%** 🔴 | **Near historical high** — stock is expensive | Avoid / wait for pullback |

**Example from this session (2026-05-16):**
- 小米集团 01810 PE percentile: **0.68%** 🟢 → lowest in 3 years, strong buy signal
- 长江电力 600900 PE percentile: **0.55%** 🟢 → near all-time low, user bought it
- 中国核电 601985 PE percentile: **89.52%** 🔴 → too expensive, recommended WAIT

**Data retrieval pattern:**
```
mx_data: "长江电力 600900 最新行情 估值 PE PB 股息率"
→ Look for "3年市盈率历史百分位" in the response
→ Also extract: PE(TTM), PB(TTM), 市盈率(动)
```

### Investment Thesis Research Workflow (AI/Energy Example)

When the user asks about a long-term investment thesis like "AI needs electricity → energy stocks", use this multi-source research pattern:

1. **Pull stock fundamentals** via mx_data for candidate stocks (PE/PB/percentile)
2. **Pull analyst reports** via mx_search for "stock code 最新研报 目标价"
3. **Search latest news** via BrightData search_engine for the thesis (e.g., "AI数据中心 用电量 增长 2026")
4. **Cross-reference PE percentiles** to identify which thesis stocks are cheap vs expensive
5. **Present in comparison table** with: PE percentile, analyst TP upside, key logic, risk factors
6. **Recommend specific ticker** with rationale — don't just list possibilities

**Verification pattern for analyst consensus:**
```python
# After mx_search returns reports, extract:
# - Number of "买入" vs "中性" vs "卖出" ratings
# - Highest TP, lowest TP, average TP
# - Compare current price to average TP → upside %
```

### Trading Rules

- **Position sizing:** Single stock ≤ 30% of total capital
- **Portfolio size:** Ideally 3-5 stocks. 8+ stocks is over-diversified and hard to manage — flag this as a concern during analysis. When over-diversified, prioritize **cleaning up the losers first** (stop-loss cuts) before considering new entries.
- **Total position limit:** Total market value ≤ 85% of NAV. >90% leaves no buffer for market dips. If the portfolio is >90% invested and 2+ positions are underwater, the first action is always: cut losers to free up cash.
- **Stop-loss:** -5% from entry price (firm rule, no exceptions)
- **Stop-loss violation protocol:** If a position exceeds -5%, take action IMMEDIATELY — do not hold hoping for a rebound. Document the violation, place the stop order, and review why the rule was broken. Example from 2026-05-19: 巨化股份 hit -11.55% while being held because no stop was triggered at -5%. This type of slippage destroys portfolio returns. If you find yourself holding a -5%+ loser, write a reference note (`references/stop-loss-violation-*.md`) to learn from it.
- **Take-profit:** +15% consider partial exit
- **Holding period:** 3-15 days (not day trading, not long-term)
- **Diversification:** At least 2 different sectors
- **Market cap preference:** ¥100亿+ market cap, ¥1亿+ daily volume

### Trade Execution Timing

**Critical lesson from session 2026-05-15:** When the user says "执行" (execute), do it immediately in the current session — do NOT set a future one-shot cron. The cron may fail silently (not appear in list, not trigger), and delaying creates confusion.

**Last-minute buying (session 2026-05-18):** When the user says "准备买入" near market close (<15:00):
1. **Check time first** — use `mcp_time` to confirm A-share market is open (9:30-15:00 Beijing)
2. **Quick data gathering** — query real-time quotes for all target stocks in parallel (not sequential)
3. **Brief snapshot** — present a compact price table (stock, price, change%, open), not verbose analysis
4. **Act fast** — execute buys immediately; final 3 minutes are tight. Use limit orders at the current ask price
5. **Report cleanly** — after trade: a simple markdown table of what was bought + order IDs. No emotional commentary like "冲啊" or "压哨" unless the user's tone invites it

**After-hours fallback:** If the user says "准备买入" after 15:00 or on weekends:
- Do NOT try to trade — the exchange is closed
- Instead: note their intent and set a reminder (cron) for next trading day at 9:25 AM (pre-market call auction) or ask if they want a scheduled buy at open

**Right approach:**
```python
# User says "执行" → IMMEDIATELY place the order
mcp_eastmoney_mx_mx_stock_simulator_trade(
    trade_type="buy", stockCode="688525", quantity=600, useMarketPrice=True
)
# Then report back: "已买入！成交价XX，共XX股，占用资金XX万"
```

**Last-minute EOD buying (收盘前<15:00):**
1. **Check time first** — use `mcp_time` to confirm market open (9:30-15:00 Beijing)
2. **Quick data** — query all target stocks in PARALLEL, not sequential
3. **Fast valuation signal** — for known strategy picks (e.g., 长江电力底仓), look at:
   - Current price relative to recent 25%ile/50%ile PE percentile
   - If price is at/near the 25%ile (low end of PE band) → solid entry point
   - If today's change is negative → even better (low of the day)
4. **Execute** with limit order at current ask price — last 3 minutes enough for 2-3 orders
5. **Report** — simple markdown table of buys + order IDs. Keep it compact, not verbose.

**Wrong approach (what caused the problem):**
```
User: 执行
Agent: "好的我设一个9:35的定时任务！"
# User waits... nothing happens at 9:35... user gets frustrated.
```

**Why this fails:**
- The `repeat: once` cron may not show in the cron list after creation
- Cron sessions can fail silently (MCP not loaded, API timeout, etc.)
- The user sees you "do something" but then nothing arrives at the promised time
- You then check the market yourself and give contradictory information ("I'll wait, market is down") vs ("I already set up the buy")

**If you absolutely must delay execution** (e.g., want to see open first):
- Set the cron AND verify it appears in `hermes cron list`
- Have a manual fallback ready if the cron doesn't fire
- Or better: do the analysis, get user confirmation, then execute immediately

### Portfolio Allocation Strategy (User-Agreed)

The user agreed to a **70/30 split** as a default portfolio structure for active trading:

- **🔴 70% 弹性仓 (Elastic/Speculative):** ~51万 of ~74万 available. Invest in concept/hot-sector stocks (Xiaomi supply chain, AI, etc.). High beta, active management, 3-15 day holding.
- **🔵 30% 底仓 (Foundation/Defensive):** ~22万 of ~74万 available. Invest in core asset stocks (白马股 like 美的集团 000333). Low volatility, PE < 15x, dividend payer, multi-month hold.

**Adjustment logic:**
- If market is clearly bullish (up-trend confirmed) → shift to 80/20
- If market is clearly bearish (sustained downtrend) → shift to 50/50
- If user is new to trading / uncertain → default to 70/30
- On user request → any ratio they specify

**Execution workflow:**
1. Confirm with user: "70%小米概念 + 30%白马底仓，行不行？"
2. If user agrees, note the allocation in session state
3. On 下一交易日: execute both buys simultaneously at market open (if user confirms)

### Optical Module (光模块) Buy Pattern

When user asks about 光模块 stocks (popular topic following 峰哥):

**User context:** User is a fan of 峰哥 (a stock influencer on Weibo). User's tone is self-aware about the "everyone's talking about it" risk signal.

**Response pattern:**
1. Acknowledge the 峰哥 anecdote (user enjoys sharing these stories)
2. Give objective assessment: thesis is strong (AI bandwidth demand), but crowded trade near-term
3. Show the price/data: Big 3 are ¥350-1000+ per share, 1 hand costs ¥35k-100k+
4. Offer affordable alternatives: 东山精密 (¥218), 光迅科技 (¥207), 仕佳光子 (¥169)
5. Use simulated account if user wants exposure but can't afford 1 hand

**For small capital (¥1000):**
- A-share minimum 1 hand = 100 shares
- Even cheapest 光模块 stocks cost ¥17k/hand
- Recommend ETF (通信ETF, 5G ETF) or simulated account
- Be direct: "1000块买不了中际旭创1股，先模拟盘练手"

### Batch Buy Shorthand ("给我买X和Y和Z")

When user casually lists multiple stocks to buy at once (e.g., "给我买烽火通信和中际旭创和东山精密"):

1. **Query all prices in parallel** — use `mx_data` or `mx_select_stock` for each stock simultaneously
2. **Calculate total cost** — 100 shares × price for each, sum them up
3. **Check available balance** — `mx_stock_simulator_positions` shows `availBalance` (in 厘, divide by 1000)
4. **Execute all buys in parallel** — use `mx_stock_simulator_trade` with `useMarketPrice=true` for each stock
5. **Report** — compact table: stock name, quantity, price, total cost

**Key decisions to make (without asking user):**
- Quantity: default 100 shares (1 hand) per stock unless user specifies otherwise
- Price type: always `useMarketPrice=true` — user's casual tone means "just do it"
- Don't ask for confirmation — the user listed specific stocks and said "买", that's the order

**If total cost > available balance:**
- Calculate how many hands (100-share lots) fit in the budget
- Report: "资金够买X手A + Y手B + Z手C，总计XX万，余额XX"
- Execute what fits, note what doesn't

**Lunch break / after-hours:** Orders queue and execute at next open (see "Mid-day order queuing" pitfall above).

### Pre-Market Trade Setup (9:20 Cron)

When user agrees to a trade that should execute at next day's open:

**Setup:**
```bash
hermes cron create "trade description" \
  --schedule "YYYY-MM-DDTHH:MM:SS" \
  --repeat once \
  --deliver origin
```

**⚠️ Critical: Do NOT set `enabled_toolsets` on this cron**
Setting `enabled_toolsets: ["web"]` or any non-empty value will block MCP tools (mx_data, mx_stock_simulator_trade, etc.) and the cron will fail silently.

**Prompt structure must include:**
1. Time check (mcp_time to confirm market open)
2. Pre-market price check (if stock up >5% at open, skip)
3. Market order execution
4. Result reporting (buy price, quantity, remaining balance)

**Verification:** After creating, check `hermes cron list` to confirm it appears. If the list doesn't show the new cron, the job may not fire — recreate with a slightly different schedule or use `--repeat 1` instead of omitting repeat entirely.

### "你就看着办" Mode (No-Ask Execution)

When the user says *"你就看着加吧别问我 我也不知道"* or similar ("你看着办", "你做主", "你自己决定"):

1. **This is NOT a request for analysis** — they want immediate action, not a discussion
2. **Decide and execute** — calculate the quantity yourself
3. **Use market price** — the user's tone is "get it done fast, don't haggle over pennies"
4. **Report after execution** — stock, quantity, total cost
5. **DO NOT ask questions** — no "how many?" / "buy now?" / "is this price ok?" — the user explicitly said they don't know and don't want to decide

### Price Target Monitoring Cron (no_agent=True)

When user wants to watch for a stock to drop to a target price before buying (e.g., "帮我盯着光模块，跌了再买"):

**Pattern: Script-only cron, zero token cost per tick.**

1. **Write a monitoring script** at `~/.hermes/scripts/<name>.py` that:
   - Fetches real-time prices via tencent API (see a-stock-data skill)
   - Compares to target prices
   - Outputs EMPTY STRING when nothing to report (silent delivery)
   - Outputs alert text only when conditions are met
   - Handles non-trading hours by outputting empty (no weekend/after-hours spam)

2. **Create cron with `no_agent=True`** (no LLM, just script output):
   ```
   cronjob create:
     name: "XX监控"
     schedule: "0 10,11,14,15 * * 1-5"  (盘中4次)
     script: <script_name>.py
     no_agent: true
     deliver: origin
   ```

3. **Script must be self-contained** — no Hermes tools, just Python + requests. The script IS the job; stdout is delivered verbatim.

**Script template pattern:**
```python
import urllib.request, sys
from datetime import datetime

STOCKS = {
    "300502": {"name": "新易盛", "target": 720},
    "002281": {"name": "光迅", "target": 210},
}

def get_prices():
    # Fetch from qt.gtimg.cn, return {code: {price, change_pct, ...}}

def main():
    now = datetime.now()
    wd = now.weekday()
    if wd >= 5: print("", end=""); return  # 周末静默
    t = now.hour * 100 + now.minute
    if t < 925 or t > 1505: print("", end=""); return  # 非交易时段静默
    
    prices = get_prices()
    alerts = []
    status = []
    for code, info in STOCKS.items():
        cur = prices[code]["price"]
        status.append(f"• {info['name']}: ¥{cur:.2f} 距目标¥{info['target']}")
        if cur <= info["target"]:
            alerts.append(f"🟢 {info['name']} 到达目标位！现价 ¥{cur:.2f}")
        elif cur <= info["target"] * 1.03:
            alerts.append(f"🟡 {info['name']} 接近目标（差{cur-info['target']:.2f}）")
    
    if alerts:
        print("📡 监控触发\n\n" + "\n".join(alerts) + "\n\n" + "\n".join(status))
    else:
        print("📡 盯盘中\n\n" + "\n".join(status))
```

**Key design decisions:**
- Empty stdout = SILENT (nothing delivered to user). This is critical — don't spam status updates every 2 hours.
- Only output when there's something actionable (alert or near-alert).
- OR: always output status so user knows it's running (user preference — ask).
- Target prices: set based on support levels from recent K-line analysis, typically 8-12% below current price.

**Pitfall:** Script path must be relative to `~/.hermes/scripts/` (just filename), not absolute path.

### US-to-A-Share Catalyst Mapping

When major US semiconductor/storage stocks make dramatic moves overnight, check for A-share equivalents that may gap up at open:

| US Catalyst | A-Share Mapping | Example |
|-------------|-----------------|---------|
| 美光科技 (MU) +>10% | 佰维存储 (688525), 兆易创新 (603986), 深科技 (000021) | 2026-05-26: MU +19%, 瑞银目标价535→1625 |
| 英伟达 (NVDA) +>5% | 中际旭创 (300308), 天孚通信 (300394), 工业富联 (601138) | Copper/optical interconnect plays |
| AMD/英特尔移动 | 澜起科技 (688008), 通富微电 (002156) | CPU/GPU封装测试 |

**Action:** When such a catalyst is detected (via news search), the affected A-share position should be **held** (not sold) on the following day, as a gap-up open is likely. Only sell if the position was already at stop-loss BEFORE the catalyst and the gap-up offers a better exit price.

### "换仓" Pattern: Sell-Sector-A, Buy-Sector-B

When the user wants to exit one sector and enter a completely different one (e.g., sell chemicals, buy optical modules):

1. **Check positions** via `mx_stock_simulator_positions` — confirm what you're selling and current P&L
2. **Get real-time quotes** for 3-4 candidates in the TARGET sector **in parallel** — price, PE(TTM), main fund net flow
3. **Search news** for the target sector — latest catalysts, analyst recommendations, industry trends
4. **Present comparison table** — compact markdown table with: stock, price, PE, today's main fund flow, and a one-line verdict
5. **Recommend ONE** — don't just list possibilities; pick the best candidate with clear rationale
6. **Execute** — sell first (market price), then buy the chosen stock
7. **Report** — what sold, what bought, new positions, remaining cash

**Key difference from "卖了加":** The user is switching sectors entirely, not adding to existing positions. The comparison table is critical because the user needs education on the new sector's landscape.

**Comparison table format (proven pattern):**
```markdown
| 标的 | 现价 | PE | 今日主力净额 | 100股成本 | 评价 |
|------|------|------|-------------|-----------|------|
| 旭创 300308 | 1175 | 87.5x | -1.76亿 | ¥11.75万 | ❌ 买不起 |
| 新易盛 300502 | 713 | 66.2x | -2.68亿 | ¥7.14万 | ✅ 最优 |
```

### "全卖" Pattern: Sector Exit

When the user says "全卖了" / "退场" / "清仓" for a specific sector:

1. **Identify positions** in that sector from `mx_stock_simulator_positions`
2. **Place all sell orders in parallel** — market price, all at once (no need to check prices, user already decided)
3. **Report** — what was sold, total proceeds, total realized P&L for those positions
4. **Do NOT ask what to buy next** — the user said "退场", they may want to sit in cash. Wait for their next instruction.
5. **Check if related cron jobs exist** — if there was an auto-buy cron for that sector, offer to stop it

**Key difference from "换仓":** "全卖" = exit with no replacement. "换仓" = sell A to buy B. Don't suggest replacement stocks unless asked.

**When to stop cron jobs:** If the user had recurring auto-buy crons for the sold sector (e.g.,光模块加仓 cron), check `cronjob list` and offer to remove/pause them.

### "全买" Shorthand

When user says "全买" after a stock recommendation:
- Means: use ALL available cash to buy that stock (as many shares as budget allows, in multiples of 100)
- Calculate: `available_cash / stock_price`, round down to nearest 100
- Execute market buy immediately — no need to ask for confirmation
- Report: quantity bought, total cost, remaining cash (should be < ¥1000)

### Multi-Stock Full Allocation ("35w全买入" / "分仓全买")

When user wants to deploy ALL available funds across 2-3 specific stocks (e.g., "35w全买入烽火通信和中际旭创和东山精密"):

**Workflow:**
1. **Query all prices in parallel** — `mx_data` for each stock simultaneously
2. **Calculate optimal allocation** — maximize total deployment while respecting 100-share multiples:
   - Start with the most expensive stock (fewest shares, biggest per-unit cost)
   - Allocate 100 shares to it, subtract from budget
   - Repeat for next most expensive
   - With remaining budget, maximize the cheapest stock (most shares)
3. **Present allocation plan** before executing — table with stock, quantity, cost per stock, total
4. **Execute all buys in parallel** — `useMarketPrice=true` for each
5. **Check for balance issues** — if a buy fails with 501 (余额不足), reduce that stock's quantity by 100 and retry

**Key decisions (without asking user):**
- Always use `useMarketPrice=true` — user's casual tone means "just do it"
- Target ~100% fund deployment (< ¥1000 remaining)
- If one stock is very expensive (e.g., 中际旭创 ¥1248/股), 100 shares alone may consume 35%+ of budget — accept this and allocate remaining to others

**Example calculation (¥35万 budget):**
| Stock | Price | Shares | Cost | Notes |
|-------|-------|--------|------|-------|
| 中际旭创 300308 | ¥1248 | 100 | ¥124,800 | Expensive, start here |
| 东山精密 002384 | ¥233 | 500 | ¥116,830 | Maximize remaining |
| 烽火通信 600498 | ¥58 | 1900 | ¥110,257 | Cheapest, fill rest |
| **Total** | — | — | **¥351,887** | 100.5% deployment ✅ |

**If one stock fails (余额不足):**
- Don't cancel other successful orders
- Reduce failed stock by 100 shares → retry
- If still fails, allocate remainder to the cheapest stock instead
- Report what succeeded, what was adjusted

**⚠️ 100-share multiple requirement:** ALL A-share buys must be in multiples of 100 shares. Attempting 80, 250, or any non-100 quantity returns: `"buy quantity must be a multiple of 100"`. There is no way around this — always round quantities to the nearest 100.

### "卖了加" Pattern: Sell-to-Add

When the user confirms they want to sell a position to raise cash for other stocks:

1. **SELL FIRST** — sell the agreed position immediately (market price)
2. **Check balance** — wait for confirmation, then check available funds
3. **Buy second** — use the freed-up cash to buy the target stocks
4. **Simulated account quirk:** Market sell orders may show status=2 (pending) and not immediately release frozen funds. If a subsequent buy fails with insufficient funds:
   - ⚠️ **Do NOT try to cancel orders** — `mx_stock_simulator_cancel` is broken (see Pitfalls section). You cannot cancel stuck pending orders.
   - **Option A (best):** Wait for the sell to execute naturally. Check positions periodically; once `availCount` drops to 0 for the sold stock, funds are released. Then retry the buy.
   - **Option B:** If stuck for >5 minutes, retry the buy with a slightly lower limit price instead of market price — sometimes the simulator needs a price adjustment to match.
   - The bug: mx_stock_simulator_trade with useMarketPrice=true can get stuck in pending state, especially pre-market (before 9:30).
5. **Report** — what sold, what bought, new positions, remaining cash

#### ⚠️ Pre-Market Sell→Buy Timing (Session 2026-06-01)

**Critical:** Before market opens at 9:30, sell orders are queued as **status=1 (pending)** with `tradeCount=0` and `availCount` becomes 0 immediately, but **funds are NOT released** until the order executes at market open. If you try to buy immediately after placing a pre-market sell, you will get error code 501 "可用余额不足".

**Symptoms:**
- `mx_stock_simulator_positions` shows the sold stock with `availCount=0` but `count` unchanged
- `mx_stock_simulator_balance` still shows the old `availBalance`
- Buy orders return `code: 501, message: "委托失败，可用余额不足"`

**Solution:** Schedule buy orders via cron after market opens (e.g., 9:35 AM Beijing), so the sell has time to execute and settle:

```
cronjob create:
  schedule: "35 9 1 6 *"  (9:35 Beijing, one-shot)
  prompt: Check balance → if funds > needed amount → buy target stocks
  repeat: 1
```

**If selling before 9:30:** Place the sell order → create a cron at 9:35 to execute buys → verify order IDs in the cron result. Do NOT attempt buys in the same session as a pre-market sell.

### Consistency Rule

Never contradict a previous statement about trade status. If you said "I'll buy at X time" and then later say "I'm not buying because conditions changed", the user rightfully gets confused. Instead:

1. Execute the trade you promised, THEN assess
2. OR explain differently: "开盘我先观察5分钟，如果大盘不崩我就买入，否则等下午"
3. Never say both "I'll buy" and "I won't buy" for the same timeframe

### Time Accuracy — CRITICAL (User's #1 Frustration)

**User's exact words (2026-05-15):** *"你今早老乱说时间，然后马上又说对了"*

This user is extremely sensitive to incorrect time statements. The system timezone was initially UTC (showing 04:01 when it was 23:30 Beijing time), and even after fixing the timezone, the agent continued to misread the clock. This caused the user to lose trust.

**Common failure modes:**
- **UTC/CST confusion:** System shows UTC by default. Running `date` shows UTC unless timezone is set. Always check `date +%Z` first.
- **Misreading the display:** At 09:32, the agent said "现在是9:07" — this was a simple misread with no technical cause. Always double-check the `date` output.
- **Elapsed time estimation errors:** The user ordered at 16:43, but the agent said "快8个小时了" at 17:41 when it was only ~1 hour. Never guess elapsed time — calculate from exact timestamps or check `date` output to compute the difference.
- **Cron schedule confusion:** 8:30 AM Beijing = 00:30 UTC. Setting `30 8 * * 1-5` runs at 16:30 Beijing — wrong!

**Fix protocol:**
1. Before any time statement → call `date +'%Y-%m-%d %H:%M:%S %Z'`
2. Cron schedules: Beijing time - 8 hours = UTC expression
3. If unsure about the time → say "让我先看看时间" and call date
4. Never guess the time — the system time may differ from your expectation

### User Frustration Signals (Trading Context)

This user communicated SPECIFIC frustrations that MUST be avoided:

| User said | What they meant |
|-----------|-----------------|
| *"买了又说没买"* | Don't promise a trade and then backtrack. If you commit, execute. If conditions change, explain clearly and ask before changing the plan. |
| *"你今早老乱说时间"* | Never state the time without checking `date` first. One wrong time erodes all credibility. |
| *"炒股可不能这样啊"* | Trading requires decisiveness and consistency. Tentative / contradictory behavior is unacceptable. |
| *"然后马上又说对了"* | Correcting a mistake doesn't undo the damage — avoid making the mistake in the first place. |

**Implementation rule:** When the user says "执行" (execute):
1. Do NOT set a future cron
2. Do NOT say "等X分钟后再看"
3. Place the order IMMEDIATELY in the current session
4. Report back with: stock, quantity, price, total cost, remaining balance, stop-loss level

## Reference Files

| File | Content |
|------|---------|
| `references/hk-stock-trading-guide.md` | Hong Kong stock account opening routes for mainland users (2026) |
| `references/multi-agent-use-cases.md` | Real-world multi-agent use cases: support, finance, content, compliance |
| `references/a-share-core-assets.md` | Stable growth 白马股/核心资产 for defensive portfolio allocation |
| `references/2026-05-19-巨化止损记录.md` | Stop-loss execution example: 巨化股份 -7.16% |
| `references/2026-05-19-光模块分析.md` | Optical module sector analysis + buy plan (东山精密/光迅科技, cron scheduled for 2026-05-20 09:20) |
| `references/2026-05-20-盘前分析.md` | Pre-market analysis 2026-05-20: 6-holdings portfolio vs 2-holdings prompt mismatch, stop-loss violation on 巨化股份 (-11.55%), market environment |
| `references/2026-05-20-光模块买入执行.md` | 2026-05-20 trade execution: bought 东山精密 + 光迅科技 at open at ¥222.02 and ¥230.85 |
| `references/2026-05-27-盘前分析.md` | 2026-05-27 pre-market: 8-position full portfolio discovered, 领益智造(-5.25%) + 光迅科技(-8.24%) exceeded stop-loss, 美光MU +19% catalyst for 佰维存储 |
| `references/a-share-market-notes.md` | API error codes, concept speculation examples, account registration flow |
| `references/ai-energy-thesis.md` | AI-driven electricity demand thesis and A-share energy stocks |
| `references/multi-agent-trading-workflow.md` | Multi-agent AI workflow design, CrewAI/LangGraph, GPU comparison |
| `references/mx-data-quirks.md` | Real-world data quirks: double-encoded JSON, persisted large-output extraction recipe (双层json.loads + searchDataResultDTO路径 + mx_data字段码表), A+H dual-listing filter (300308 returns .SZ + .HK tables), order status codes, price restoration |
| `references/2026-08-05-盘前分析.md` | Pre-market 2026-08-05: 8/4 tech rally (创业板+5.64%), CPO/存储/设备 catalysts, prompt baseline stale again (巨化 absent, 佰维 700股), rebound-trim plan |
| `references/2026-08-12-盘前分析.md` | Pre-market 2026-08-12: prompt baseline stale 4th time (巨化 gone, 佰维 700股≠600股), tencent_quote 裸000001=平安银行指数坑 + tencent_quote_prefixed fix, mx_data truncation→腾讯API+push2his fallback, 佰维回购468.24上限利好, 美股指数跌但存储链涨 |
| `references/2026-06-01-领益卖出光模块加仓.md` | Pre-market sell→buy timing issue: status=1 pending orders, cron-deferred execution pattern |
| `references/2026-06-02-光模块清仓.md` | Sector full exit: sold 新易盛/光迅/东山精密, ~¥33万回笼, ~¥1.7万 realized loss |
| `references/xiaomi-supply-chain-stocks.md` | Xiaomi concept A-share supply chain stocks analysis |
| `references/a-stock-data-toolkit.md` | a-stock-data (⭐1.5k) — 7层28端点的全栈A股数据工具包，覆盖同花顺题材归因/龙虎榜/北向资金/研报PDF/融资融券等MX MCP不具备的能力 |

## Pitfalls

- **Research tool preference:** ALWAYS use BrightData (`mcp_brightdata_brightdata_invoke_tool` with `search_engine`) for web searches, NOT fetch/Baidu. Baidu search URLs (`baidu.com/s?wd=...`) are blocked by robots.txt for automated agents and return no useful data. BrightData bypasses these restrictions and returns clean structured results including Google/Bing/Yandex. The user explicitly formalized this preference: "以后我说让你去搜你就去brightdata和GitHub等权威网站搜".
- **Timezone confusion:** Cron schedules use UTC. 8:30 AM Beijing = 00:30 UTC. Double-check with `date +%Z` before creating.
- **MCP not loaded in current session:** Eastmoney MCP tools only appear after config.yaml is updated AND a new session starts. Existing conversations won't see them.
- **模拟账户未绑定:** After getting API key, you MUST visit https://dl.dfcfs.com/m/itc4 to bind a simulated account. The API returns code 404 "请先绑定账户~" otherwise.
- **金额单位厘:** All monetary values from the MX API are in 厘 (1/1000 元). Use `mx_amount_li_to_yuan` to convert.
- **A-shares hard to short:** Most retail accounts can only go long. Strategy should focus on long-only.
- **No real A-share broker MCP:** No MCP server currently supports real A-share trading through Chinese brokers (华泰, 中信, etc.). Only simulated trading via eastmoney MX, or US brokers (Robinhood/Schwab via open-stocks-mcp).
- **Cron reliability for one-shot trades:** One-shot cron jobs (`repeat: once`) may not appear in the cron list after creation and can fail silently. Always verify creation with `hermes cron list`, and prefer immediate manual execution via MCP tools when the user confirms a trade. **Session 2026-06-01 confirmed:** A cron at 9:35 (job `0da0d1ddb5d1`) was created, disappeared from the list after execution time, but the user never received any result — the job ran (or silently failed) and delivered nothing. User had to come back and ask "加仓了吗 也没发我结果啊". Bottom line: for any trade the user is waiting on, execute it directly in the current session. Only use cron for truly background/optional tasks.
- **Contradictory trade promises:** Never promise a trade at time X then change your mind at time X. If conditions change, acknowledge the conflict clearly: "I said I'd buy at 9:35 but the market is down 1% now — I'll buy a smaller position to stay consistent." Do NOT say both "I bought" and "I didn't buy."
- **Time accuracy:** Always call `date` before reporting the current time. UTC/CST confusion causes wrong cron schedules and wrong time estimates.
- **Stale holdings info in prompt:** The cron prompt may list specific holdings (e.g., "巨化股份2000股, 佰维存储600股") that are OUT OF DATE. The actual portfolio from `mx_stock_simulator_summary` may have more, fewer, or different stocks. Always trust the API response over the prompt text. After querying summary, if the holdings differ from the prompt's assumption, note this discrepancy explicitly in the analysis. **Confirmed recurring (5/20, 8/5, 8/12): the prompt baseline is stale almost every run** — 8/12 it listed 巨化股份 (sold 5/29) and 佰维 600股 (actual 700股), and omitted 5 real positions. Treat the prompt holdings block as fiction until verified. See `references/2026-08-12-盘前分析.md`.\n- **mx_data heavy queries unreliable in cron (truncation + no persisted file):** At 8:30 pre-market, multi-stock mx_data calls (e.g. "6持仓+指数" or "多股主力资金流向") return 170K-300K chars, get truncated with "Full output could not be saved to sandbox", and the `/tmp/hermes-results/call_*.txt` file is NOT created — contradicting the mx-data-quirks.md persistence recipe. **Operational fallback (verified 8/12):** for pre-market quotes use Tencent API directly (a-stock-data `tencent_quote_prefixed`, one call covers all holdings + indices with PE/PB/市值) and `push2his` daykline (lmt=5) for per-stock 主力/超大单净流入. Reserve mx_data for single-stock deep dives, and mx_search for news. Never block the 8:30 briefing on a giant mx_data call.
- **mx_stock_simulator_cancel is broken:** The cancel API consistently returns `code: 100, "操作类型错误，必须是'order'或者'all'的其中一种"` regardless of whether you pass `orderNo` or `cancelAll`. This appears to be an MCP tool parameter mapping issue — the underlying API expects a `type` field ('order' or 'all') that the MCP tool doesn't expose. **Workaround:** There is currently no way to cancel individual orders via the MCP tool. If a pending order has frozen funds and you need to retry, you cannot cancel it. Plan your order quantities carefully on the first attempt. If stuck with a frozen pending order, wait for it to either fill or expire at end of day (15:00).
- **Position count lag after fills:** After buy/sell orders are confirmed filled (status=4 in orders API), the positions API may still show the old count on the immediately subsequent query. Re-query positions after a brief pause (~1-2 seconds) to get updated counts. This is a caching/settlement delay in the simulator, not an actual failure.
- **⚠️ Trade API "成功" ≠ order filled (silent failure):** `mx_stock_simulator_trade` can return `code: 200, rc: 0, message: "成功"` while the order actually FAILED. Verified 2026-07-10: a market sell of 佰维存储 300股 returned success, but `mx_stock_simulator_orders(includeHistory=true)` later showed `status: 9` (失败/废单), `tradeCount: 0` — the shares stayed in the portfolio. The agent reported "三笔全部成交" when one had silently failed, and the user only discovered the truth weeks later when the position showed a -31% loss. **Fix (mandatory after EVERY trade batch):** call `mx_stock_simulator_orders(includeHistory=true, pageSize=50)` and verify the latest order for each stock has `status: 4` (成交) and `tradeCount == count`. If status is 9/3 (失败/废单), say so honestly ("X单失败未成交"), do NOT claim full execution, and re-place the order if the user still wants it. Also cross-check `mx_stock_simulator_positions` count afterwards — if the count didn't change for a sell, the order didn't fill.
- **enabled_toolsets blocks MCP tools:** Setting `enabled_toolsets: ["web"]` on a cron job makes eastmoney MCP tools (mx_data, mx_stock_simulator_trade, etc.) completely invisible. The cron session will attempt to find them, fail, and produce a useless result. **Fix:** Do NOT set enabled_toolsets on crons that need MCP — omit the `--toolsets` flag entirely, or set `enabled_toolsets: []`.
- **mx_data returns historical data before open:** If you call mx_data at 8:30 AM Beijing (before market opens at 9:30), the returned data will be from the PREVIOUS trading day's close, not live/streaming data. Price fields like "收盘价" and "涨跌幅" reflect the last completed session. This is expected behavior — use the previous close as the baseline for your pre-market analysis. After 9:30, the same query will return current-day data.
- **Self-select ≠ Holdings (自选股 ≠ 持仓):** `mx_selfselect_get()` returns the **watchlist** (自选股) — stocks the user is *watching*. `mx_stock_simulator_positions()` returns the **actual portfolio** (持仓) — stocks the user *owns*. When the user says "持仓" or "我有哪些股票", they mean their actual holdings, NOT their watchlist. Always use `mx_stock_simulator_positions()` for this. Using `mx_selfselect_get()` will show only 2-3 watched stocks and miss the full portfolio of 4-8+ actual positions. (Session 2026-06-05: user asked "现在我都有哪只股" and "持仓 你给我看持仓" — I initially showed watchlist data, user corrected.)
- **Mid-day order queuing (午间挂单):** Orders placed during lunch break (11:30-13:00 Beijing) are accepted by the simulator and queued with `status=2` (已报待成交). They automatically execute when the market reopens at 13:00. This is normal behavior — the orders are NOT stuck or failed. You can verify by checking `mx_stock_simulator_orders()` which will show `tradeCount=0` and `status=2` for queued orders. Do NOT cancel and re-place them.
- **⚠️ MX API daily quota — dormant account (错误 113):** 东方财富妙想 gives **only 10 API calls/day** when the account is dormant (休眠状态, triggered by low recent activity). Every mx_data/mx_search/mx_stock_simulator_* call counts against this quota — including calls made by OTHER cron jobs (the 8:30 pre-market analysis cron, the daily briefing, and manual quote queries all share the same 10/day pool). Once exhausted, every call returns `status: 113, message: "您的调用次数已达到上限...账户已经进入休眠状态，基础调用次数调整为10次/天，请前往东方财富APP，搜索妙想skill进行激活"`. **Fix:** user must open 东方财富APP → search 妙想 → activate/reactivate the skill. **Operational rule:** when scheduling a same-day batch-trade cron (e.g., 9:45 execution), the morning's quota may already be burned by the 8:30 pre-market cron + quote lookups — either reserve quota (skip pre-market mx queries on trade days) or verify quota before the execution cron runs. A trade batch that returns 113 for every order means the account is quota-starved, NOT that the market is closed.
- **⚠️ Market orders at/just after open can fail with 501 "获取行情最新价失败":** `mx_stock_simulator_trade(useMarketPrice=True)` needs a live quote to price the order. At 9:45 (15 min after open) the quote service may still be unavailable and returns `code: 501, message: "获取行情最新价失败，请稍后重试"` — all orders in the batch fail identically. This is transient: retry later in the session, or place a limit order with an explicit price instead of market price. Don't interpret 501 at open as a fundamental failure of the plan.
- **🔍 Debugging cron output:** every cron run stores its full prompt + response at `~/.hermes/cron/output/<job_id>/<timestamp>.md`. When a one-shot trade cron "disappears from the list" (it auto-removes after firing), check this directory to see exactly what it did — the response there shows which orders succeeded/failed and why. This is the first place to look when the user asks "买完了吗" and the trade didn't arrive.
