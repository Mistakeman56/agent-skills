# Miloco Service Restart — Incident Log (2026-07-16)

## Problem
Pre-run cron job timed out: `⚠️ 获取感知日志超时，PVE/CT <ID> 可能不可达`

## Diagnosis
1. `pct status 310` → `running` (fast)
2. `ps aux | grep miloco` showed 7 processes, including:
   - `miloco-cli perceive logs --limit 1` (R state, 0:14 CPU)
   - `miloco-cli service start` (R state, 0:09 CPU)
   - `miloco-cli perceive logs --limit 10` (R state)
   - Multiple `bash -c` wrappers
3. No miloco.main or supervisord processes visible (they were killed in a previous attempt)

## What Happened
- `miloco-cli service stop` returned `{"code":0,"message":"stopped"}` but exit code 137 (killed by `kill -9`)
- After stop + kill, **zero** miloco processes remained — supervisord itself was dead
- `miloco-cli service start` **hung** (15s timeout) — the CLI itself was stuck
- `curl http://127.0.0.1:1810/health` returned empty — backend not running

## Fix That Worked
```bash
killall -9 python3 2>/dev/null    # nuke all Python processes
killall -9 supervisord 2>/dev/null
sleep 2
# supervisord was NOT on PATH inside pct exec, but the full-path version worked:
/usr/bin/python3 /usr/local/bin/supervisord -c /root/.openclaw/miloco/supervisord.conf
```

## Verification (5s after start)
- `ps aux | grep miloco` → supervisord (PID 1547871) + miloco.main (PID 1547873, 60% CPU during init)
- `curl http://127.0.0.1:1810/health` → `{"status":"ok"}`
- `miloco-cli perceive logs --limit 3` → 3 entries returned (all from 2026-06-24, 12 days stale)
- `miloco-cli perceive devices` → 3 cameras, all online

## Key Takeaway
When process pileup is severe enough, `miloco-cli service start` itself can hang because the CLI subprocess management is blocked by zombie processes. The nuclear option (`killall -9 python3` + fresh supervisord) is the reliable fallback. The `supervisord` binary path issue (`command not found` without full path) is a minor PITFALL to remember.

## Stale Logs Note
Logs remain from 2026-06-24 (12 days old) after restart. This suggests the perception inference pipeline was down for an extended period. The backend is healthy but not generating fresh inferences yet — worth monitoring in subsequent cron runs.
