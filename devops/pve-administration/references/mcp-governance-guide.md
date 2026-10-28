# MCP Server Governance (Consolidated from mcp-governance)

## Audit Framework
Classify every MCP server in `~/.hermes/config.yaml`:

| Category | Criteria | Action |
|----------|----------|--------|
| **Core** | Used every session (memory, filesystem, time) | **Keep** |
| **Regular** | Used at least once per week (brightdata, github, eastmoney-mx, simple-rag) | **Keep** |
| **Situational** | Used occasionally (amap, bazi, cloakbrowser, engram, homeassistant) | **Keep but note** |
| **Rare/Never** | Haven't used in 30+ days, no clear use case | **Remove** |

## Removal Process
1. Delete entry from `mcp_servers` section in config.yaml
2. Run `hermes tools` or `/reload-mcp` to verify clean load
3. Check for duplicate entries

## Essential MCPs (Never Remove)
- **GitHub** — essential for repo inspection; fix via proxy routing, not deletion
- **BrightData** — primary search/scrape tool
- **CloakBrowser** — for Cloudflare/login-walled sites (installed with effort, don't waste)
- **simple-rag** — stores structured knowledge bases
- **engram** — structured long-tail memory (different from Hermes memory)

## Memory Layering
| Storage | Purpose | Injection | Size |
|---------|---------|-----------|------|
| **Hermes Memory** | High-frequency/emergency facts | Auto-injected every session | Keep < 1500 chars |
| **Engram** | Knowledge, preferences, project history | Proactive query at session start | Unlimited |

**Rule:** Prefix every session with an engram search for context before assuming nothing is stored.

## CloakBrowser vs BrightData Strategy
- **BrightData**: General web search, scraping, discovery
- **CloakBrowser**: Sites behind Cloudflare, CAPTCHA, complex web apps
- They are **complementary, not alternatives**

## Pitfalls
- After editing config.yaml, always reload MCP to catch syntax errors
- Watch for duplicate entries (same MCP server listed twice)
- YAML serialization can corrupt — use `yq` or Python, not sed/echo
- Don't delete engram just because memory exists — they serve different purposes
- Don't remove RAG — it stores exam prep materials and structured knowledge
