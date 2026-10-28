# a-stock-data 已验证端点速查（Hermes LXC 202, 2026-05-20）

## ✅ 全部可用（仅需 requests, 零鉴权）

| 端点 | 调用方式 | 响应速度 | 说明 |
|------|---------|:--------:|------|
| 腾讯行情 | `tencent_quote([codes])` | ~0.3s | PE/PB/市值/盘口/涨跌停价 |
| 同花顺热点 | `ths_hot_reason(date)` | ~80ms | 当日强势股+题材归因reason tags |
| 北向资金 | `hsgt_realtime()` | ~0.5s | 沪/深股通分钟级262点 |
| 行业排名 | `industry_comparison(n)` | ~0.5s | 东财全行业涨跌/领涨股 |
| 全市场龙虎榜 | `daily_dragon_tiger(date)` | ~0.8s | 当日上榜+净买额排名 |
| 龙虎榜席位 | `dragon_tiger_board(code, date)` | ~1.5s | 个股上榜+买卖席位TOP5+机构 |
| 东财研报 | `eastmoney_reports(code)` | ~1s | 研报列表+评级+EPS预测 |
| 东财资金流(分钟级) | `eastmoney_fund_flow_minute(code)` | ~0.5s | 主力/大单/中单/小单 |
| 个股资金流120日 | `stock_fund_flow_120d(code)` | ~0.5s | 日级主力净流入 |
| 融资融券 | `margin_trading(code)` | ~0.8s | 日级融资余额/买入/偿还 |
| 大宗交易 | `block_trade(code)` | ~0.8s | 溢价率+买卖方 |
| 股东户数 | `holder_num_change(code)` | ~0.8s | 季度级筹码集中度 |
| 分红送转 | `dividend_history(code)` | ~0.8s | 每股派息/送股/转增 |
| 限售解禁 | `lockup_expiry(code, date)` | ~0.8s | 历史+未来90天 |
| 东财个股新闻 | `eastmoney_stock_news(code)` | ~0.5s | 个股相关新闻 |
| 财联社快讯 | `cls_telegraph()` | ~0.5s | 全市场实时电报 |
| 东财全球资讯 | `eastmoney_global_news()` | ~0.5s | 7x24财经快讯(需uuid) |
| 东财个股信息 | `eastmoney_stock_info(code)` | ~0.3s | 行业/总股本/市值/上市日期 |
| 巨潮公告 | `cninfo_announcements(code)` | ~1s | 全文检索 |

## ❌ 已知不可用

| 端点 | 原因 | 替代方案 |
|------|------|---------|
| 百度概念板块 | `ResultCode=10003` 接口已变更 | 同花顺热点的reason字段间接看题材 |
| mootdx TCP行情 | LXC无国内IP，TCP 7709不通 | 腾讯财经替代 |
| mootdx 财务/F10 | 同上 | 东财个股信息+新浪三表 |
| iwencai | 需API Key(未申请) | 东财研报替代 |

## ⚠️ 需注意

- **百度概念板块** `ResultCode` 可能返回 `10003`（接口变更）或 `0`/`"0"`（不稳定），用 `str()` 统一比较
- **腾讯行情** 编码为GBK，必须 `decode("gbk")`
- **东财全球资讯** 需要 `req_trace=uuid4()` 参数，否则403
- **巨潮公告** orgId格式：沪=`gssh0{code}`, 深=`gssz0{code}`, 北=`gsbj0{code}`
- **全市场龙虎榜** 非交易日/盘后未更新时返回空数据
