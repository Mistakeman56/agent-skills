# MCP Server Audit & Cleanup Checklist

## Trigger

Periodically (every few weeks, or when user says "查查MCP/看看都有什么MCP") or when user asks why the agent forgot about a deployment. A stale MCP list causes:
- Wasted tokens (every server's tool descriptions inflate the system prompt)
- Confusion (agent sees tools it forgot exist and doesn't think to use them)
- Memory drift (agent confidently states a server exists that was removed, or vice versa)

## Audit Procedure

### Step 1: List all configured MCP servers

```bash
# Read from config.yaml
grep -A3 "^  [a-z]" ~/.hermes/config.yaml | grep -E "^  [a-z]|command:|url:" | head -60

# Or read the full mcp_servers section
# Line number depends on config — search for it:
grep -n "mcp_servers:" ~/.hermes/config.yaml
```

### Step 2: Build the usage table

For each server, categorize based on what you actually remember using:

| Category | Label | Criteria |
|----------|-------|----------|
| ✅ Active | Used regularly | Called at least once in the last 2 weeks |
| ⚠️ Occasional | Used rarely but has value | Called once in the last month |
| ❓ Unknown | Don't know if it works | Not used recently, but may be relevant |
| 🗑️ Stale | Should be removed | Never used, or superseded by another tool |

### Step 3: Verify "Unknown" servers

For SSH-based MCP servers, check if they're actually running on the remote host:

```bash
ssh -o StrictHostKeyChecking=no root@REMOTE_IP "ps aux | grep -i mcp | grep -v grep"
```

For local servers, check the process tree:

```bash
ps aux | grep -i "mcp\|npx.*mcp" | grep -v grep
```

### Step 4: Ask the user for confirmation

Present the categorized table to the user with a clear question:
- "这些从没用的MCP删了行吗？"
- "这个xxx是不是有但你没用过？"

### Step 5: Remove/comment out stale servers

```yaml
# In ~/.hermes/config.yaml, delete the server's entry:
# mcp_servers:
#   stale-server:          ← delete this entire block
#     command: npx
#     args: ["stale-pkg"]
```

Then reload MCP: `/reload-mcp` in session.

### Step 6: Update memory

After confirming with the user, save the current MCP state to memory so next session is accurate.

## Common Stale Server Patterns

| Server | Why it's often stale | Replacement |
|--------|---------------------|-------------|
| `openwebsearch` | BrightData MCP does everything it does, better | `brightdata` |
| `fetch` | BrightData `scrape_as_markdown` = fetch+break CAPTCHA | `brightdata` |
| `sequentialthinking` | Rarely needed for this user's workflow | None (delete) |
| `git` | Only useful during active development sessions | None (ad-hoc) |
| `github` | Unreliable — frequent connection failures | `gh` CLI or BrightData scrape |
| `excel` | User rarely works with spreadsheets | None (ad-hoc) |
| `homeassistant` | Needs HA API token configured; mcp_servers config exists but unused | Either configure or remove |
| `xiaomi-home` | Needs Mi Home account QR login | Either set up properly or remove |
| `cloakbrowser` | Recently added, verify if it's been used | Either use or remove |

## Token Savings Estimate

| Action | Tokens saved per turn | Monthly savings (DeepSeek) |
|--------|----------------------|---------------------------|
| Remove 1 server with ~5 tools | ~300 tokens | ~¥2-3 |
| Remove 8 stale servers | ~4K tokens | ~¥16-24 |
| Remove ALL stale + compress remaining | ~5K tokens | ~¥20-30 |

## Cost-Benefit: Keep vs Remove

Before removing, ask: **"Will I need this in the next month?"**

- **Keep if:** the user might ask about it within 30 days, or it serves a unique function no other server covers
- **Remove if:** never used, superseded, or only relevant for one-off tasks that can be done via terminal
- **Special case — `engram`:** This is a persistent memory system. Even if never directly called, it could be useful as an alternative to Hermes built-in memory. Ask the user before removing.
