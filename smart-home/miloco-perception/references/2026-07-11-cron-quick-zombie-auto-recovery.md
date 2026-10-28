# 2026-07-11 Quick Zombie Auto-Recovery

## Timeline
- 15:16 CST — Pre-run script timed out; PVE load 11.79
- 15:17 — Killed 4 host-level pre-run zombies (miloco-cli service start × 1, perceive logs × 3)
- 15:17 — Container echo OK, pgrep revealed zombie miloco.main (PID 254371) + running supervisord (PID 234317)
- 15:17 — supervisorctl confirmed miloco-backend RUNNING (pid 257628, uptime 0:00:08)
- 15:18 — Health check OK after 15s wait
- 15:21 — Fresh perception logs confirmed (total_inferences: 1, 三楼书房 scene description)

## Key Pattern
This was the fastest recovery observed — **zero manual intervention on the container**. The sequence was:
1. Kill host-level pre-run zombies → load dropped
2. Container's supervisord had already auto-restarted miloco.main (zombie → fresh process)
3. Just waited for backend initialization, then verified

Total time from diagnosis to working logs: ~5 minutes (including waits).

## Why This Worked
- Supervisord was alive and healthy (not stuck, not zombie)
- The only issue was miloco.main as zombie — supervisord detected it and auto-restarted
- Host-level zombie cleanup reduced load from 11.79, making subsequent commands responsive

## Contrast with Nuclear Restart Path
- Nuclear restart: kill processes → clear socket → restart supervisord (takes 30-40s)
- Supervisord auto-recovery: just wait (takes 10-20s for backend init)
- Auto-recovery is always faster when supervisord is alive

## Diagnostic Quick-Check
```
lxc-attach -n 310 -- pgrep -la python3
# If only zombie miloco.main + running supervisord → auto-recovery likely
# Check supervisorctl status to confirm
lxc-attach -n 310 -- /usr/local/bin/supervisorctl -c /root/.openclaw/miloco/supervisord.conf status
# If RUNNING with low uptime → backend just restarted, wait 15s
```
