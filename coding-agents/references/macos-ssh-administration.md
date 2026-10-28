# macOS SSH Remote Administration Patterns

## SSH Credentials (User's MacBook Air)

| Field | Value |
|-------|-------|
| LAN IP | 192.0.2.10 (DHCP, may change) |
| Tailscale IP | 100.64.0.1 |
| Username | cuiyiming |
| Password | <PASSWORD> |
| SSH enabled | Yes (Remote Login in System Settings → General → Sharing) |

**⚠️ LAN IP changes on reboot.** If LAN SSH fails, try Tailscale IP. If both fail, Mac is likely sleeping or Tailscale disconnected.

## PATH Issues in SSH Sessions

macOS SSH sessions do NOT load:
- nvm (`~/.nvm/nvm.sh`)
- homebrew shellenv (unless in `~/.zprofile` or `~/.zshrc`)
- Interactive shell RC files (SSH uses non-interactive login shell)

**Fix:** Always prefix commands with:
```bash
export PATH=/opt/homebrew/bin:$PATH
```

**Common paths:**
| Tool | Path |
|------|------|
| node/npm | `/opt/homebrew/bin/node`, `/opt/homebrew/bin/npm` |
| brew | `/opt/homebrew/bin/brew` |
| claude | `/opt/homebrew/bin/claude` (after symlink restore) |
| python3 | `/usr/bin/python3` (system) or `/opt/homebrew/bin/python3` |

## Scp File Transfer

```bash
# Local → Remote
sshpass -p '<PASSWORD>' scp -o StrictHostKeyChecking=no /tmp/file.py cuiyiming@100.64.0.1:/tmp/file.py

# Remote → Local
sshpass -p '<PASSWORD>' scp -o StrictHostKeyChecking=no cuiyiming@100.64.0.1:/tmp/file.py /tmp/file.py
```

## Reliable Pattern for Complex Remote Operations

When SSH + heredoc + Python escaping becomes unmanageable:

1. Write the script locally to `/tmp/script.py`
2. SCP it to the remote machine
3. Execute via SSH: `sshpass -p '<PASSWORD>' ssh ... "python3 /tmp/script.py"`
4. Clean up: `sshpass -p '<PASSWORD>' ssh ... "rm /tmp/script.py"`

This avoids all bash↔Python↔SSH escaping issues.

## Common Tasks

### Check Claude Code Status
```bash
sshpass -p '<PASSWORD>' ssh cuiyiming@IP '
export PATH=/opt/homebrew/bin:$PATH
echo "=== claude binary ==="
ls -la /opt/homebrew/bin/claude 2>/dev/null || echo "MISSING"
echo "=== npm global ==="
npm list -g --depth=0 2>/dev/null | grep claude
echo "=== settings.json ==="
cat ~/.claude/settings.json 2>/dev/null
'
```

### Check System Proxy Status
```bash
sshpass -p '<PASSWORD>' ssh cuiyiming@IP '
echo "=== networksetup ==="
networksetup -getwebproxy Wi-Fi
echo "=== scutil ==="
echo "show State:/Network/Global/Proxies" | scutil | head -10
'
```

### Fix .zshrc (Python Script Pattern)
```python
# Write locally as /tmp/fix_zshrc.py, then scp + execute
import json

home = "/Users/cuiyiming"
with open(f"{home}/.openclaw/agents/main/agent/auth-profiles.json") as f:
    kimi_key = json.load(f)["profiles"]["openai:manual"]["key"]

content = f'''# Homebrew
eval "$(/opt/homebrew/bin/brew shellenv)"

# OpenClaw Completion
source "/Users/cuiyiming/.openclaw/completions/openclaw.zsh"

. "$HOME/.local/bin/env"

# OpenClaw - Kimi API
export OPENAI_BASE_URL="https://api.kimi.com/coding/v1"
export OPENAI_API_KEY="{kimi_key}"

# PATH
export PATH="/opt/homebrew/bin:$HOME/.local/bin:$PATH"
'''

with open(f"{home}/.zshrc", "w") as f:
    f.write(content)
print("done")
```
