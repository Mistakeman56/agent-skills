# 2026-07-13 Cron — Scenario B− (Sl state, not Dl)

## Incident
Pre-run script timed out (`⚠️ 获取感知日志超时`). Agent diagnosed and recovered.

## Key Finding: B− with Sl state
- miloco.main PID 1588303: **Sl state** (not Dl), 6.5% MEM, 0:01 CPU time, started at 17:40 UTC
- supervisord PID 1584612: running since 17:38 UTC
- Port 1810: **NOT listening** (`ss -tlnp` showed no 1810)
- curl health: exit code 7 (connection refused)
- Service logs: stale from Jul 12 17:38 (old session)

**Contrast with classic B− (2026-07-12)**: The 2026-07-12 incident showed Dl state with 1-2s CPU time. This session showed Sl state with 35s CPU time over 8+ hours. Both are stuck init — the key signal is low CPU time relative to wall-clock uptime, not the specific process state.

## Recovery
Nuclear restart via pct exec (no lxc-attach needed):
1. `kill -9 <supervisord_PID> <miloco_main_PID>` — both killed cleanly
2. `rm -f /root/.openclaw/miloco/supervisor.sock`
3. `/usr/local/bin/supervisord -c /root/.openclaw/miloco/supervisord.conf`
4. Health check at 25s: `{"status":"ok"}`
5. Perception logs confirmed fresh inferences (timestamps matching current UTC time)

## Pre-run zombie cleanup
15 stuck miloco-cli processes killed from host shell before nuclear restart:
- `miloco-cli perceive logs` (R state, 23.2% CPU)
- `miloco-cli service start` (D state, 20.7% CPU)
- Various bash wrappers

## Perception data after recovery
- 北院: Night vision, white SUV + black sedan, no people
- 前院: Night vision, BBQ grill, tool cabinet, no people
- 三楼书房: Person lying on bed (趴在床上), room dark — normal nighttime rest

## Lessons
1. **B− is not limited to Dl state**: Sl state with low CPU time is equally valid. The diagnostic is "CPU time << wall-clock uptime", not a specific ps state.
2. **Host-level zombie cleanup before nuclear restart**: Killing pre-run zombies first reduces load and prevents interference with the restart.
3. **pct exec nuclear restart worked cleanly**: No need for lxc-attach fallback this time. The kill + socket clear + supervisord start sequence completed in one shot.
4. **Port binding took ~25s**: Health check at 25s succeeded. Consistent with documented 25-30s timing.
