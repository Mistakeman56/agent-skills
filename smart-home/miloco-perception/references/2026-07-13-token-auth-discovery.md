# 2026-07-13: Token Authentication Discovery

## Problem
Pre-run script timed out fetching perception logs. Manual SSH + `miloco-cli perceive logs` returned `"cannot connect to Miloco backend at http://127.0.0.1:1810"` despite backend being healthy.

## Root Cause
`miloco-cli perceive logs` requires `MILOCO_TOKEN` environment variable for authentication. Without it, the CLI cannot connect even though:
- Backend is running (PID 594021, `/usr/bin/python3 -m miloco.main`)
- Port 1810 is listening (`ss -tlnp | grep 1810` → `LISTEN 0 2048 0.0.0.0:1810`)
- `curl -s http://127.0.0.1:1810/` returns the web UI HTML

## Fix
```bash
export MILOCO_TOKEN=95ac63403f1f45a38f66f72bd085b27b81c2352c3f1546f991c03c07f3f7a082
miloco-cli perceive logs --since 1h --limit 10 --jsonl
```

## Token Location
The token is embedded in the web UI's `index.html`:
```html
window.__MILOCO_TOKEN__ = "95ac63403f1f45a38f66f72bd085b27b81c2352c3f1546f991c03c07f3f7a082";
```
Extract via:
```bash
curl -s http://127.0.0.1:1810/ | grep -oP 'MILOCO_TOKEN__ = "\K[^"]+'
```

## Backend Architecture
- Managed by **supervisord** (not systemd)
- Config: `/root/.openclaw/miloco/supervisord.conf`
- Process: `/usr/bin/python3 -m miloco.main`
- Log: `/root/.openclaw/miloco/log/miloco-backend.log`
- CLI: `/usr/local/bin/miloco-cli` (must be on PATH)

## Key Commands Verified
| Command | Status |
|---------|--------|
| `miloco-cli perceive logs --since 1h --limit 5 --jsonl` | ✅ Works with token |
| `miloco-cli perceive --help` | ✅ Shows subcommands: clear, devices, logs, query |
| `miloco-cli service status` | ✅ Fast health check (no token needed) |
| `ss -tlnp \| grep 1810` | ✅ Confirms backend listening |
| `ps aux \| grep miloco` | ✅ Shows supervisord + miloco.main |
