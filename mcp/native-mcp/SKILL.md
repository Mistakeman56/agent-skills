---
name: native-mcp
description: "MCP client: connect servers, register tools (stdio/HTTP)."
version: 1.0.1
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [MCP, Tools, Integrations]
    related_skills: [mcporter]
---

# Native MCP Client

Hermes Agent has a built-in MCP client that connects to MCP servers at startup, discovers their tools, and makes them available as first-class tools the agent can call directly. No bridge CLI needed -- tools from MCP servers appear alongside built-in tools like `terminal`, `read_file`, etc.

## When to Use

Use this whenever you want to:
- Connect to MCP servers and use their tools from within Hermes Agent
- Add external capabilities (filesystem access, GitHub, databases, APIs) via MCP
- Run local stdio-based MCP servers (npx, uvx, or any command)
- Connect to remote HTTP/StreamableHTTP MCP servers
- Have MCP tools auto-discovered and available in every conversation

For ad-hoc, one-off MCP tool calls from the terminal without configuring anything, see the `mcporter` skill instead.

## Prerequisites

- **mcp Python package** -- optional dependency; install with `pip install mcp`. If not installed, MCP support is silently disabled.
- **Node.js** -- required for `npx`-based MCP servers (most community servers)
- **uv** -- required for `uvx`-based MCP servers (Python-based servers)

Install the MCP SDK:

```bash
pip install mcp
# or, if using uv:
uv pip install mcp
```

## Quick Start

Add MCP servers to `~/.hermes/config.yaml` under the `mcp_servers` key:

```yaml
mcp_servers:
  time:
    command: "uvx"
    args: ["mcp-server-time"]
```

Restart Hermes Agent. On startup it will:
1. Connect to the server
2. Discover available tools
3. Register them with the prefix `mcp_time_*`
4. Inject them into all platform toolsets

You can then use the tools naturally -- just ask the agent to get the current time.

## Configuration Reference

Each entry under `mcp_servers` is a server name mapped to its config. There are two transport types: **stdio** (command-based) and **HTTP** (url-based).

### Stdio Transport (command + args)

```yaml
mcp_servers:
  server_name:
    command: "npx"             # (required) executable to run
    args: ["-y", "pkg-name"]   # (optional) command arguments, default: []
    env:                       # (optional) environment variables for the subprocess
      SOME_API_KEY: "value"
    timeout: 120               # (optional) per-tool-call timeout in seconds, default: 120
    connect_timeout: 60        # (optional) initial connection timeout in seconds, default: 60
```

### HTTP Transport (url)

```yaml
mcp_servers:
  server_name:
    url: "https://my-server.example.com/mcp"   # (required) server URL
    headers:                                     # (optional) HTTP headers
      Authorization: "Bearer sk-..."
    timeout: 180               # (optional) per-tool-call timeout in seconds, default: 120
    connect_timeout: 60        # (optional) initial connection timeout in seconds, default: 60
```

### All Config Options

| Option            | Type   | Default | Description                                       |
|-------------------|--------|---------|---------------------------------------------------|
| `command`         | string | --      | Executable to run (stdio transport, required)     |
| `args`            | list   | `[]`    | Arguments passed to the command                   |
| `env`             | dict   | `{}`    | Extra environment variables for the subprocess    |
| `url`             | string | --      | Server URL (HTTP transport, required)             |
| `headers`         | dict   | `{}`    | HTTP headers sent with every request              |
| `timeout`         | int    | `120`   | Per-tool-call timeout in seconds                  |
| `connect_timeout` | int    | `60`    | Timeout for initial connection and discovery      |

Note: A server config must have either `command` (stdio) or `url` (HTTP), not both.

## How It Works

### Startup Discovery

When Hermes Agent starts, `discover_mcp_tools()` is called during tool initialization:

1. Reads `mcp_servers` from `~/.hermes/config.yaml`
2. For each server, spawns a connection in a dedicated background event loop
3. Initializes the MCP session and calls `list_tools()` to discover available tools
4. Registers each tool in the Hermes tool registry

### Tool Naming Convention

MCP tools are registered with the naming pattern:

```
mcp_{server_name}_{tool_name}
```

Hyphens and dots in names are replaced with underscores for LLM API compatibility.

Examples:
- Server `filesystem`, tool `read_file` → `mcp_filesystem_read_file`
- Server `github`, tool `list-issues` → `mcp_github_list_issues`
- Server `my-api`, tool `fetch.data` → `mcp_my_api_fetch_data`

### Auto-Injection

After discovery, MCP tools are automatically injected into all `hermes-*` platform toolsets (CLI, Discord, Telegram, etc.). This means MCP tools are available in every conversation without any additional configuration.

### Connection Lifecycle

- Each server runs as a long-lived asyncio Task in a background daemon thread
- Connections persist for the lifetime of the agent process
- If a connection drops, automatic reconnection with exponential backoff kicks in (up to 5 retries, max 60s backoff)
- On agent shutdown, all connections are gracefully closed

### Idempotency

`discover_mcp_tools()` is idempotent -- calling it multiple times only connects to servers that aren't already connected. Failed servers are retried on subsequent calls.

## Transport Types

### Stdio Transport

The most common transport. Hermes launches the MCP server as a subprocess and communicates over stdin/stdout.

```yaml
mcp_servers:
  filesystem:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/home/user/projects"]
```

The subprocess inherits a **filtered** environment (see Security section below) plus any variables you specify in `env`.

### HTTP / StreamableHTTP Transport

For remote or shared MCP servers. Requires the `mcp` package to include HTTP client support (`mcp.client.streamable_http`).

```yaml
mcp_servers:
  remote_api:
    url: "https://mcp.example.com/mcp"
    headers:
      Authorization: "Bearer sk-..."
```

If HTTP support is not available in your installed `mcp` version, the server will fail with an ImportError and other servers will continue normally.

### Remote MCP via SSH (Stdio Bridge)

When MCP servers live on a separate machine (LXC container, Raspberry Pi, VPS), use **SSH as the transport bridge**. Hermes spawns `ssh` as the local subprocess, and the remote command's stdin/stdout are piped through as stdio for the MCP protocol.

```yaml
mcp_servers:
  filesystem:
    command: "ssh"
    args:
      - "-o"
      - "StrictHostKeyChecking=no"
      - "root@192.0.2.10"
      - "/opt/mcp-start.sh"
      - "filesystem"
    timeout: 60
```

**Key practices:**

1. **SSH key auth is mandatory.** Set up passwordless SSH before configuring MCP:
   ```bash
   # On Hermes host, generate key if needed
   ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N "" -C "hermes-mcp"

   # Copy public key to remote (use sshpass as bootstrap if needed)
   sshpass -p 'PASSWORD' ssh root@REMOTE_IP \
     "echo '$(cat ~/.ssh/id_ed25519.pub)' >> ~/.ssh/authorized_keys"

   # Verify
   ssh -o BatchMode=yes root@REMOTE_IP hostname
   ```
   If `sshpass` times out in the terminal tool, use Python's `subprocess.run` instead — it often handles SSH negotiation more reliably.

2. **Use wrapper scripts, not inline commands.** The `env` field in MCP config sets variables on the **local** side (Hermes host), not on the remote machine. To set env vars or do pre-launch setup on the remote, create a wrapper script:
   ```bash
   # On remote machine: /opt/mcp-start-websearch.sh
   #!/bin/bash
   export DEFAULT_SEARCH_ENGINE=duckduckgo
   exec /usr/bin/open-websearch
   ```
   Then reference it from the MCP config:
   ```yaml
   command: "ssh"
   args: ["-o", "StrictHostKeyChecking=no", "root@REMOTE_IP", "/opt/mcp-start-websearch.sh"]
   ```

3. **Always verify remote tools are reachable** before adding to config:
   ```bash
   ssh root@REMOTE_IP "which open-websearch || npx open-websearch@latest 2>&1 | head -3"
   ```

### NPM-based MCP Servers (npx / @scope/package)

Many MCP servers ship as npm packages invoked via `npx`. These require Node.js 18+.

```yaml
mcp_servers:
  brightdata:
    args:
      - "@brightdata/mcp"
    command: npx
    timeout: 120
    env:
      API_TOKEN: "your_token_here"   # required, Bright Data API token
      ZONE: ""                        # optional, web unlocker zone
      HTTP_PROXY: "http://proxy:port"
      HTTPS_PROXY: "http://proxy:port"
```

**BrightData MCP specifics:**
- The old HTTPS endpoint (`https://mcp.brightdata.com/mcp?token=...`) is **deprecated** (returned `Invalid credentials` as of May 2026). Use the npx-based config above exclusively.
- BrightData also offers WebSocket browser endpoints (`wss://brd-customer-...@brd.superproxy.io:9222`) — these are **not MCP server URLs** but Playwright CDP connection targets. Use them with `playwright.chromium.connect_over_cdp(ws_url)` for stealth browser automation through BrightData's proxy network.
- Tokens can expire. If you get `Invalid credentials` from the MCP server startup, the user needs to generate a new token from the BrightData dashboard (bright.cn).
- BrightData MCP provides 5 tools: `search_engine` (Google/Bing/Yandex SERP), `scrape_as_markdown` (break CAPTCHA/bot detection), `search_engine_batch` (up to 5 queries), `scrape_batch` (up to 5 URLs), `discover` (AI semantic search with intent-based ranking, date filtering, geo-targeting).
- **TOOL-USE PRIORITY** (critical lesson from user correction): When the task requires searching for information that basic tools can't find (Chinese API pricing pages, GFW-blocked content, cloud provider rate cards, deep documentation), **try BrightData MCP first** before falling back to openwebsearch or basic web_search. BrightData breaks through bot detection (CAPTCHA/reCAPTCHA) that blocks normal tools. If BrightData MCP itself fails (token expired), use CloakBrowser MCP (if configured) to render the page via BrightData WS proxy. The user explicitly expects these premium tools to be tried first for hard-to-reach content.

**Pitfall: `@` symbol in YAML** — When using npm scoped packages like `@brightdata/mcp`, the value starting with `@` must be quoted in YAML:
```yaml
    args:
      - "@brightdata/mcp"     # ✅ correct
      - @brightdata/mcp       # ❌ YAML parse error
```

## Security

### Environment Variable Filtering

For stdio servers, Hermes does NOT pass your full shell environment to MCP subprocesses. Only safe baseline variables are inherited:

- `PATH`, `HOME`, `USER`, `LANG`, `LC_ALL`, `TERM`, `SHELL`, `TMPDIR`
- Any `XDG_*` variables

All other environment variables (API keys, tokens, secrets) are excluded unless you explicitly add them via the `env` config key. This prevents accidental credential leakage to untrusted MCP servers.

```yaml
mcp_servers:
  github:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      # Only this token is passed to the subprocess
      GITHUB_PERSONAL_ACCESS_TOKEN: "ghp_..."
```

### Credential Stripping in Error Messages

If an MCP tool call fails, any credential-like patterns in the error message are automatically redacted before being shown to the LLM. This covers:

- GitHub PATs (`ghp_...`)
- OpenAI-style keys (`sk-...`)
- Bearer tokens
- Generic `token=`, `key=`, `API_KEY=`, `password=`, `secret=` patterns

## Troubleshooting

### "MCP SDK not available -- skipping MCP tool discovery"

The `mcp` Python package is not installed. Install it:

```bash
pip install mcp
```

### "No MCP servers configured"

No `mcp_servers` key in `~/.hermes/config.yaml`, or it's empty. Add at least one server.

### "Failed to connect to MCP server 'X'"

Common causes:
- **Command not found**: The `command` binary isn't on PATH. Ensure `npx`, `uvx`, or the relevant command is installed.
- **Package not found**: For npx servers, the npm package may not exist or may need `-y` in args to auto-install.
- **Node.js version too low**: Some npx-based MCP servers require Node.js 22+. Check with `node --version`.
- **Timeout**: The server took too long to start. Increase `connect_timeout`.
- **Port conflict**: For HTTP servers, the URL may be unreachable.
- **Custom MCP server protocol mismatch**: If you wrote a custom MCP server and get `CancelledError`, the server likely doesn't speak the correct MCP protocol. The MCP wire format over stdio uses JSON-RPC 2.0 with specific method names — see `references/building-custom-mcp-servers.md` for the exact protocol.
- **Gateway venv vs system python mismatch**: Hermes gateway runs MCP subprocesses using `~/.hermes/hermes-agent/venv/bin/python3` (gateway's own venv). If your custom MCP script depends on packages only installed in the system Python (e.g., `cloakbrowser`, `playwright`), it will crash with `ModuleNotFoundError` at startup with no visible error in gateway logs (only `unhandled errors in a TaskGroup`). The process dies before any MCP handshake. Fixes:
  1. **Install in gateway venv**: `~/.hermes/hermes-agent/venv/bin/pip install <package>` — the cleanest fix.
  2. **Use absolute system python path**: Set `command: /usr/bin/python3` in the MCP config — works if system python has the required packages.
  3. **PYTHONPATH env**: Add the system site-packages via `env: { PYTHONPATH: "/usr/local/lib/python3.11/dist-packages" }` — fragile across Python versions.
- **Python MCP server uses sync API in asyncio**: If you wrote a custom MCP server using `playwright.sync_api` (sync) but it runs inside Hermes gateway's asyncio event loop, you'll get `"It looks like you are using Playwright Sync API inside the asyncio loop. Please use the Async API instead."`. Fix: rewrite the server to use `playwright.async_api` with `async/await`. See `references/building-custom-mcp-servers.md` for async MCP server patterns.

### "MCP server 'X' requires HTTP transport but mcp.client.streamable_http is not available"

Your `mcp` package version doesn't include HTTP client support. Upgrade:

```bash
pip install --upgrade mcp
```

### Tools not appearing

- Check that the server is listed under `mcp_servers` (not `mcp` or `servers`)
- Ensure the YAML indentation is correct
- Look at Hermes Agent startup logs for connection messages
- Tool names are prefixed with `mcp_{server}_{tool}` -- look for that pattern

### Connection keeps dropping

The client retries up to 5 times with exponential backoff (1s, 2s, 4s, 8s, 16s, capped at 60s). If the server is fundamentally unreachable, it gives up after 5 attempts. Check the server process and network connectivity.

### CRITICAL: Never heredoc-overwrite JSON configs with secrets

**This is a top-priority pitfall — it has caused real data loss.** When editing any JSON config file that contains API keys, tokens, or passwords (mimocode, Claude Code, Hermes, etc.), **NEVER** use a shell heredoc or `cat > file << EOF` to overwrite the entire file. The heredoc will replace sensitive values with literal text, destroying the real credentials.

**Wrong (destroys API keys):**
```bash
cat > ~/.config/mimocode/config.json << 'EOF'
{
  "provider": { "options": { "apiKey": "PLACEHOLDER" } }
}
EOF
```

**Right (preserves existing values):**
```bash
# Use Python to read, merge, and write back
python3 -c "
import json
with open('$CONFIG') as f: cfg = json.load(f)
cfg['mcpServers'] = { ... }  # add/merge new section
with open('$CONFIG', 'w') as f: json.dump(cfg, f, indent=2)
"
```

Or with `jq`:
```bash
jq '.mcpServers = { "name": { "command": "uvx", "args": [...] } }' \
  "$CONFIG" > "$CONFIG.tmp" && mv "$CONFIG.tmp" "$CONFIG"
```

**Why this happens:** Terminal output masks secrets with `***`, so you can't read the real value back. Once overwritten, the original key is gone with no backup. Always merge, never overwrite.

### MCP tools return empty results or "private/internal address" errors

This is often DNS-related, especially in China where GFW poisons DNS for foreign domains. MCP servers on the remote machine resolve domains to fake IPs (e.g., `198.18.x.x`). See `references/china-networking.md` for diagnosis and workarounds. Quick check: switch search engines to China-accessible ones (Bing, Baidu) via the `env` config field.

### GLIBC version mismatch (prebuilt Linux binaries)

Prebuilt Linux binaries (e.g., from GitHub Releases tagged `x86_64-unknown-linux-gnu`) may be compiled against a newer GLIBC than Debian 12's GLIBC 2.36. The binary fails with:

```
./binary: /lib/x86_64-linux-gnu/libc.so.6: version `GLIBC_2.38' not found
```

**Check before downloading:**
```bash
ldd --version | head -1    # Debian 12 = 2.36
```

**Workarounds (order of preference):**
1. **Build from source** — `cargo install --git <repo> <crate>` links against system GLIBC (needs Rust toolchain, ~10 min on 2GB/2-core)
2. **Docker** — `docker run ghcr.io/owner/image` if Docker is on the remote host
3. **musl static build** — check releases for `-musl` or `-static` variants
4. **Older release** — earlier versions may have been built with older toolchains

### Slow GitHub Release downloads

When downloading 30MB+ binaries from GitHub Releases takes >60s:
1. Download on a machine with better connectivity, then `scp` to target
2. Use `gh release download` if `gh` CLI is available (often faster via authenticated API)
3. Use `wget` instead of `curl` — handles slow/flaky connections better with `--timeout`

### Go Binary MCP Servers (e.g., Engram)

Some MCP servers ship as single Go binaries rather than npm/Python packages. They have distinct characteristics:

- **No runtime dependencies** — no Node.js or Python needed
- **Install via curl/wget** — download binary from GitHub Releases
- **Configure via flags**, not env vars — e.g., `--tools=agent` for engram
- **Timeout tuning critical** — Go binary startup + SQLite operations may need longer than npm servers. Start with `timeout: 120`, not the default 60.

Example engram config:
```yaml
mcp_servers:
  engram:
    command: engram
    args: ["mcp", "--tools=agent"]
    timeout: 120
```

See `references/engram-mcp.md` for full integration details, tool list, and known issues (CJK search limitation, session lifecycle requirements).

### Evaluating MCP Servers

Refer to `references/evaluating-mcp-servers.md` for a decision framework, case studies, and popular category picks. Use it when the user asks "should I install this MCP?" or when choosing between competing MCP servers.

For Chinese A-share stock/fund market MCP servers specifically, see `references/cn-stock-market-mcp-servers.md` — covers akshare-one (data), eastmoney-mx (simulated trading), cn-funds (portfolio management), and comparison with international alternatives.

For CloakBrowser + BrightData integration (stealth browser via Unlocker HTTP proxy), see `references/cloakbrowser-brightdata-integration.md` — covers both WS and HTTP proxy patterns, python venv mismatch for gateway MCP subprocesses, sync/async Playwright API pitfalls, LXC connectivity issues, and all proxy failure modes encountered in this user's setup.

## Examples

### Time Server (uvx)

```yaml
mcp_servers:
  time:
    command: "uvx"
    args: ["mcp-server-time"]
```

Registers tools like `mcp_time_get_current_time`.

### Filesystem Server (npx)

```yaml
mcp_servers:
  filesystem:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/home/user/documents"]
    timeout: 30
```

Registers tools like `mcp_filesystem_read_file`, `mcp_filesystem_write_file`, `mcp_filesystem_list_directory`.

### GitHub Server with Authentication

```yaml
mcp_servers:
  github:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_PERSONAL_ACCESS_TOKEN: "ghp_xxxxxxxxxxxxxxxxxxxx"
    timeout: 60
```

Registers tools like `mcp_github_list_issues`, `mcp_github_create_pull_request`, etc.

### Remote HTTP Server

```yaml
mcp_servers:
  company_api:
    url: "https://mcp.mycompany.com/v1/mcp"
    headers:
      Authorization: "Bearer <API_KEY>"
      X-Team-Id: "engineering"
    timeout: 180
    connect_timeout: 30
```

### Multiple Servers

```yaml
mcp_servers:
  time:
    command: "uvx"
    args: ["mcp-server-time"]

  filesystem:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]

  github:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_PERSONAL_ACCESS_TOKEN: "ghp_xxxxxxxxxxxxxxxxxxxx"

  company_api:
    url: "https://mcp.internal.company.com/mcp"
    headers:
      Authorization: "Bearer <API_KEY>"
    timeout: 300
```

All tools from all servers are registered and available simultaneously. Each server's tools are prefixed with its name to avoid collisions.

## Sampling (Server-Initiated LLM Requests)

Hermes supports MCP's `sampling/createMessage` capability — MCP servers can request LLM completions through the agent during tool execution. This enables agent-in-the-loop workflows (data analysis, content generation, decision-making).

Sampling is **enabled by default**. Configure per server:

```yaml
mcp_servers:
  my_server:
    command: "npx"
    args: ["-y", "my-mcp-server"]
    sampling:
      enabled: true           # default: true
      model: "gemini-3-flash" # model override (optional)
      max_tokens_cap: 4096    # max tokens per request
      timeout: 30             # LLM call timeout (seconds)
      max_rpm: 10             # max requests per minute
      allowed_models: []      # model whitelist (empty = all)
      max_tool_rounds: 5      # tool loop limit (0 = disable)
      log_level: "info"       # audit verbosity
```

Servers can also include `tools` in sampling requests for multi-turn tool-augmented workflows. The `max_tool_rounds` config prevents infinite tool loops. Per-server audit metrics (requests, errors, tokens, tool use count) are tracked via `get_mcp_status()`.

Disable sampling for untrusted servers with `sampling: { enabled: false }`.

## Notes

- MCP tools are called synchronously from the agent's perspective but run asynchronously on a dedicated background event loop
- Tool results are returned as JSON with either `{"result": "..."}` or `{"error": "..."}`
- The native MCP client is independent of `mcporter` -- you can use both simultaneously
- Server connections are persistent and shared across all conversations in the same agent process
- After adding a new MCP server to config.yaml, use the **`/reload-mcp`** slash command in an active session to pick it up without restarting the agent. This works for both new additions and config changes to existing servers.
