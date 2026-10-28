# 2026-07-08 Cron: B+ → A Cascade (Partial Recovery → Container Hang → Full Recovery)

## Timeline
- Pre-run script timed out fetching perception logs
- PVE reachable, CT <ID> running, pct exec works
- Diagnosed **Scenario B+**: port 1810 LISTENING but `curl health` → exit code 7 (connection refused)
- `ps aux` revealed:
  - supervisord (PID 34551) — alive
  - `miloco-cli service start` (PID 117735/117742) — stuck zombie
  - miloco.main (PID 117744) — **D state** (uninterruptible sleep)
- **First recovery attempt**: PID-targeted kill of stuck processes only (117744, 117742, 117735), left supervisord alive
  - Supervisord auto-restarted miloco.main (new PID 117844)
  - Health passed after ~15s
  - Service uptime 44s, `perceive logs --since 30m` returned cached data (`total_inferences: 0`)
  - Waited 30s → `perceive logs --since 2m` **timed out** (60s)
  - `ps aux` and `curl health` also started timing out → **progressive degradation**
  - pct exec completely hung → escalated to **Scenario A** (container hang)
- **Second recovery**: container stop/start via PVE
  - `pct stop 310` → verified stopped → `pct start 310`
  - Waited 10s → pct exec works
  - Started supervisord directly (not `miloco-cli service start`)
  - Health OK after ~20s
  - Waited 30s → `perceive logs --since 5m` returned fresh data (`total_inferences: 1`)
  - Pipeline fully recovered

## Key Pattern: Partial B+ Recovery Cascades to Container Hang

When you kill only the stuck miloco.main + zombie CLI processes but leave supervisord alive:

1. Supervisord auto-restarts miloco.main
2. New miloco.main briefly binds port 1810, health passes
3. Pipeline fails to produce fresh inferences (stale cache, `total_inferences: 0`)
4. Within 60s: progressive degradation → pct exec hangs → container effectively unresponsive

**Why this happens**: The auto-restarted miloco.main inherits the same broken state (D-state I/O blockage or pipeline deadlock) that killed the original. Supervisord's restart doesn't clear the underlying issue.

## Recovery Decision Tree

```
B+ diagnosed (port listening, health unreachable)
  ├─ Kill ALL miloco PIDs including supervisord → clean restart → likely works
  │   (the "full nuclear" approach from d-state-recovery.md)
  │
  └─ Kill stuck PIDs only, leave supervisord → auto-restart → MAY cascade
      ├─ Health OK + fresh inferences within 60s → recovery succeeded (lucky)
      └─ Health OK but CLI commands timeout → STOP. Container stop/start next.
          Do NOT retry CLI commands — each timeout degrades the container further.
```

**Preferred path for B+**: Kill ALL processes (including supervisord), clear socket, restart supervisord fresh. This avoids the auto-restart cascade entirely.

**If cascade already happening** (pct exec timing out): Go directly to container stop/start. Don't waste restart budget on CLI-level retries.

## Comparison with Other B+ Incidents
- `2026-07-08-cron-d-state-recovery.md`: B0 (port NOT listening), killed all 4 PIDs including supervisord, clean restart worked first try.
- `2026-07-08-cron-post-restart-pipeline-failure.md`: B+ → full nuclear restart → health OK but pipeline broken → progressive degradation. Budget exhausted.
- **This incident**: B+ → partial kill (supervisord alive) → auto-restart cascade → container stop/start → FULL RECOVERY. Container stop/start was the reliable fix after partial recovery failed.
