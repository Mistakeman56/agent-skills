# OpenAI Codex CLI — Complete Guide (2026)

## What It Is

OpenAI Codex CLI is a **terminal-based AI coding agent** that runs locally on your machine. It can read, change, and run code in a selected directory. Open source (Apache-2.0) at https://github.com/openai/codex.

## Four Ways to Use Codex

| Mode | How | Best For |
|:----|:----|:---------|
| **CLI** | `codex` in terminal | Core usage, most flexible |
| **VS Code Extension** | Install from IDE marketplace | Editing in context |
| **Desktop App** | `codex app` | GUI-friendly |
| **Web** | chatgpt.com/codex | Zero-install cloud |

## Installation

```bash
# npm (all platforms)
npm install -g @openai/codex

# Homebrew (macOS)
brew install --cask codex

# Binary download
# From https://github.com/openai/codex/releases/latest
# macOS ARM: codex-aarch64-apple-darwin.tar.gz
# Linux x64:  codex-x86_64-unknown-linux-musl.tar.gz
```

## Authentication

Run `codex` → **Sign in with ChatGPT** (uses your Plus/Pro plan).

You can also use an API key, but this requires additional setup (separate billing at $1.50/1M input, $6/1M output for codex-mini-*).

## Usage Limits (ChatGPT Plus)

- **Limit type:** Reasoning-time-based, not message-count-based
- **Plus ($20/mo):** ~40 minutes of reasoning time per 5-hour rolling window
- **Pro ($200/mo):** 5x the Plus limit
- **Over-limit:** Can purchase additional credits without upgrading plan
- **Shared across:** Codex CLI + ChatGPT web + any OAuth-connected tools
- **Complexity matters:** Longer reasoning tasks consume more of the 5-hour cap

## Key Features

- **Read & modify code** in the working directory
- **Run commands** to test/verify changes
- **Multi-file edits** with awareness of project context
- **Asynchronous** — submit tasks, wait for results
- **AGENTS.md support** — project-level instructions for Codex

## Comparison with Other AI Coding Agents

| Dimension | Codex CLI | Claude Code | Cursor |
|:----------|:---------:|:-----------:|:-----:|
| **Model** | GPT-5-Codex | Claude Opus 4/4.6 | Claude/GPT multi |
| **Token efficiency** | ✅ Most efficient | ⚠️ 5.5x more tokens | ⚠️ High |
| **Reasoning** | Good | ✅ Best (SWE-bench) | Good |
| **Interactive vs Async** | Async (submit & wait) | Interactive (real-time) | Interactive |
| **MCP** | ❌ No native | ✅ Native | ✅ Plugin |
| **Pricing** | Included in Plus | API-based ($3/M tokens) | $20/mo |
| **Open source** | ✅ Apache-2.0 | ❌ | ❌ |

## For the User (<PASSWORD>)

### Why Codex CLI matters for them:

1. **GPT Plus includes Codex usage** — once their Plus subscription is active, they can use Codex at no extra cost
2. **Could run on PVE server** — Linux binary works on the same Hermes host
3. **Complementary to local Gemma** — Codex for code generation, Gemma for data processing
4. **Could be integrated via MCP** — if Codex gets MCP support, Hermes could directly delegate coding tasks

### Integration idea for the user's setup:

```
User sends task via WeChat
  → Hermes (this agent) plans and delegates
    → Codex CLI writes the code
    → Local Gemma processes data / formats output
    → Hermes delivers result back to WeChat
```

## Pitfalls

- **Limits are shared** — using Codex in the web app also consumes your CLI limit
- **Reasoning-heavy tasks eat the cap fast** — 40 min reasoning ≈ 20 code reviews or 3-5 complex features
- **Not real-time** — unlike Claude Code, you submit and wait. You can't continue a conversation in the CLI
- **AGENTS.md is project-specific** — works best with a per-project config file
- **Ollama/OpenAI API key mode is separate billing** — using Codex with an API key costs extra and doesn't count toward your Plus plan's included usage

## Key URLs

- GitHub: https://github.com/openai/codex
- Codex pricing: https://developers.openai.com/codex/pricing
- Using Codex with ChatGPT: https://help.openai.com/en/articles/11369540-codex-in-chatgpt
