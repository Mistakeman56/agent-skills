# Cron Watchdog Pattern (`no_agent=True` + Conditional Output)

Monitor anything with **zero LLM cost** — a script that only outputs when a value changes, wired as a `no_agent=True` cron job. The output is delivered verbatim; if the script exits silently (no stdout), nothing is sent.

## When to Use

- Balance monitoring (DeepSeek, OpenRouter, etc.)
- Quota / usage tracking (API rate limits, token budgets)
- Health checks that should only alert on state change
- Any sensor-like monitoring where silence = no news

## Setup

### 1. Write the watchdog script

Place in `~/.hermes/scripts/` — cron `no_agent` requires scripts relative to this dir.

**Pattern:**
```python
#!/usr/bin/env python3
"""Watchdog: output only when value changes."""
import json, urllib.request, os

CACHE = os.path.expanduser("~/.hermes/.my_watchdog_cache")

# 1. Fetch current value
# (API call, file read, command output, etc.)
current = "..."

# 2. Read last cached value
last = ""
if os.path.exists(CACHE):
    with open(CACHE) as f:
        last = f.read().strip()

# 3. Compare — silent exit if unchanged
if current == last:
    exit(0)

# 4. Value changed — update cache and output
with open(CACHE, 'w') as f:
    f.write(str(current))

# 5. Output is delivered verbatim to the user
print(f"🔔 [Watchdog] Value changed!")
print(f"Previous: {last}")
print(f"Current:  {current}")
```

### 2. Create the cron job

```bash
hermes cron create "every 30m" \
  --name "My Watchdog" \
  --script "my_watchdog.py" \
  --deliver origin \
  --no-agent
```

Key params:
- `--no-agent` — the script IS the job; no LLM is invoked
- `--script` — relative path under `~/.hermes/scripts/`
- `--deliver origin` — sends stdout to the user's active chat platform
- Empty stdout (or `exit(0)` without printing) = no delivery

### 3. Verify

```bash
hermes cron list          # Check job exists and is enabled
```

First run always fires (no prior cache → "change" detected). Subsequent runs are silent until the value actually changes.

## Pitfalls

- **Script path must be relative** to `~/.hermes/scripts/`. Absolute paths are rejected.
- **Stderr is not delivered.** Only stdout is sent. Use `print()` for output, `exit(1)` with messages to stderr for error logging (visible in cron run logs, but not sent to user).
- **Cache file location.** Use `~/.hermes/` to keep state alongside config. Use a unique filename per watchdog to avoid collisions.
- **Exit code matters.** `exit(0)` = success (output delivered). Non-zero = job failed (logged, not delivered to user).
- **API key extraction from config.yaml.** When reading Hermes's own config (e.g. for DeepSeek balance), use Python regex: `re.search(r'model:.*?api_key:\s*([^\n]+)', content, re.DOTALL)`. The `...` displayed by `grep`/`cat` is a truncation artifact — the full key is in the file.

### Script Gotcha: Config File Regex Parsing

When a `no_agent` watchdog script reads the API key from `~/.hermes/config.yaml`, beware of **multiline regex matching**:

```yaml
model:
  api_key: sk-eec...b7d6        # ← target this
  base_url: https://api.deepseek.com/v1
  default: deepseek-chat
  provider: deepseek
```

If the script does:
```python
# WRONG — DOTALL mode causes this to span across sections
match = re.search(r'model:.*?api_key:\s*([^\n]+)', content, re.DOTALL)
```

The DOTALL flag makes `.` match newlines, so the regex can skip past unrelated config blocks (custom_providers, auxiliary, etc.) and match the *wrong* `api_key:` field entirely, returning a Kimi key instead of the DeepSeek key.

**Fix:** Use `re.MULTILINE` and anchor the match to the start of the line:
```python
# RIGHT — anchored to start of line, no DOTALL
match = re.search(r'^model:\s*\n\s+api_key:\s*(\S+)', content, re.MULTILINE)
```

This ensures it only matches when `model:` starts a new line and `api_key:` is directly within the next line of that block—not somewhere else in the config file.

---

## Example

See `~/.hermes/scripts/deepseek_balance_watchdog.py` for a complete working watchdog that:
- Queries DeepSeek /user/balance API
- Caches the previous total balance
- Only outputs (triggers delivery) when the balance changes
- Runs every 30 minutes via `hermes cron`
