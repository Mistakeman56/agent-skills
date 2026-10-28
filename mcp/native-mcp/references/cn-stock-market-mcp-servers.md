# Chinese Stock Market MCP Servers

Research conducted 2026-05-14. Covers MCP servers for A-share data, simulated trading, and real trading.

## Summary Table

| MCP Name | Type | A-Share Data | A-Share Trading | Install | Free | Stars |
|----------|------|-------------|----------------|---------|------|-------|
| **akshare-one-mcp** | Data query | ✅ Full (A/B/H) | ❌ | Easy (`uvx`) | ✅ | 170 |
| **stock-mcp** | Data query | ✅ Full | ❌ | Easy | ✅ | 7 |
| **cn-funds-mcp** | Data+portfolio | ✅ Funds+A-shares | ❌ (management only) | Easy | ✅ | 4 |
| **eastmoney-mx-finance** | Data+simulated trade | ✅ Full | ⚠️ Simulated only | Medium (needs API key) | ⚠️ Free tier | <1 |
| **A-Scope-Research** | AI analysis | ✅ | ❌ | Medium (needs LLM key) | ⚠️ | 7 |
| **FinanceMCP-Alpha** | Quant factors | ✅ (needs Tushare token) | ❌ | Medium | ⚠️ | 4 |

## A-Share Dedicated Servers

### akshare-one-mcp (⭐170)
- **Repo**: [zwldarren/akshare-one-mcp](https://github.com/zwldarren/akshare-one-mcp)
- **Features**: Historical quotes, real-time data, news, financial statements (3 sheets), insider trading data, technical indicators (MA/MACD/RSI/Bollinger)
- **Install**: `uvx akshare-one-mcp`
- **Pros**: Richest data source, multi-source (EastMoney/Sina), free no API key, technical indicator calculation
- **Cons**: Query only, no trading; depends on akshare library
- **Hermes config**:
  ```yaml
  akshare:
    command: "uvx"
    args: ["akshare-one-mcp"]
  ```

### stock-mcp (⭐7)
- **Repo**: [very99/stock-mcp](https://github.com/very99/stock-mcp)
- **Features**: Real-time quotes (Sina/Tencent/EastMoney cross-validation), 60+ day history, technical indicators (MA5/10/20/60, RSI, MACD, volume ratio, turnover rate), news sentiment, market overview
- **Install**: `git clone → npm install → npm run build`, then configure MCP client to point at `dist/index.js`
- **Pros**: Multi-source cross-validation, good Chinese support
- **Cons**: Query only; Node.js requires local build

### cn-funds-mcp (⭐4)
- **Repo**: [smallke/cn-funds-mcp](https://github.com/smallke/cn-funds-mcp)
- **Features**: Fund search/valuation/holdings/nav history, A-share tick-by-tick/real-time quotes, market overview/capital flow (main force/northbound), sector capital flow, portfolio management, scheduled reminders
- **Install**: `git clone → npm install → npm start`
- **Pros**: Most comprehensive China fund+stock MCP! Includes portfolio management, scheduled profit reminders, capital flow analysis, no API key needed
- **Cons**: Query only, no real/simulated trading

### eastmoney-mx-finance-mcp-server
- **Repo**: [jm12138/eastmoney-mx-finance-mcp-server](https://github.com/jm12138/eastmoney-mx-finance-mcp-server)
- **Features**: Based on EastMoney·妙想(MX) API. 12 tools covering news search, financial data queries, smart stock selection (natural language), portfolio management, and **simulated trading** (buy/sell orders, cancel, order history, position/summary)
- **Dependencies**: `mcp[cli]>=1.0.0`, `httpx>=0.27.0` (both likely already in Hermes venv)
- **Install**:
  ```bash
  # Preferred: install with dependencies
  pip install /path/to/eastmoney-mx-finance-mcp-server
  
  # If proxy blocks pip install (common behind Clash proxy): install via Hermes venv with --no-deps
  ~/.hermes/hermes-agent/venv/bin/pip install /path/to/repo --no-deps
  ```
  All deps (`mcp`, `httpx`, `typer`) are already present in the Hermes venv, so `--no-deps` is safe.
- **API Key**: Register at the **东方财富妙想 platform**: [marketing.dfcfs.com/views/finskillshub/indexIoMv0EzE](https://marketing.dfcfs.com/views/finskillshub/indexIoMv0EzE)
  - Page has a **「立即领取」** (Claim Now) button under "API KEY 新用户注册即送额度5000"
  - Click it → register/login → get `MX_APIKEY`
  - Alternative link: [clawhub.ai](https://clawhub.ai/u/QQK000) (personal invite, less reliable)
- **Hermes config**:
  ```yaml
  mcp_servers:
    eastmoney-mx:
      command: ~/.hermes/hermes-agent/venv/bin/eastmoney-mx-finance-mcp-server
      args:
      - stdio
      env:
        MX_APIKEY: "your-api-key-here"
      timeout: 30
  ```
- **Error codes** (from server.py):
  - `113`: 调用次数达到上限
  - `114/116`: 密钥无效
  - `404`: 未绑定模拟账户 (go to [dl.dfcfs.com/m/itc4](https://dl.dfcfs.com/m/itc4))
  - `501`: 交易失败 (非交易时段/余额不足/价格不符规则)
- **Tools**:
  | Tool | Description |
  |------|-------------|
  | `mx_search(query)` | News/search (news, announcements, research reports, policy) |
  | `mx_data(toolQuery)` | Financial data queries (quotes, capital flow, financials, executives) |
  | `mx_select_stock(keyword, pageNo, pageSize)` | Smart stock selection by natural language |
  | `mx_selfselect_get()` | Query watchlist |
  | `mx_selfselect_manage(query)` | Add/remove watchlist items |
  | `mx_stock_simulator_balance()` | Simulated account balance |
  | `mx_stock_simulator_positions()` | Simulated account positions |
  | `mx_stock_simulator_trade(type, stockCode, quantity, useMarketPrice, price)` | Buy/sell orders |
  | `mx_stock_simulator_cancel(orderNo, cancelAll)` | Cancel orders (single/all) |
  | `mx_stock_simulator_orders(pageNo, pageSize, includeHistory)` | Order/history query |
  | `mx_stock_simulator_summary()` | Combined balance+positions summary |
- **Pros**: Only A-share MCP with trading capability (simulated)
- **Cons**: Needs API key registration; simulated not real trading
- **Note**: Amount fields in "厘" (1元=1000厘) — must use `mx_amount_li_to_yuan()` to convert

### A-Scope-Research (⭐7)
- **Repo**: [guangxiangdebizi/A-Scope-Research](https://github.com/guangxiangdebizi/A-Scope-Research)
- **Features**: Multi-agent A-share analysis system (technical/fundamental/quantitative/sentiment/risk-control 5 analysts debating), Streamlit web UI
- **Pros**: Multi-agent debate analysis, supports multiple LLM backends (OpenAI/Zhipu/Qwen/etc.)
- **Cons**: Needs additional LLM API key; no trading; it's a top-level application

### FinanceMCP-Alpha (⭐4)
- **Repo**: [guangxiangdebizi/FinanceMCP-Alpha](https://github.com/guangxiangdebizi/FinanceMCP-Alpha)
- **Features**: Tushare-based WorldQuant 101 Alpha factor calculator. Supports 7 Alpha factors (Alpha3/13/15/16/44/50/55) real-time computation
- **Pros**: Quant trading dedicated, Alpha factor calculation
- **Cons**: Needs Tushare Token (free registration), factor calculation only, no trading

## International Servers (Reference Only)

### open-stocks-mcp (⭐4)
- **Repo**: [Open-Agent-Tools/open-stocks-mcp](https://github.com/Open-Agent-Tools/open-stocks-mcp)
- **Features**: Robinhood + Schwab multi-broker MCP, 104 tools covering account/market data/options/order management
- **Real Trading**: ✅ Yes (Robinhood/Schwab)
- **China A-shares**: ❌ No

### ibkr-mcp-server (multiple forks)
- **Repos**: GaoChX/ibkr-mcp-server, jinyiabc/ibkr-mcp
- **Features**: Interactive Brokers MCP, account management, market data, real trading
- **Real Trading**: ✅ Yes (through IBKR)
- **China A-shares**: ⚠️ Indirect (IBKR supports Hong Kong Stock Connect, limited China ETFs)

## Alipay MCP

**Does not exist.** The only search result `alipay-mini-mcp` (yssmiac7/alipay-mini-mcp, 0 stars) compiles and analyzes Alipay mini-programs — unrelated to finance/trading.

## Recommendations

### For data analysis (install on Hermes):
```yaml
# Best all-in-one A-share data
akshare:
  command: "uvx"
  args: ["akshare-one-mcp"]
```

### For simulated trading practice:
Install `eastmoney-mx-finance-mcp-server` via pip, register API key at clawhub.ai, then configure with env var.

### For real A-share trading:
**No MCP solution exists yet.** Chinese broker APIs (华泰 xtquant, 中信 QMT) are closed systems requiring account + capital threshold. Real trading requires manual operation or self-developed QMT/PTrade integration.

## Hermes Built-in Finance Skills (Not for Stock Trading)

Under `optional-skills/finance/`:
- `3-statement-model` — Financial modeling
- `dcf-model` — DCF valuation
- `comps-analysis` — Comparable company analysis
- `lbo-model` — LBO modeling
- `merger-model` — M&A modeling
- `excel-author` — Excel modeling
- `pptx-author` — Finance PPT

These are investment banking skills, unrelated to A-share stock trading.
