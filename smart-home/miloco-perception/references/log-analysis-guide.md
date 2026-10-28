# Perception Log Analysis Guide

## `perceive logs` Options

| Flag | Purpose | Example |
|------|---------|---------|
| `--since 1h` | Relative time window (`h`/`m`/`s`/`d` combos) | `miloco-cli perceive logs --since 1h` |
| `--limit N` | Cap result count | `miloco-cli perceive logs --since 1h --limit 30` |
| `--jsonl` | JSONL output (timestamp prefix, one JSON per line) | `miloco-cli perceive logs --jsonl` |
| `--pretty` | Human-readable formatted output | `miloco-cli perceive logs --pretty` |

**Agent cron usage**: `--since 1h --limit 50` for monitoring. `--jsonl` for structured parsing.

### ⚠️ PITFALL: `--sort` Flag Does Not Exist
The `--sort` flag is NOT a valid option for `miloco-cli perceive logs`. Using it causes the command to hang or timeout (the CLI likely ignores unrecognized flags and enters a bad state):

```
❌ --sort desc               → Timeout (flag not supported)
❌ --sort asc                → Timeout (flag not supported)
✅ --since 1h --limit 5     → Returns recent events (sorted by time by default)
```

The only supported flags are: `--since`, `--limit`, `--jsonl`, `--pretty`. There is no way to change sort order — results are always returned in chronological order.

### ⚠️ PITFALL: `--after` Flag Causes Timeouts
The `--after` flag (absolute timestamp) can cause CLI commands to hang/timeout on large datasets. Avoid using it:
```
❌ --after 2026-07-14T00:00:00   → Timeout after 30s
✅ --since 24h                   → Returns quickly
✅ --since 7d                    → Returns quickly
```
Always use `--since` with a duration window instead of `--after` with absolute timestamps.

### ⚠️ PITFALL: `--since` Rejects Natural Language
The `--since` flag requires compact duration format, NOT natural language:
```
❌ --since "2 hours ago"   → Error: "Invalid 'since' format: 2 hours ago. Expected e.g. '30m', '1h', '2h30m', '7d'."
❌ --since "1 hour"        → Same error
✅ --since 2h
✅ --since 30m
✅ --since 1h30m
```

### ⚠️ PITFALL: Timestamps Are UTC, Not Local
Perception log timestamps use ISO 8601 with `+00:00` (UTC). When interpreting for a Chinese user, **add 8 hours** for CST:
```
Log entry:  "t": "2026-07-13T13:19:15+00:00"
Local time:  2026-07-13 21:19:15 CST (UTC+8)
```
Always convert in your analysis — reporting "13:19" as the event time is misleading. Use phrases like "晚上9:19" or "21:19 CST" instead.

## ⚠️ PITFALL: Stale Cursor with Default `perceive logs`

Running `miloco-cli perceive logs` **without `--since`** uses cursor-based incremental pulling. If the cursor file hasn't been updated recently (e.g. after a service restart, container reboot, or long idle period), **it returns days-old events as if they were current**. In one session, the default query returned logs from 19 days ago while `--since 7d` found events from yesterday.

**Rule**: Always use `--since` with a time window when checking for recent events in cron jobs or monitoring scripts. The cursor is useful for agent loops that process events incrementally, but NOT for "what happened recently?" queries.

```bash
# ❌ BAD — may return ancient events
miloco-cli perceive logs --limit 5

# ✅ GOOD — guaranteed recent window
miloco-cli perceive logs --since 24h --limit 10
```

## Perception Log Format

Each JSONL line: `TIMESTAMP: {"区域名": "描述", ...}`

- Keys = camera/area names (e.g. `三楼书房`, `前院`, `北院`)
- Values = natural-language scene descriptions
- Person/pet presence is described in the value text; no boolean flags

## Backend Health Check

The `miloco-backend` runs as a **python3 process** on port 1810 — NOT a systemd service.

```bash
pct exec 310 -- bash -c 'curl -s http://127.0.0.1:1810/health'
# Expected: {"status":"ok"}
```

If `miloco-cli perceive logs` returns `"cannot connect to Miloco backend"`:

### Startup Delay Pattern (Process Alive, Port Not Yet Bound)
The backend may be **starting up** — the process is running but hasn't bound port 1810 yet. Wait ~10 seconds and retry:
```bash
# 1. Confirm process exists
pct exec 310 -- bash -c 'ps aux | grep miloco.main | grep -v grep'
# 2. Check port binding
pct exec 310 -- bash -c 'ss -tlnp | grep 1810'
# 3. If port not listening, wait and retry
sleep 10 && pct exec 310 -- bash -c 'ss -tlnp | grep 1810'
```

### Supervisord Diagnostics
The backend is managed by **supervisord** (not systemd). Use these to check status and logs:
```bash
pct exec 310 -- bash -c 'export PATH=/usr/local/bin:$PATH; supervisorctl -c /root/.openclaw/miloco/supervisord.conf status'
pct exec 310 -- bash -c 'export PATH=/usr/local/bin:$PATH; supervisorctl -c /root/.openclaw/miloco/supervisord.conf tail -30 miloco-backend'
```
Note: `supervisorctl tail` shows the last N lines of the backend log — useful for seeing startup errors.

### ⚠️ Distinguishing Startup Delay vs. Missing Token

Both scenarios produce the identical error: `"cannot connect to Miloco backend at http://127.0.0.1:1810"`. Quick diagnostic:

```bash
# 1. Check if port is bound (if empty → startup delay, wait 10s)
pct exec 310 -- bash -c 'ss -tlnp | grep 1810'

# 2. If port IS bound, test curl directly (if it works → missing token)
pct exec 310 -- bash -c 'curl -s http://127.0.0.1:1810/ | head -1'

# 3. If curl also fails → backend started but crashed; check logs
pct exec 310 -- bash -c 'export PATH=/usr/local/bin:$PATH; supervisorctl -c /root/.openclaw/miloco/supervisord.conf tail -20 miloco-backend'
```

**Decision tree**:
- Port empty → wait 10s, retry (startup delay pattern)
- Port bound + curl works → set MILOCO_TOKEN and retry
- Port bound + curl fails → **check `supervisorctl status` uptime first**:
  - If uptime < 30s → **still starting up** (port bound but not yet accepting connections). Wait 15s, retry `miloco-cli perceive logs` directly — do NOT force-kill.
  - If uptime > 30s (or minutes/hours) → backend likely crashed; check `supervisorctl tail`, then force-kill and restart.

> **Pitfall**: After a supervisord restart, `ss` shows port 1810 bound and `curl` returns exit code 7, but the backend is still initializing. Treating this as a crash and force-killing will kill a perfectly healthy startup. Always check `supervisorctl status` uptime before escalating to force-kill.

### ⚠️ Forced Restart When "Already Running" but Unresponsive
If `miloco-cli service start` reports `"already running (pid=XXXX)"` but the backend isn't serving requests (curl returns empty/error on port 1810), the process may be in a zombie state.

**Detect zombie main process** — run `ps aux | grep miloco` and look for `<defunct>`:
```
root  3812  ...  supervisord -c .../supervisord.conf   ← supervisord alive
root  116047 ... [python3] <defunct>                    ← main process is zombie
```
If you see `[python3] <defunct>` for the `miloco.main` process while supervisord still shows `running`, the backend is dead despite supervisord claiming it's alive. This is the zombie state.

Force-kill everything and restart fresh:

```bash
pct exec 310 -- bash -c 'export PATH=/usr/local/bin:$PATH; killall -9 miloco-cli python3 2>/dev/null; sleep 2; nohup miloco-cli service start &>/tmp/miloco-restart.log &'
# Wait for port to bind (typically 5-10s after kill)
sleep 8
pct exec 310 -- bash -c 'ss -tlnp | grep 1810'
# Then verify with:
pct exec 310 -- bash -c 'curl -s http://127.0.0.1:1810/ | head -1'
```

**Pitfall**: `killall -9 python3` is aggressive — it will also kill the supervisord parent process. After restart, supervisord will respawn. This is expected behavior and does not require manual supervisord restart.

### Other Checks
1. Check `ss -tlnp | grep 1810` — if nothing, backend is down or starting
2. Check `systemctl list-units --type=service | grep miloco` — may not be registered
3. Check `ps aux | grep miloco-backend` — may have crashed
4. Backend binary: `/usr/local/bin/miloco-backend`

## ⚠️ PITFALL: Not All Subcommands Need the Token

`person list` and `perceive devices` work WITHOUT `MILOCO_TOKEN`. Only `perceive logs` (and similar perception query commands) require it. This creates a useful **diagnostic shortcut**:

```
✅ miloco-cli person list          → Works (no token needed)
✅ miloco-cli perceive devices     → Works (no token needed)
❌ miloco-cli perceive logs        → "cannot connect to Miloco backend"
```

**If `person list` and `perceive devices` succeed but `perceive logs` fails, it's almost certainly the missing token — NOT a backend crash.** Skip the supervisord / force-kill / restart diagnostics and just set the token first:

```bash
export MILOCO_TOKEN=$(curl -s http://127.0.0.1:1810/ | grep -oP 'MILOCO_TOKEN__ = "\K[^"]+')
miloco-cli perceive logs --since 1h --limit 5
```

This avoids 5-10 minutes of unnecessary container restart cycles when the backend is actually fine.

## Token Authentication Required

`miloco-cli perceive logs` requires the `MILOCO_TOKEN` environment variable, even when the backend is running on port 1810. Without it, the CLI returns: `"cannot connect to Miloco backend at http://127.0.0.1:1810"`.

**How to get the token**: Fetch the web UI index page and extract it:
```bash
curl -s http://127.0.0.1:1810/ | grep -oP 'MILOCO_TOKEN__ = "\K[^"]+'
```
Current token (rotate if compromised): `95ac63403f1f45a38f66f72bd085b27b81c2352c3f1546f991c03c07f3f7a082`

## Full Retrieval Command (SSH into CT <ID>)

```bash
sshpass -p "<PASSWORD>" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=15 root@192.0.2.10 \
  "pct exec 310 -- bash -c 'export PATH=/usr/local/bin:\$PATH; export MILOCO_TOKEN=95ac63403f1f45a38f66f72bd085b27b81c2352c3f1546f991c03c07f3f7a082; miloco-cli perceive logs --since 1h --limit 50 2>&1'"
```

Note: `\$PATH` escaping is required when nesting bash -c inside pct exec.

## Detecting Pipeline Stoppage vs. Cursor Staleness

Two different failure modes produce "old logs" — diagnose correctly:

| Symptom | Cause | Fix |
|---------|-------|-----|
| `--since 1h` returns nothing, but `--since 7d` or default query returns events | **Cursor staleness** — cursor file not updated after restart/idle | Use `--since` with a wider window |
| `--since 7d` also returns nothing, or latest event is days/weeks old | **Pipeline stoppage** — cameras disconnected, inference service crashed, or backend stopped processing | Check camera online status (`miloco-cli perceive devices`), restart backend |

**Detection pattern for cron jobs**: After fetching logs, compare the latest event timestamp to current time. If the gap exceeds a configurable threshold (e.g. 2 hours), flag it as a potential pipeline stoppage rather than just "no events."

```bash
# Quick staleness check — extract latest timestamp and compare
LATEST=$(miloco-cli perceive logs --limit 1 --jsonl 2>/dev/null | head -1 | grep -oP '"t": "\K[^"]+')
if [ -n "$LATEST" ]; then
  LATEST_EPOCH=$(date -d "$LATEST" +%s 2>/dev/null)
  NOW_EPOCH=$(date +%s)
  AGE_HOURS=$(( (NOW_EPOCH - LATEST_EPOCH) / 3600 ))
  if [ "$AGE_HOURS" -gt 2 ]; then
    echo "WARNING: Latest perception event is ${AGE_HOURS}h old — pipeline may be stopped"
  fi
fi
```

## Soft Restart Before Force-Kill

When `miloco-cli perceive logs` returns `"cannot connect to Miloco backend"`, try a soft restart first — it may reconnect without killing processes:

```bash
pct exec 310 -- bash -c 'export PATH=/usr/local/bin:$PATH; miloco-cli service start 2>&1'
# If it says "already running (pid=XXX)" — wait 5s and retry the logs query
sleep 5
pct exec 310 -- bash -c 'export PATH=/usr/local/bin:$PATH; miloco-cli perceive logs --since 1h --limit 5 2>&1'
```

If this doesn't recover the backend, fall through to the force-kill pattern documented above.

## Device Health Check

Use `miloco-cli perceive devices` to verify camera status:

```bash
pct exec 310 -- bash -c 'export PATH=/usr/local/bin:$PATH; miloco-cli perceive devices 2>&1'
```

Returns JSON with each camera's `online` status, `did`, and `room_name`. All cameras should show `"online": true`.

## Active Perception Query (`perceive query`)

For real-time camera analysis (not historical logs), use `perceive query`:

```bash
miloco-cli perceive query --source <camera_did> --query "现在画面中有人吗？" 2>&1
```

| Flag | Purpose | Required |
|------|---------|----------|
| `--source` | Camera device DID (repeatable) | ✅ |
| `--query` | Natural language question about the scene | ✅ |
| `--pretty` | Human-readable output | Optional |

**Example** — check if someone is in the study:
```bash
miloco-cli perceive query --source 1180976594 --query "三楼书房有人吗？" 2>&1
```

**Multi-camera query** (merge views):
```bash
miloco-cli perceive query --source 1180976594 --source 1179415436 --query "家里有人吗？" 2>&1
```

**Pitfall**: This command is slower than `perceive logs` (5-30s) because it triggers a fresh multi-modal inference. It may hang or timeout when the backend is under heavy load. Use `--query` (not `--question` — the flag name is `--query`).

**Camera DIDs** (from `miloco-cli device list`):
- 三楼书房: `1180976594`
- 前院: `1179415436`
