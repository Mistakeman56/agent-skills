# 2026-07-10 Cron: Device Control Partial Backend

## Summary
Pre-run script timed out. Manually recovered via SSH → PVE → CT <ID>. Perception logs retrieved successfully, but device control failed.

## Timeline
- 08:59 Beijing: 三楼书房 occupied (two people)
- 09:02: One person sleeping in 三楼书房
- 09:16: Silver car arrived at 北院
- 09:26: 三楼书房 became empty
- 11:03: Agent ran — fetched logs, attempted device control

## Key Finding
- `miloco-cli perceive logs --since 2h --limit 10` succeeded — returned 10 entries
- `miloco-cli perceive logs --limit 10` returned stale June 24 data with `total_inferences: 0`
- `miloco-cli device control 888910528 switch 0` failed: `"cannot connect to Miloco backend at http://127.0.0.1:1810"`
- `miloco-cli perceive devices` hung (timeout 60s)
- `miloco-cli service status` not tested this session

## Analysis
The backend's perception endpoint (used by `perceive logs`) was functional and returned fresh data. However, the device control endpoint was unreachable. This suggests:
1. The perception module and device control module may use different internal connections
2. Device control requires a separate initialization step or connection path
3. The backend was partially operational — enough for monitoring but not for automation

## Implication
When running as a cron job for monitoring + automation:
1. Always attempt perception first to confirm monitoring works
2. If perception works but device control fails, report the partial state
3. Do NOT restart the backend just for device control — the monitoring value is intact
4. Consider whether the device control endpoint needs to be explicitly enabled or if it depends on a separate service

## Device Attempted
- 书房筒灯开关 (888910528): switch → 0 (off)
