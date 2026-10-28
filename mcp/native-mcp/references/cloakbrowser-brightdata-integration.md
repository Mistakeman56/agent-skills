# CloakBrowser + BrightData Integration

Custom MCP server for stealth browser automation using CloakBrowser (Playwright-based anti-detection) and optionally BrightData Unlocker HTTP proxy.

## Architecture

```
Hermes Gateway
  └─ mcp-compressor (optional wrapper for stdio management)
        └─ /usr/bin/python3 ~/.hermes/scripts/cloakbrowser_mcp.py  (MCP server)
              └─ playwright chromium.launch()  (local headless browser)
                    └─ context proxy → BrightData Unlocker (optional)
```

## Two Proxy Patterns

### Pattern A: CDP via BrightData WS (deprecated/scraping_browser)

```
connect_over_cdp("wss://brd-customer-xxx-zone-scraping_browser1:password@brd.superproxy.io:9222")
```

- Remote browser hosted by BrightData
- Use `playwright.chromium.connect_over_cdp(ws_url)`
- No local Chromium needed
- **Token expires** — `zone-scraping_browser1` password can change without notice
- Was used successfully with password `mray43xcm7rd` (now expired)

### Pattern B: Local Chromium + BrightData Unlocker HTTP Proxy (current)

```python
BRIGHTDATA_PROXY = {
    "server": "http://brd.superproxy.io:33335",
    "username": "brd-customer-hl_50afbb6d-zone-mcp_unlocker",
    "password": "1xo2mrlvtg2b",
}

# launch with NO proxy
_browser = await _pw.chromium.launch(
    headless=True,
    args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"],
)

# per-page proxy = BrightData Unlocker
_context = await _browser.new_context(proxy=BRIGHTDATA_PROXY, ...)
```

- Local Chromium launched by CloakBrowser, pages routed through Unlocker
- Unlocker handles CAPTCHA/bot detection at page level
- Export IP comes from BrightData proxy network, not the local Clash node

## Pitfalls

### 1. Python venv mismatch
**Symptom:** Gateway log says `initial connection failed` with `unhandled errors in a TaskGroup` — no other details.
**Root cause:** Hermes gateway spawns MCP servers using `~/.hermes/hermes-agent/venv/bin/python3`, but CloakBrowser and Playwright are installed in system Python (`/usr/bin/python3`). The gateway venv doesn't have them.
**Fix:** Use absolute system python path in MCP config:
```yaml
  cloakbrowser:
    command: /usr/bin/python3    # NOT just "python3"
    args:
      - ~/.hermes/scripts/cloakbrowser_mcp.py
```

### 2. Sync API in asyncio loop
**Symptomy:** "It looks like you are using Playwright Sync API inside the asyncio loop. Please use the Async API instead."
**Root cause:** Gateway runs MCP servers in an asyncio event loop. The custom MCP server script must use `playwright.async_api` with `async/await`, not `playwright.sync_api`.
**Fix:** Use `from playwright.async_api import async_playwright` and make all browser operations async.

### 3. Missing `serverInfo` in initialize response
**Symptom:** `ValidationError: 1 validation error for InitializeResult — serverInfo Field required`
**Root cause:** MCP protocol requires `initialize` response to include a `serverInfo` object with `name` and `version`. Custom MCP scripts often omit this.
**Fix:**
```python
if method == "initialize":
    return {"jsonrpc": "2.0", "id": request_id, "result": {
        "protocolVersion": "2024-11-05",
        "serverInfo": {"name": "cloakbrowser", "version": "1.0.0"},
        "capabilities": {"tools": {}},
    }}
```

### 4. LXC outbound connectivity  
**Symptom:** `net::ERR_EMPTY_RESPONSE` or `net::ERR_CONNECTION_REFUSED`  
**Root cause:** LXC container may not have outbound internet. In this user's setup, LXC 202 (Hermes host) has outbound via iptables/clash routing on 192.0.2.10:7890 (authenticated proxy). Playwright's `--proxy-server` flag does NOT support authentication (`user:pass@host:port` format), only raw host:port.  
**Workarounds:**  
1. **LXC with default route outbound** — no proxy config needed at all (browser just works) 👍 This user's LXC 202 actually has direct outbound via iptables forwarding to Clash, so Playwright can make direct HTTPS connections (exit IP 203.0.113.1 — the Clash node IP). No proxy config in launch or context needed.  
2. **Context-level proxy** — `browser.new_context(proxy={...})` supports auth but is per-page, not per-connection. Only useful if the proxy target is reachable directly from LXC  
3. **SOCKS5 proxy** — if available without auth, can be used with `--proxy-server`  

**Key lesson learned:** Always test `playwright.chromium.launch()` with NO proxy first — LXC may already have outbound routing. The user's setup (Clash on 192.0.2.10) routes all traffic from LXC 202 through the proxy at network level. Trying to add proxy layers on top of that causes `ERR_EMPTY_RESPONSE`.

### 5. BrightData Unlocker proxy vs Scraping Browser
BrightData has two browser products with different connection methods:

| Product | Endpoint | Port | Auth Method | Use Case |
|---------|----------|------|-------------|----------|
| Scraping Browser | `wss://...@brd.superproxy.io` | `:9222` | WS URL with user:pass | Remote browser (CDP) |
| Web Unlocker | `http://brd.superproxy.io` | `:33335` | HTTP proxy auth | Local browser via proxy |

The Unlocker (port 33335) works with curl via SOCKS/HTTP proxy but has **inconsistent Playwright support** — context-level proxy may return `ERR_EMPTY_RESPONSE` for HTTPS sites depending on Playwright/chromium version.

## Testing

```bash
# Test Unlocker proxy with curl (via Clash for outbound)
curl -x "http://Clash:password@192.0.2.10:7890" \
  --proxy-user "brd-customer-hl_50afbb6d-zone-mcp_unlocker:1xo2mrlvtg2b" \
  "https://httpbin.org/ip"

# Test BrightData Unlocker directly
curl --proxy brd.superproxy.io:33335 \
  --proxy-user "brd-customer-xxx-zone-mcp_unlocker:password" \
  -k "https://geo.brdtest.com/welcome.txt?product=unlocker&method=native"
```
