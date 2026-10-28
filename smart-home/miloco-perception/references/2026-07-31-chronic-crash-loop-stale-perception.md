# Chronic Crash Loop + Stale Perception — 2026-07-31 Late-Night Findings

**Date**: 2026-07-31 23:50 (Beijing), second cron incident the same evening (23:37 recovery + 23:50 re-check)

## Scenario
- Pre-run script: `⚠️ 无法解析感知日志` (could not parse perception log)
- PVE host load 6.33 (down from 12+ after the 23:37 host-side kill recovery) — host fine
- Backend was SIGKILLed AGAIN at 15:49:59 UTC (23:49 Beijing) — only ~5 min after the 23:44 "recovered" report. supervisord auto-respawned (new pid).

## Key new diagnostics (beyond existing references)

### 1. The crash loop is CHRONIC — check the kill count first
```bash
sshpass -p "<PASSWORD>" ssh -o ConnectTimeout=8 root@192.0.2.10 \
  "timeout 20 pct exec 310 -- grep -c SIGKILL /root/.openclaw/miloco/log/supervisord.log"
# 2026-07-31: 3638 SIGKILLs since 2026-06-27 (~107/day, every ~13 min)
```
A single recovery (kill + respawn) does NOT hold — the process gets SIGKILLed again within minutes. Root cause is resource exhaustion: miloco.main sits at ~95% of container RAM (2.0GB RSS) → OOM-kill pattern.

### 2. Identity fusion broken by expired omni API token → person_id=None
Even with a freshly running backend, the perception engine logs:
```
miloco.perception.engine.identity.engine - INFO - [Identity/omni] cam=... track_id=N → person_id=None conf=0.00
  reason="fused_main_call_failed: ... HTTPStatusError: Client error '401 Unauthorized' for url
  'https://token-plan-cn.xiaomimimo.com/v1/chat/completions'"
```
Tracks are detected (camera sees people) but WHO cannot be resolved → home/away automation is blind. Fix requires renewing the xiaomimimo omni API token in the backend config — not fixable via CLI.

### 3. Perception events 13 days stale despite backend running
`perception_log` table last entry 2026-07-18 (312+ h old); `meaningful_events` table EMPTY. Backend had been "up" between crashes but produced no perception events. Query the DB with python3 — **`sqlite3` CLI is NOT installed in CT <ID>**:
```bash
sshpass -p "<PASSWORD>" ssh -o ConnectTimeout=8 root@192.0.2.10 \
  "timeout 25 pct exec 310 -- python3 - <<'EOF'
import sqlite3, datetime, time
db = sqlite3.connect('/root/.openclaw/miloco/miloco.db')
now = time.time()
for r in db.execute('SELECT timestamp, descriptions FROM perception_log ORDER BY rowid DESC LIMIT 3'):
    print(datetime.datetime.utcfromtimestamp(r[0]/1000).isoformat(), round((now-r[0]/1000)/3600,1), 'h ago |', r[1][:60])
EOF"
```

### 4. Backend restarted at the exact moment the cron pre-run script executed
On 2026-07-31 the backend restart (15:50:03 UTC) collided with the cron run (23:50 Beijing) → perceive logs returned nothing parseable. Post-restart window: uptime <120s, queries return empty/errors. Do NOT retry aggressively (see pitfall #0 — piling stuck miloco-cli processes makes the container worse).

## Lessons
- A "recovered" backend can SIGKILL-loop again within 5 minutes. Always check `grep -c SIGKILL supervisord.log` and perception_log age to judge whether the fix actually holds.
- Distinguish three failure layers: (a) process crash-loop (memory), (b) identity auth 401 (token), (c) stale perception data (no events for days). Each needs a different fix; only (a) is handled by killing processes.
- Report to assistant should name the root causes (memory quota + expired token), not just "restarted OK".
