# A-Share Market Notes

## Concept Speculation Examples

### 椰树牌矿泉水 → ST椰岛 (2026-05-14)

**Event:** During a state dinner for Trump's visit to China, 椰树牌 coconut water appeared on the banquet table. The next day, ST椰岛 (stock code: 600238) — a company that produces coconut-based products — hit the daily limit up (+5%).

**Key facts:**
- 椰树 (coconut tree brand) and ST椰岛 (Hainan Yedao) are COMPLETELY DIFFERENT companies
- They share only the character "椰" (coconut) in their names
- ST椰岛 is a special-treatment (ST) stock with fundamental problems
- The rally has no fundamental basis — pure name association speculation

**Implication for trading strategy:**
- Monitor banquet/state dinner appearances of consumer brands
- Track companies with names similar to trending brands
- Add "ST" stocks to watchlist when related news breaks — they have smaller floats and can spike harder
- Be ready to exit quickly — these rallies are short-lived

## API Error Codes

| Code | Meaning | Fix |
|------|---------|-----|
| 404 | 请先绑定账户~ | Visit https://dl.dfcfs.com/m/itc4 to bind simulated account |
| 113 | 调用次数达到上限 | Upgrade API key on 妙想 platform |
| 114/116 | 密钥无效 | Check MX_APIKEY |
| 501 | 交易失败 | Non-trading hours, insufficient balance, or price violation |

## Account Registration Flow

1. Visit https://marketing.dfcfs.com/views/finskillshub/indexIoMv0EzE
2. Click "立即领取" (Claim Now) button
3. Register → receive MX_APIKEY (新用户送5000额度)
4. Visit https://dl.dfcfs.com/m/itc4 to bind simulated trading account
5. Default simulated capital: 1,000,000 元 (100万)

## Key MCP Endpoints

- Base URL: `https://mkapi2.dfcfs.com/finskillshub/api/claw`
- Headers: `{"apikey": "your-key", "Content-Type": "application/json"}`
- All amounts in 厘 (1/1000 元). Divide by 1000 to get 元.
