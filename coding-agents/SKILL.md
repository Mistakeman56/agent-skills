---
name: coding-agents
description: "Delegate coding tasks to autonomous CLI agents (Claude Code, Codex, OpenCode). Covers orchestration via Hermes terminal, PTY handling, tmux sessions, PR reviews, parallel worktrees, and cost management."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Coding-Agent, Claude, Codex, OpenCode, Delegation, PTY, Automation, PR-Review]
    related_skills: [github, requesting-code-review, systematic-debugging]
---

# Coding Agents — Autonomous CLI Delegation

Delegate coding tasks to external autonomous CLI agents, orchestrated from Hermes via the terminal and process tools. Three supported agents, each optimized for different model ecosystems.

## Decision Framework

| Factor | Claude Code | Codex | OpenCode |
|--------|-------------|-------|----------|
| **Model lock-in** | Claude models only | GPT models only | None — any provider |
| **Domestic Chinese models** | ❌ Not designed for | ❌ Not designed for | ✅ Native support |
| **Framework maturity** | ⭐⭐⭐⭐⭐ Most complete | ⭐⭐⭐ Sandboxed | ⭐⭐⭐ Lightweight |
| **Cost** | $20/mo or API billing | ChatGPT Plus $20/mo or API | Free |
| **Open source** | ❌ | ❌ | ✅ |
| **Best for** | Claude models (Sonnet/Opus) | GPT models (GPT-4o/o3) | Non-proprietary models (DeepSeek, Qwen, GLM) |

**Rule of thumb:** If the user wants domestic/non-proprietary models → OpenCode. If Claude → Claude Code. If GPT → Codex.

## Common Orchestration Patterns

All three agents share these Hermes integration patterns:

### Print Mode (One-Shot, Preferred for Most Tasks)
```bash
# Claude Code
terminal(command="claude -p 'task description' --allowedTools 'Read,Edit' --max-turns 10", workdir="/project", timeout=120)

# Codex
terminal(command="codex exec 'task description'", workdir="/project", pty=true)

# OpenCode
terminal(command="opencode run 'task description'", workdir="/project")
```

### Interactive PTY via tmux (Multi-Turn Sessions)
```bash
#适用于所有三个 agent
terminal(command="tmux new-session -d -s agent-work -x 140 -y 40")
terminal(command="tmux send-keys -t agent-work 'cd /project && <agent-command>' Enter")
# Monitor
terminal(command="tmux capture-pane -t agent-work -p -S -50")
```

### Background Mode (Long Tasks)
```bash
terminal(command="<agent> exec --full-auto 'task'", workdir="/project", background=true, pty=true)
# Monitor
process(action="poll", session_id="<id>")
process(action="log", session_id="<id>")
```

### Parallel Work with Worktrees
```bash
terminal(command="git worktree add -b fix/issue-78 /tmp/issue-78 main")
terminal(command="<agent> exec 'Fix issue #78' --workdir /tmp/issue-78 --background")
```

## PR Review Patterns

All agents can review PRs:

```bash
# Claude Code: from PR number
terminal(command="claude -p 'Review this PR thoroughly' --from-pr 42 --max-turns 10", workdir="/repo", timeout=120)

# Codex: clone + review
terminal(command="REVIEW=$(mktemp -d) && git clone ... && gh pr checkout 42 && codex review --base origin/main", pty=true)

# OpenCode: built-in PR command
terminal(command="opencode pr 42", workdir="/project", pty=true)
```

## Detailed References

| Agent | Reference | Key Contents |
|-------|-----------|-------------|
| Claude Code | [references/claude-code.md](references/claude-code.md) | Full CLI flags, print mode, interactive mode, hooks, MCP, CLAUDE.md, settings, subagents, troubleshooting |
| Codex | [references/codex.md](references/codex.md) | Auth (OAuth + API key), phone verification workarounds, headless auth, exec mode, worktrees |
| OpenCode | [references/opencode.md](references/opencode.md) | Multi-provider auth, one-shot vs interactive, TUI keybindings, session management |
| Kimi Code CLI | [references/kimi-code-cli.md](references/kimi-code-cli.md) | 国内终端 AI 编程 Agent（用户 cmd 里用 `kimi`）：免审批参数 `--yolo`/`--auto`、命令速查、`kimi web` 本地服务、config.toml 持久化 |
| Third-party providers | [references/third-party-providers.md](references/third-party-providers.md) | cc-haha setup, domestic Chinese model providers (MiMo, DeepSeek) |
| ChatGPT Plus subscription | [references/chatgpt-plus-subscription-guide.md](references/chatgpt-plus-subscription-guide.md) | US/Turkish Apple gift card flows, regional pricing |
| macOS SSH admin | [references/macos-ssh-administration.md](references/macos-ssh-administration.md) | SSH into macOS for agent management |

## Pitfalls (Universal)

1. **PTY required for interactive mode** — all three agents are TUI apps that hang without a PTY
2. **Git repo required** — Codex and OpenCode refuse to run outside a git directory
3. **Session monitoring** — use `tmux capture-pane` (Claude Code) or `process(action="poll")` (all)
4. **Clean up tmux sessions** — background sessions persist; kill when done
5. **Cost awareness** — set `--max-turns` (Claude Code) or `--max-budget-usd` to prevent runaway costs
6. **Context degradation** — quality drops above 70% context window usage; compact or start fresh

## Rules for Hermes Agents

1. Prefer print mode / `run` for single tasks — cleaner, no dialog handling
2. Use tmux for multi-turn interactive work
3. Always set `workdir` to keep agents focused on the right project
4. Set `--max-turns` in print mode to prevent infinite loops
5. Monitor sessions proactively — don't block waiting
6. Clean up tmux sessions when done
7. Report results with concrete outcomes (files changed, tests passing)
