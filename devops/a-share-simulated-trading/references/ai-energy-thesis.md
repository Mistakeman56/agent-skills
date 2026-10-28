# AI + Energy Investment Thesis (AI驱动电力需求)

## Core Thesis

**AI needs massive amounts of electricity, and this demand is structural (not cyclical):**

- A single ChatGPT query costs ~10x the electricity of a traditional Google search
- Global data center electricity consumption is projected to **double by 2030**, reaching 8-10% of total global electricity
- Training a single large model costs **millions of dollars in electricity**
- Inference (actual usage) costs are even higher than training and growing faster
- AI "Token出海" (Chinese models expanding overseas) further multiplies compute demand
- This is **exponential, not linear** growth — unlike traditional industrial electricity demand

## Who Benefits in A-Shares

### Tier 1: Power Generators (Most Direct, Most Certain)

The logic: AI data centers need guaranteed 24/7 power supply. More data centers → more electricity sold. No tariff risk (power purchase agreements are long-term).

| Code | Name | PE | 3Y PE%ile | Thesis | Verdict |
|:----:|:-----|:--:|:---------:|:-------|:-------:|
| **600900** | **长江电力** | **18.3x** | **0.55%** 🟢 | Hydro king, lowest marginal cost per kWh, stable output, AI can't run without power | **BUY — near 3yr low** |
| 601985 | 中国核电 | 22.8x | 89.52% 🔴 | Nuclear runs 24/7, perfect for data center base load, zero-carbon mandate | WAIT — PE too high |
| 600905 | 三峡能源 | ~22x | ~50% 🟡 | Wind+solar leader, green power policy support | HOLD — mid-range |
| 600886 | 国投电力 | ~15x | ~30% | Hydro + thermal mix, underexposed | OBSERVE |

### Tier 2: Grid Infrastructure (Highest Growth Elasticity)

As more data centers connect, the grid needs massive upgrades in transmission, distribution, and intelligent dispatch.

| Code | Name | What They Do | Thesis |
|:----:|:-----|:-------------|:-------|
| 600406 | 国电南瑞 | Grid automation & intelligent dispatch | AI调度需求爆发式增长 |
| 601567 | 三星医疗 | Smart meters, power distribution | 数据中心配电设备 |
| 002028 | 思源电气 | Power electronics, transformers | High-voltage equipment for data center substations |

### Tier 3: Data Center Infrastructure

| Code | Name | What They Do | Thesis |
|:----:|:-----|:-------------|:-------|
| 002837 | 英维克 | Data center cooling | AI chips run hot → need more cooling |
| 300738 | 奥飞数据 | IDC data center operator | Direct beneficiary of AI computing demand |
| 603881 | 数据港 | IDC + cloud infrastructure | Alibaba/GCP data center partner |

## Cautions & Risks

1. **电价管制 (Price controls):** Chinese electricity prices are government-regulated. Power generators can't freely raise prices even if demand spikes. Revenue grows with volume, not price.
2. **Coal cost exposure:** ~60% of China's electricity is still coal-fired. Coal price volatility compresses thermal power margins.
3. **Long project lead times:** Nuclear plants take 7-10 years from approval to operation. Hydro projects 5-8 years. Supply can't respond quickly to demand.
4. **Market already pricing in some expectation:** Many energy stocks have already risen on general "green power" sentiment. The pure AI-additional-demand thesis may not be fully priced in yet.
5. **Regional mismatch:** Data centers concentrate in coastal cities (Beijing, Shanghai, Shenzhen), but power generation is often in remote areas (Yunnan, Sichuan, Inner Mongolia). Transmission bottlenecks exist.

## Recommended Strategy

### If User Asks About Energy Stocks:

1. **Always check PE 3-year percentile first** — the energy sector trades heavily on narrative; valuation tells you if the narrative is already priced in.
2. **Severely undervalued (< 20% percentile):** 长江电力 at 0.55% — strong buy signal
3. **Overvalued (> 80% percentile):** 中国核电 at 89.5% — wait for pullback
4. **Preferred allocation:** 70% power generator (长江电力) + 30% grid infrastructure (国电南瑞) if user wants pure energy play
5. **Alternative combo:** 30% 长江电力 as defensive foundation + 70% growth stocks (Xiaomi concept, AI, etc.)

### Key Data Points to Fetch When Analyzing Energy Stocks

```
mx_data: "长江电力 600900 最新行情 估值 PE PB 股息率"
→ Extract: PE(TTM), PB, 3-year PE percentile, dividend yield

mx_data: "中国核电 601985 最新行情 估值 PE PB 股息率"
→ Extract: PE(TTM), PB, 3-year PE percentile

mx_data: "国电南瑞 600406 最新行情 估值 PE PB"
→ Extract: PE(TTM), PB, 3-year PE percentile
```

## Session History

- 2026-05-16: User independently raised the AI+energy thesis ("未来五年能源概念股是不是会飞升，因为AI需要很多很多电力"). This was their own insight, not prompted. After data analysis, agreed on 长江电力 (600900) as the best current buy given 0.55% PE percentile. User added it to Monday buy list alongside Xiaomi concept stocks. Portfolio plan: 70% 小米概念 + 30% 长江电力底仓.
