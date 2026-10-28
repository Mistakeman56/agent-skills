# MCP Ecosystem Research (2026-05)

## Top MCP Servers by Usefulness (for our setup)

### Already Installed (all on LXC 200 via SSH)

| # | Name | Stars | Free | Purpose |
|---|------|:-----:|:----:|---------|
| 1 | Bright Data | 2.4K | 5000/mo | Search + Scrape + Anti-block |
| 2 | Context7 | 54K | ✅ | Real-time tech docs for coding |
| 3 | Playwright | 30K | ✅ | Browser automation (JS rendering) |
| 4 | GitHub | 15K | ✅ | Code search, PR/Issue management |
| — | Amap (高德) | — | ✅* | Maps, geocoding, routing (CN) |
| — | Zhipu (智谱) | — | ✅* | Multi-engine Chinese search |
| — | Excel | — | ✅ | Excel read/write without MS Office |

*Amap and Zhipu need free API keys from their respective platforms.

### Recommended but Not Installed

| Name | Why | When to Add |
|------|-----|-------------|
| PDF Reader | Read PDFs, extract text/tables | When we need document processing |
| PaddleOCR | Chinese OCR | When we need image→text |
| A-Stock-Market | China A-share data | If financial analysis needed |
| Docker MCP | Container management | If we go heavy on Docker |
| PostgreSQL MCP | Database direct access | If we set up a database |

### Industry Context

- **14,000+ MCP servers** on PulseMCP as of May 2026
- MCP donated to Linux Foundation (AAIF) Dec 2025 — now multi-vendor standard
- **Major players**: Anthropic (origin), OpenAI, Google, Microsoft, AWS all on board
- **Security**: OX Security April 2026 found systemic RCE affecting all SDKs — only install trusted packages

## Search Quality Comparison

| Engine | Chinese Quality | Our Setup |
|--------|:--------------:|-----------|
| Bright Data (Google-backed) | ⭐⭐⭐⭐⭐ | ✅ Primary |
| Bing (via open-websearch) | ⭐ | ❌ Abandoned — returns irrelevant results for CN queries |
| Baidu | ⭐⭐⭐ | Not tested |
| Zhipu (aggregator) | ⭐⭐⭐⭐ | ⚠️ Needs API key |

## Cost Analysis: MCP vs CLI

From Scalekit benchmark (Claude Sonnet, GitHub ops):
- Simple query: CLI 1,365 tokens vs MCP 44,026 (32x)
- Complex query: CLI 5,010 tokens vs MCP 33,712 (7x)
- Monthly (10K ops): CLI $3.20 vs MCP $55.20

**Rule of thumb**: Local dev workflow → CLI. External service integration → MCP.

## Package Name Pitfalls

Articles/blog posts frequently list wrong npm package names. Always verify:
1. Search npm registry directly
2. Or check the GitHub repo's package.json
3. The `bin` field in package.json is the actual command name, NOT the package name
