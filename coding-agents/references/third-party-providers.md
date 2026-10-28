# Third-Party Provider Configuration for Claude Code Family

## cc-haha (Claude Code Haha)

Third-party Claude Code fork with GUI for provider management. Supports domestic Chinese model providers natively.

- **GitHub:** https://github.com/NanmiCoder/cc-haha
- **Install (macOS):** Download DMG from GitHub Releases → mount → drag to /Applications
- **Quarantine fix:** If macOS says "file corrupted", run:
  ```bash
  xattr -d com.apple.quarantine ~/Downloads/Claude-Code-Haha_*.dmg
  # Then re-open the DMG and drag to /Applications
  ```
  Or on the already-installed app:
  ```bash
  xattr -d com.apple.quarantine "/Applications/Claude Code Haha.app"
  ```
- **Uninstall:** Eject DMGs (`hdiutil detach /Volumes/Claude\ Code\ Haha*`), delete app from /Applications, clean `~/Library/Caches/claude-cli-nodejs`, remove `~/Applications/Claude Code URL Handler.app` if present.
- **Config location:** `~/.claude/settings.json` (same as official Claude Code)

### MiMo (Xiaomi) API Configuration

MiMo provides both OpenAI-compatible and Anthropic-compatible endpoints.

**Endpoints:**
| Protocol | Base URL |
|----------|----------|
| OpenAI | `https://api.xiaomimimo.com/v1` |
| Anthropic | `https://api.xiaomimimo.com/anthropic` |
| Token Plan (OpenAI) | `https://token-plan-cn.xiaomimimo.com/v1` |

**Model names (ALL lowercase, verified from official docs):**
| Model | Name |
|-------|------|
| Pro | `mimo-v2.5-pro` |
| Standard | `mimo-v2.5` |
| V2 Pro | `mimo-v2-pro` |
| Flash | `mimo-v2-flash` |
| Omni | `mimo-v2-omni` |

**Two ways to connect:**

**Option A (recommended): Anthropic direct — no proxy needed**

MiMo natively supports Anthropic protocol. Skip the proxy conversion entirely:
```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "https://api.xiaomimimo.com/anthropic",
    "ANTHROPIC_MODEL": "mimo-v2.5-pro",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "mimo-v2.5",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "mimo-v2.5-pro",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "mimo-v2.5-pro",
    "ANTHROPIC_API_KEY": "你的API Key"
  }
}
```
This is the cleanest config — no local proxy, no protocol conversion, direct Anthropic format.

**Option B: OpenAI proxy conversion mode**

cc-haha's proxy at `http://127.0.0.1:3456/proxy` converts Anthropic → OpenAI format:
```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:3456/proxy",
    "ANTHROPIC_MODEL": "mimo-v2.5-pro",
    "ANTHROPIC_API_KEY": "proxy-managed"
  }
}
```
⚠️ This adds a conversion layer that can cause "Invalid request" errors. Use Option A unless you have a reason.

**⚠️ Pitfalls (verified 2026-06-03):**

1. **Endpoint URL must NOT include `/chat/completions`** when using proxy mode. The proxy appends the path automatically. Use `https://api.xiaomimimo.com/v1`, NOT `https://api.xiaomimimo.com/v1/chat/completions`.

2. **MiMo supports Anthropic protocol natively** — this means cc-haha can connect directly without the proxy conversion layer. The Anthropic endpoint (`/anthropic`) accepts standard Anthropic message format, which is what Claude Code sends natively.

3. **cc-haha GUI configuration (if using proxy mode):**
   | Field | Value |
   |-------|-------|
   | 接口地址 | `https://api.xiaomimimo.com/v1` |
   | API 格式 | `OpenAI Chat Completions (代理转换)` |
   | 主模型 | `mimo-v2.5-pro` |
   | Haiku/Sonnet/Opus | 同主模型 |

### Stuck Process Diagnosis

When cc-haha or Claude Code appears stuck (spinning, no progress, counter frozen):

**Process names differ by variant (important for SSH remote diagnosis):**
| Variant | Server process | CLI process | Notes |
|---------|---------------|-------------|-------|
| cc-haha | `claude-sidecar server` | `claude-sidecar cli` | Desktop app spawns both |
| Official Claude Code | `claude` (single process) | `claude.ex` on macOS | TUI runs in terminal |

**Diagnosis steps (works for both variants):**

1. **Check if API is being called:**
   ```bash
   lsof -i -nP | grep xiaomimimo  # or grep the provider's domain
   ```
   - If connections exist → provider is responding slowly, wait or Ctrl+C
   - If NO connections → process is idle/stuck, safe to Ctrl+C

2. **Check process state:**
   ```bash
   ps -p <PID> -o pid,state,etime,rss,pcpu
   ```
   - `S` (sleeping) + low CPU + no API connection = stuck, Ctrl+C
   - `S` + active API connection = model still generating, be patient

3. **Token safety:** If the UI shows output tokens (e.g., "↓ 1360") but is frozen with no API connection, the tokens were already generated. Ctrl+C won't waste additional tokens.

4. **Remote diagnosis via SSH (Mac example):**
   ```bash
   sshpass -p 'pass' ssh cuiyiming@100.64.0.1 "
     ps aux | grep -iE 'claude|haha' | grep -v grep
     lsof -i -nP 2>/dev/null | grep xiaomimimo || echo 'no API connection'
   "
   ```

### Model Tier Mapping (Haiku/Sonnet/Opus)

Claude Code internally routes different task types to different model tiers:
- **Opus:** Complex reasoning, architecture decisions
- **Sonnet:** Main coding tasks (default for most work)
- **Haiku:** Lightweight tasks (summarization, quick Q&A, context compression)

When using a single non-Claude model, set all three to the same model. Splitting tiers (e.g., standard model for Haiku, Pro for Sonnet/Opus) saves marginal tokens but adds complexity and risks weaker responses on "simple" tasks that turn out not to be simple.

## Framework Comparison (Claude Code vs OpenCode vs Codex)

For domestic Chinese model users, the key differentiator is model lock-in:

| | Claude Code | Codex | OpenCode |
|---|---|---|---|
| Model lock-in | Anthropic (configurable but optimized for Claude) | OpenAI (configurable but optimized for GPT) | None (provider-agnostic by design) |
| Domestic model support | Via proxy/config hacks | Via proxy/config hacks | Native (OpenRouter, custom base_url) |
| Framework maturity | Most mature (hooks, subagents, MCP, CLAUDE.md) | Mid-tier (sandbox, git-native) | Youngest but functional |
| Best for domestic models | Workable but Claude-optimized tool calling may underperform | Weakest fit | Best fit (framework designed for model flexibility) |

**Rule of thumb:** If using Claude-family models → Claude Code framework. If using domestic models → OpenCode is more reliable because the framework is designed to迁就 the model rather than demand Claude-level capability.

**cc-haha middle ground:** If you want Claude Code's mature framework but with multi-provider support, cc-haha provides the GUI for provider management. Just be aware that Claude Code's tool calling format is optimized for Claude models, so non-Claude models may underperform on complex agentic tasks.
