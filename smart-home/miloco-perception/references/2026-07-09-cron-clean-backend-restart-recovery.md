# 2026-07-09 Cron: Clean Backend Restart Recovery

## Summary
Pre-run script timed out ("获取感知日志超时"). Manual diagnosis revealed the backend had just restarted (uptime_seconds: 20). Simple wait-and-retry (15s) resolved it.

## Timeline
- Pre-run script timed out
- `miloco-cli perceive logs --since 1h --limit 20` → `"cannot connect to Miloco backend at http://127.0.0.1:1810"`
- `miloco-cli service status` → `running: true, uptime_seconds: 20, pid: 140571` (supervisord IPC worked)
- Waited 15s, retried → success (20 fresh log entries, total_inferences: 1)

## Key Insight
`miloco-cli service status` communicated via supervisord's UNIX socket, not the backend HTTP API. It succeeded while `perceive logs` failed because the backend was still initializing after a restart. This made it possible to diagnose "backend initializing" without deeper investigation.

## Recovery Path
1. Check `service status` → if running with low uptime_seconds, backend is initializing
2. Wait 15-20s
3. Retry `perceive logs --since 1h --limit 20`
4. Verify `total_inferences >= 1` for fresh data

## Classification
Trivial recovery — no escalation needed. No service restart, no container restart, no PID kills.

## Perception Content
All areas empty (nighttime, ~00:07-01:02 Beijing time). One cat sighting in 前院 at 00:32. No human presence detected anywhere. Normal nighttime state.
