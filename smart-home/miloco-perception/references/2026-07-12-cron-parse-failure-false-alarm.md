# 2026-07-12 Cron — "⚠️ 无法解析感知日志:" False Alarm

## Summary
Pre-run script returned "⚠️ 无法解析感知日志:" but the service was actually healthy. The failure was caused by pre-run zombie processes accumulating on the PVE host, not a backend issue. After killing host-level zombies, perception logs retrieved successfully on first attempt.

## Initial State
- PVE reachable, host load moderate
- miloco.main at 19% CPU, Sl state (healthy, actively inferring)
- supervisord running (PID 1101149, uptime since Jul06)
- Stuck pre-run zombies on PVE host:
  - `bash -c miloco-cli service start` (PID 2132049) — 11.8% CPU, S state
  - `miloco-cli service start` (PID 2132368) — 2.2% CPU, D state
  - SSH wrapper (PID 2132016) — stuck

## Diagnosis
The "⚠️ 无法解析感知日志:" string does NOT always indicate a real backend failure. In this case:
- Service was healthy (health OK, miloco.main inferring at 19% CPU)
- Pre-run script spawned `miloco-cli service start` processes that got stuck
- The parse failure was likely the pre-run script timing out or receiving partial/malformed output from its own zombie processes

**Key distinction from 2026-07-10**: The 2026-07-10 case was a genuine B/B+ hybrid (port unbound, D-state miloco.main, real failure). This session was a false alarm — service healthy, just pre-run pileup.

## Recovery
Host-level zombie cleanup only (no nuclear restart needed):
1. `kill -9 2132049 2132368 2132016` — killed stuck pre-run processes on PVE host
2. `pct exec 310 -- miloco-cli perceive logs --since 30m --limit 5 --pretty` → success on first try

## Post-Recovery Verification
- Health: `{"status":"ok"}`
- All 3 cameras online
- Fresh inference: total_inferences: 1
- Latest data: person lying on bed in study watching phone (23:32 Beijing)

## Key Observations
1. **"⚠️ 无法解析感知日志:" is NOT exclusively a failure indicator**: When accompanied by healthy host-level diagnostics (miloco.main in Sl state, moderate CPU), it's most likely a pre-run script issue, not a backend problem.
2. **Host-level zombie cleanup is sufficient**: No need for nuclear restart or container stop/start when the service is demonstrably healthy.
3. **False Alarm Shortcut applies**: miloco.main at 19% CPU in Sl state = healthy. The 7-step diagnostic path can be shortened: skip to zombie cleanup + direct log retrieval after confirming service health.
4. **`miloco-cli service status` fails with FileNotFoundError**: `supervisorctl` not on default PATH inside `pct exec`. Use `curl health` as fallback. Already documented in skill.

## Perception Snapshot (post-recovery)
- 三楼书房: person lying on bed watching phone (user)
- 北院: 2 cars parked, no people
- 前院: no people

No home/away transition. Person was in study since at least 23:10 (making bed), moved to lying down by 23:32. Still present at 23:39.
