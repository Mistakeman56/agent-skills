---
name: codex
description: "Delegate coding to OpenAI Codex CLI (features, PRs)."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Coding-Agent, Codex, OpenAI, Code-Review, Refactoring]
    related_skills: [claude-code, hermes-agent]
---

# Codex CLI

Delegate coding tasks to [Codex](https://github.com/openai/codex) via the Hermes terminal. Codex is OpenAI's autonomous coding agent CLI.

## When to use

- Building features
- Refactoring
- PR reviews
- Batch issue fixing

Requires the codex CLI and a git repository.

## Prerequisites

### Installation

```bash
# Standard
npm install -g @openai/codex

# China / GFW-restricted networks — use npm mirror:
npm install -g @openai/codex --registry https://registry.npmmirror.com
```

### Authentication

Codex supports two auth paths:

1. **ChatGPT OAuth** (recommended — uses ChatGPT Plus/Pro subscription, no extra API cost)
2. **API Key** (`echo "$OPENAI_API_KEY" | codex login --with-api-key` — separate API billing)

Verify auth status:
```bash
codex login status
# Should show: "Logged in using ChatGPT"
```

For Hermes itself, `model.provider: openai-codex` uses Hermes-managed Codex
OAuth from `~/.hermes/auth.json` after `hermes auth add openai-codex`. For the
standalone Codex CLI, a valid CLI OAuth session lives under
`~/.codex/auth.json`; do not treat a missing `OPENAI_API_KEY` alone as proof
that Codex auth is missing.

### Edge Requirements

- **Must run inside a git repository** — Codex refuses to run outside one
- Use `pty=true` in terminal calls — Codex is an interactive terminal app

## Authentication & Phone Verification — Critical Pitfalls

### Problem

As of April/May 2026, Codex CLI frequently triggers **phone number verification**
on first login, especially when:
- Switching devices or reinstalling
- Logging in from a new IP/location
- Using a VPN/proxy (OpenAI flags the login as suspicious)
- Account has no prior Codex session

Users from China face a double-bind:
- **With US proxy ON** → Codex asks for a **US phone number** (Chinese +86 not accepted)
- **Without proxy (China direct)** → Login page is blocked by GFW

### Solutions (ordered by reliability)

**Solution 1: Copy `auth.json` from an already-authenticated device** ✅ Best
```bash
# On the OLD device where Codex already works:
cp ~/.codex/auth.json /path/to/safe/transfer/

# On the NEW device:
mkdir -p ~/.codex
cp /path/to/safe/transfer/auth.json ~/.codex/auth.json
codex login status  # Should show authenticated
```
- **Works even on headless servers** — no browser needed
- auth.json contains OAuth tokens, **treat like a password**
- Only copy between YOUR own trusted devices

**Solution 2: Device auth login** ⚠️ May still trigger phone verification
```bash
codex login --device-auth
# Shows a URL + one-time code
# Open URL in browser (with proxy ON), login, enter code
```
- Bypasses localhost callback failures on headless servers
- But does **NOT** bypass phone verification if the account requires it
- ⚠️ User experience from 2026-05-16: device auth still asked for US phone number when used with US proxy

**Solution 3: API Key login** ✅ Bypasses ChatGPT auth entirely
```bash
# Create an API key at https://platform.openai.com/api-keys first
export OPENAI_API_KEY="sk-..."
echo "$OPENAI_API_KEY" | codex login --with-api-key
```
- **No phone verification needed** (creating the key might, but using it won't)
- ⚠️ Uses **API billing** — NOT included in ChatGPT Plus subscription
- Best for headless servers / CI/CD

**Solution 4: Upgrade to ChatGPT Plus first, THEN login**
- Free accounts trigger stricter verification
- Many users report **phone verification disappears after subscribing to Plus**
- The Plus subscription proves the account is legitimate, reducing risk triggers

### Solution 5: Temporary US phone number (SMS activation)
- Use services like sms-activate.org (supports Chinese payment, ~¥2-3 per number)
- Buy a temporary US number, use it for verification
- Works for Chinese users who can't receive +86 SMS from OpenAI

**⚠️ Service status (verified 2026-05-16):**
- `sms-activate.org` — **SHUT DOWN** (as of Dec 2024). Dead link.
- `voidmob.com` — Legit service but registration returns 505 error. In waitlist mode.
- `5sim.net` — Working but payment is restricted (needs Nigeria card).
- `smspool.net` — **Working.** Supports PayPal/crypto for OpenAI verification. Non-VoIP numbers.
- `sms-man.com` — Working. Cheap (~$0.10/SMS). Crypto/PayPal.
- `buynumber.io` — Working. From $0.25. Crypto (BTC/ETH).
- `tiger-sms.com` — Working. Multiple payment methods.

### Solution 6: 闲鱼 (Xianyu) one-time verification ✅ Cheapest for Chinese users

**For Chinese users only.** Search 闲鱼 for "OpenAI验证码", "Codex登录" or "ChatGPT手机验证":
- Sellers use their own real US phone to receive the verification SMS for you
- Cost: **¥4-10 per time** (verified working 2026-05-16)
- No minimum balance or bulk credit needed
- Transaction is one-off, no recurring commitment
- ⚠️ You give the seller your ChatGPT password briefly — change it after verification

**Alternative: Buy a pre-authenticated account.** Search 闲鱼 for "Codex已登录" or "ChatGPT Plus成品号", then extract `~/.codex/auth.json` from it (see Solution 1).

### Alternative: Codex VS Code Extension (Bypasses CLI auth entirely)

If Codex CLI auth is blocked, use the **Codex VS Code extension** instead. It uses a different auth path (browser OAuth) and may not trigger phone verification:

1. In VS Code: Extensions → Search "Codex" → Install (by OpenAI)
2. Click the Codex icon in the sidebar
3. Sign in with ChatGPT account via browser OAuth
4. Use Codex directly inside VS Code—read, edit, debug files

**CLI vs IDE vs ChatGPT App experience (from user feedback 2026-05-16):**

| Feature | Codex CLI / App | VS Code Extension | ChatGPT Mac App + Work with Apps |
|:--------|:---------------:|:-----------------:|:--------------------------------:|
| Read project files | ✅ Full project | ✅ Current file | ⚠️ Current file only |
| Edit any file | ✅ | ✅ Current file | ⚠️ Current file only |
| Run code / tests | ✅ | ❌ | ❌ |
| New project from scratch | ✅ | ❌ | ❌ |
| Background long tasks | ✅ | ❌ (5min timeout) | ❌ |
| Multi-file refactors | ✅ | ⚠️ Limited | ❌ |
| PR review / creation | ✅ | ❌ | ❌ |
| Phone verification | ❌ **Blocked** | ⚠️ May need it | ✅ **Mac App is clean** |

**Practical verdict:** VS Code extension ≈ 70% of CLI capability for day-to-day editing. ChatGPT Mac App + VS Code ≈ 50%. Full CLI needed for autonomous multi-file work. Use VS Code extension as a fallback when CLI auth is stuck.

### auth.json Paths

| System | Path |
|--------|------|
| macOS | `~/.codex/auth.json` |
| Linux | `~/.codex/auth.json` |
| Windows | `C:\\Users\\<Username>\\.codex\\auth.json` |
| Custom | `$CODEX_HOME/auth.json` |

## Headless Server Auth — Hermes Integration Pitfall

When authenticating Codex from within Hermes (PVE/LXC/SSH server with no browser), the default terminal timeout kills the auth process before it can save the token.

**❌ Wrong (default 30s timeout kills auth):**
```bash
terminal(command="codex login --device-auth", timeout=30)
# Process killed before token saved — even if user completed browser auth!
```

**✅ Correct — background process + file redirect:**
```bash
# Step 1: Start in background with long timeout, redirect output to file
terminal(command="codex login --device-auth > /tmp/codex_auth_output.txt 2>&1",
         background=true, timeout=300)

# Step 2: Read URL + code from file and send to user
terminal(command="cat /tmp/codex_auth_output.txt", timeout=5)
# User opens https://auth.openai.com/codex/device in browser
# User enters the one-time code (e.g., 4TN1-8L7VU, expires 15min)

# Step 3: Poll until process exits
process(action="poll", session_id="<proc_id>")

# Step 4: Verify
terminal(command="codex login status", timeout=5)
# "Logged in using ChatGPT" = success

# Step 5: Confirm auth.json
terminal(command="ls -la ~/.codex/auth.json", timeout=5)
```

**Key insight:** The 30s default terminal timeout is the root cause. The device auth process prints the URL+code then **blocks waiting for the user**. When it times out, the process is killed before it receives the OAuth callback. Using `background=true` with a long timeout solves this.

## One-Shot Tasks

```
terminal(command="codex exec 'Add dark mode toggle to settings'", workdir="~/project", pty=true)
```

For scratch work (Codex needs a git repo):
```
terminal(command="cd $(mktemp -d) && git init && codex exec 'Build a snake game in Python'", pty=true)
```

## Background Mode (Long Tasks)

```
# Start in background with PTY
terminal(command="codex exec --full-auto 'Refactor the auth module'", workdir="~/project", background=true, pty=true)
# Returns session_id

# Monitor progress
process(action="poll", session_id="<id>")
process(action="log", session_id="<id>")

# Send input if Codex asks a question
process(action="submit", session_id="<id>", data="yes")

# Kill if needed
process(action="kill", session_id="<id>")
```

## Key Flags

| Flag | Effect |
|------|--------|
| `exec "prompt"` | One-shot execution, exits when done |
| `--full-auto` | Sandboxed but auto-approves file changes in workspace |
| `--yolo` | No sandbox, no approvals (fastest, most dangerous) |

## PR Reviews

Clone to a temp directory for safe review:

```
terminal(command="REVIEW=$(mktemp -d) && git clone https://github.com/user/repo.git $REVIEW && cd $REVIEW && gh pr checkout 42 && codex review --base origin/main", pty=true)
```

## Parallel Issue Fixing with Worktrees

```
# Create worktrees
terminal(command="git worktree add -b fix/issue-78 /tmp/issue-78 main", workdir="~/project")
terminal(command="git worktree add -b fix/issue-99 /tmp/issue-99 main", workdir="~/project")

# Launch Codex in each
terminal(command="codex --yolo exec 'Fix issue #78: <description>. Commit when done.'", workdir="/tmp/issue-78", background=true, pty=true)
terminal(command="codex --yolo exec 'Fix issue #99: <description>. Commit when done.'", workdir="/tmp/issue-99", background=true, pty=true)

# Monitor
process(action="list")

# After completion, push and create PRs
terminal(command="cd /tmp/issue-78 && git push -u origin fix/issue-78")
terminal(command="gh pr create --repo user/repo --head fix/issue-78 --title 'fix: ...' --body '...'")

# Cleanup
terminal(command="git worktree remove /tmp/issue-78", workdir="~/project")
```

## Batch PR Reviews

```
# Fetch all PR refs
terminal(command="git fetch origin '+refs/pull/*/head:refs/remotes/origin/pr/*'", workdir="~/project")

# Review multiple PRs in parallel
terminal(command="codex exec 'Review PR #86. git diff origin/main...origin/pr/86'", workdir="~/project", background=true, pty=true)
terminal(command="codex exec 'Review PR #87. git diff origin/main...origin/pr/87'", workdir="~/project", background=true, pty=true)

# Post results
terminal(command="gh pr comment 86 --body '<review>'", workdir="~/project")
```

## Reference Files

| File | Content |
|------|---------|
| `references/chatgpt-plus-subscription-guide.md` | US/Turkish Apple gift card flows for ChatGPT Plus subscription, comparison of regional pricing |

## Hermes + Codex 双 AI 架构（用户确立的分工模式）

来自 2026-05-16 的用户设计：

```
assistant（决策）
  ├→ Hermes（DeepSeek V4 Flash / 或其他性价比模型）— 日常助手
  │   • 微信聊天、行情查询、PPT 制作、班级事务、考研规划
  │   • 省 token、够用就行、性价比优先（日费 ~¥3-7）
  │   • 遇到技术难题时调 Codex 想方案
  │
  └→ Codex CLI（GPT-5.5）— 技术攻坚
      • 编程难题、架构设计、复杂算法
      • "智商更高但框架偏编程，不适合日常"
      • 由 Hermes 调度（通过 terminal 工具），结果翻译后转给用户
```

**关键原则：** Codex 是技术专家，Hermes 是日常管家。不要把 Codex 当日常聊天用，那是大材小用。遇到真·技术难题，让 Hermes 说"稍等，我喊 Codex 想想"，出方案后翻译成用户能懂的语言。

Hermes 调度 Codex 的示例：
```bash
# Hermes 内部用 terminal 工具调用 Codex
terminal(command="codex --yolo exec '写一个 Python 函数解析股票 CSV，按日期分组计算日均价'", workdir="/tmp/scratch", pty=true, background=true)
# 等 Codex 跑完，把结果转成中文解释给用户
```

## Rules

1. **Always use `pty=true`** — Codex is an interactive terminal app and hangs without a PTY
2. **Git repo required** — Codex won't run outside a git directory. Use `mktemp -d && git init` for scratch
3. **Use `exec` for one-shots** — `codex exec "prompt"` runs and exits cleanly
4. **`--full-auto` for building** — auto-approves changes within the sandbox
5. **Background for long tasks** — use `background=true` and monitor with `process` tool
6. **Don't interfere** — monitor with `poll`/`log`, be patient with long-running tasks
7. **Parallel is fine** — run multiple Codex processes at once for batch work
