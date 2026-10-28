# Miloco Perception Engine — Diagnostics Reference

## Correct CLI Subcommands

The `miloco-cli` CLI has evolved — older subcommand names no longer work:

| ❌ Wrong | ✅ Correct | Purpose |
|----------|-----------|---------|
| `miloco-cli perception log` | `miloco-cli perceive logs` | Query perception event history |
| `miloco-cli perception status` | `miloco-cli perceive --help` | Discover available perceive subcommands |

**Pitfall**: `miloco-cli` will error with "No such command 'perception'" and suggest alternatives like `perceive` or `person`. Always use `perceive` as the parent subcommand.

## Reliable Quick-Diagnostics

When perception log queries hang, these simpler commands work faster and confirm the service is alive:

1. **Service status** (fast, returns JSON):
   ```
   miloco-cli service status
   ```
   Returns: `{"running": true, "managed": true, "pid": ..., "uptime_seconds": ..., "log_file": "...", "server": {"url": "..."}}`

2. **Backend log tail** (confirm recent activity):
   ```
   tail -30 /root/.openclaw/miloco/log/miloco-backend.log
   ```
   Look for: `MiotProxy initialization successful`, `device online`, `RuleRunner init`

3. **Process check** (confirm miloco processes are running):
   ```
   ps aux | grep -i miloco
   ```
   Should show: `supervisord`, `miloco-cli service start`, `miloco.main`

## Pitfall: High PVE Load Causes miloco-cli Timeouts

When PVE host load average is high (e.g. 9+), even basic `miloco-cli` commands like `perceive logs` may time out after 15-30s, despite CT <ID> being responsive to `pct exec 310 -- echo OK`.

**Workaround**: Use `miloco-cli service status` instead — it's fast and returns JSON confirming the service is running. Then check `miloco-backend.log` directly for recent activity.

**Symptom**: PVE `uptime` shows load 9+, `pct exec 310 -- echo OK` works but `miloco-cli perceive logs` hangs.

## ⚠️ PITFALL: Never Start Backend with `nohup`

Starting `miloco-backend` with `nohup miloco-backend &` bypasses supervisord and causes **pct exec to hang indefinitely** — even `pct exec 310 -- uptime` times out.

**Always use supervisord**:
```bash
# ✅ Correct
pct exec 310 -- supervisorctl -c /root/.openclaw/miloco/supervisord.conf start miloco-backend

# ❌ WRONG — causes container hang
pct exec 310 -- bash -c 'nohup miloco-backend &>/tmp/miloco-backend.log &'
```

If pct exec hangs after a nohup start: `pct exec 310 -- killall miloco-backend`, wait 5s, then restart via supervisord. See `references/pitfall-nohup-backend-start.md` for full recovery.

## Pitfall: MILOCO_TOKEN Required for perceive logs

Even with the backend healthy on port 1810, `miloco-cli perceive logs` fails with `"cannot connect to Miloco backend"` unless `MILOCO_TOKEN` is set. This is an authentication requirement, not a connectivity issue.

**Fix**: `export MILOCO_TOKEN=<token>` before calling the CLI. Token is in the web UI's `index.html` (`window.__MILOCO_TOKEN__`). Current: `95ac63403f1f45a38f66f72bd085b27b81c2352c3f1546f991c03c07f3f7a082`.

**Quick check**: `curl -s http://127.0.0.1:1810/ | grep -oP 'MILOCO_TOKEN__ = "\K[^"]+'`

## ⚠️ PITFALL: False-Alarm Shortcut Misfires During an OOM/Restart Loop

The documented false-alarm shortcut (miloco.main at >100% CPU, STAT `Sl`, CPU TIME accumulating) ALSO matches a backend auto-restarting under memory pressure — re-initializing, reloading models, churning. Do NOT declare "false alarm" on the ps pattern alone. **Validate with the health endpoint BEFORE skipping steps 3-7**:

- If `curl http://localhost:1810/health` fails (exit 7 connection refused, or timeout) instead of returning `{"status":"ok"}` → NOT a clean false alarm.
- If the miloco.main PID changes between two `ps` checks → restart churn, check WHY (dmesg OOM + MemAvailable + supervisord SIGKILL count).

**2026-08-01 05:05 session**: ps showed Sl/109-138% CPU/accumulating TIME (looked exactly like the shortcut), but health refused + PID churn (3589886→3595194→3602759) → dmesg showed OOM kill at 05:03, MemAvailable 14MB (critical, threshold <50MB), SIGKILL 3676 — an ongoing OOM loop, not a clean false alarm. Same OOM loop flagged earlier that day (reference `2026-08-01-oom-sigkill-loop.md`); SIGKILL count climbed 3649→3676, MemAvailable dropped 173MB→14MB.

**Also**: a fresh process at ~0:49 CPU time does NOT yet satisfy shortcut criterion (3) "accumulated in minutes" — wait/verify before treating it as confirmed inference.
