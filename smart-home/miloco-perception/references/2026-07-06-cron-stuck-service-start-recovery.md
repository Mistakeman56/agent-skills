# 2026-07-06 ~00:20 — Cron: Stuck service start → Nuclear restart recovery

## Context
Scheduled cron job (感知引擎监控). Pre-run script timed out: `⚠️ 获取感知日志超时，PVE/CT <ID> 可能不可达`.

## Diagnosis Sequence
1. `pct status 310` → `running` (fast, container alive)
2. `miloco-cli perceive logs --limit 5` → 30s timeout
3. `miloco-cli perceive devices` → 20s timeout
4. `curl http://127.0.0.1:1810/health` → exit code 7 (connection refused — port 1810 NOT listening)
5. `ps aux | grep miloco` → **key finding**:
   - supervisord running (Ss state, healthy)
   - `miloco-cli service start` stuck (bash wrapper + python3 in R/S state)
   - `supervisorctl status miloco-backend` stuck in R state
   - miloco.main process alive but port not bound

**Diagnosis: Scenario D** — stuck `miloco-cli` subprocesses blocking the CLI, port 1810 never bound.

## Nuclear Restart (1st attempt — succeeded)
```
killall -9 supervisord   # MUST be first — owns the listening port
killall -9 python3        # kills miloco.main + stuck cli processes
sleep 3                    # port release
rm -f /root/.openclaw/miloco/supervisor.sock
/usr/local/bin/supervisord -c /root/.openclaw/miloco/supervisord.conf
```

## Recovery Verification (all passed)
- Health: `{"status":"ok"}` within 10s
- Cameras: all 3 online (三楼监控 ✅ 北院摄像头 ✅ 前院摄像机 ✅)
- Service logs: showed fresh inference at 00:23:19 for 前院 ("前院空无一人，地面有水渍")
- Pipeline: `total_inferences` started incrementing, fresh timestamps

## Key Observations
1. **Single nuclear restart fixed it** — no need for container stop/start
2. **Port check (`ss -tlnp | grep 1810`) was the fastest diagnostic** — before the 20-30s timeout of `perceive logs` or `perceive devices`
3. The stuck processes were `miloco-cli service start` (from a previous cron attempt?) and `supervisorctl status` — both in R or S state, interfering with subsequent CLI calls
4. `perceive logs` still returned cached June 24 data initially, but fresh inferences appeared in service logs ~10s after restart
5. No home/away events in the latest perception data (前院 empty)

## Pattern Confirmation
This session confirms the Scenario D nuclear restart pattern from the skill works reliably:
- Kill supervisord first, then python3
- Clear supervisor.sock
- Start supervisord directly (full path)
- Wait 8-10s for port binding
- Health check to verify
