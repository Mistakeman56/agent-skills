# 2026-07-08 Cron: Zombie-Bound Port Recovery

## Timeline
- Pre-run script timed out fetching perception logs
- Diagnosed: PVE reachable, CT <ID> running, port 1810 LISTENING but health endpoint unreachable (curl exit code 7)
- `ps aux` showed: supervisord (PID 116206) + stuck `miloco-cli service start` (PID 1103386/1103391) + miloco.main (PID 1103394)
- Root cause: old miloco.main held the port socket but was dead/unresponsive — zombie-bound socket
- Recovery: PID-targeted nuclear restart (kill -9 all 4 PIDs → clear socket → supervisord start)
- Health restored within 10s. Fresh perception logs obtained with `total_inferences: 1`.

## Key Observations
- This is **Scenario B+**: port listening + health unreachable. Distinct from Scenario B (no listener), D (health OK), and E+ (port drops).
- The stuck `miloco-cli service start` process was a zombie from a previous failed attempt — it was running (S state, not R/D) but doing nothing useful.
- PID-targeted kills worked cleanly — no killall unreliability issues this time.
- `perceive logs --since 1h` returned fresh data from 23:34-23:38 Beijing time, confirming pipeline was healthy post-restart.

## Perception Content (post-recovery)
- 北院: nighttime, white SUV + black sedan parked, no activity
- 三楼书房: person lying on bed watching phone (bare-chested male, 23:34)
- 前院: empty, no people
- No home/away events detected — person is home resting
