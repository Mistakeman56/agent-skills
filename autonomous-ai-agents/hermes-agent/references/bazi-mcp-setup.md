# Bazi (八字) MCP Server

## Repository
- **repo**: `cantian-ai/bazi-mcp` (⭐372)
- **description**: MCP server for Chinese Bazi (八字) fortune telling — four pillars, ten gods, hidden stems, nayin, great luck periods, spirits, punishments/combinations
- **requirements**: Node.js 22+

## Installation

### Local (LXC/Hermes host)
```bash
npm install -g bazi-mcp
```

### Via LXC 200 (if Node >=22)
Create wrapper script `/opt/mcp-start-bazi.sh`:
```bash
#!/bin/bash
export PATH="/root/.local/bin:$PATH"
exec npx bazi-mcp
```

Then add to Hermes config:
```yaml
mcp_servers:
  bazi:
    command: npx
    args:
    - bazi-mcp
    timeout: 30
```

## Tool Reference

### `getBaziDetail`
Get full Bazi reading from date and gender.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `solarDatetime` | string | No* | ISO format with timezone, e.g. `2005-05-06T02:00:00+08:00` |
| `lunarDatetime` | string | No* | Lunar date, e.g. `2000-5-5 12:00:00` |
| `gender` | number | **Yes** | `0` = female, `1` = male |
| `eightCharProviderSect` | number | No | `1` = 23:00-23:59 next day's stem, `2` = same day (default) |

*Must pass exactly one of `solarDatetime` or `lunarDatetime`.

**Output includes:**
- 四柱 (year/month/day/hour pillars) with 天干/地支/五行/阴阳/十神
- 藏干 (hidden stems) with 主气/中气/余气
- 纳音 (nayin) for each pillar
- 神煞 (spirits) per pillar
- 大运 (great luck) — full 10-year periods with ages
- 胎元/胎息/命宫/身宫
- 刑冲合会 (punishments/combinations/harmonies)

### `getChineseCalendar`
Get Chinese almanac info for a date.

**Parameters:** optional date string, defaults to today.

**Output includes:** zodiac, nayin, solar terms, 28 mansions, auspicious/directions/conflict info.

## Known Pitfalls
- **gender must be a number**, not a string — `1` not `"男"`
- **ISO format required for solarDatetime** — include timezone offset `+08:00`
- **丑时 = 01:00-03:00**, use `T02:00:00` as middle point
- After adding to config, run `/reload-mcp` in the active session or restart gateway — config change alone isn't enough for the current session
- Node.js <22 will fail; LXC 200 has v20, so install on host (LXC 202) not via SSH wrapper
