# 2026-07-08 — Clean Scenario A Container Hang Recovery

## Timeline
- 18:32 UTC: cron pre-run script timeout (感知日志超时)
- PVE reachable: OK
- CT <ID> status: `running` (but unresponsive)
- `pct exec 310 -- ss -tlnp | grep 1810`: 15s timeout
- `lxc-attach -n 310 -- bash -c 'ss -tlnp | grep 1810'`: 15s timeout
- `lxc-attach -n 310 -- echo HELLO`: 15s timeout
- → **True container-level hang** (all 3 probe levels failed, including lxc-attach)
- `pct stop 310`: success
- `pct start 310 && sleep 10 && pct exec 310 -- echo PVE_OK`: success
- supervisord restart via pct exec: success
- Health check #1 (~15s after supervisord): exit code 7 (failed)
- Health check #2 (~30s after supervisord): `{"status":"ok"}` ✓
- `perceive logs --since 1h --limit 10`: success, 10 entries, `total_inferences: 1`

## Key Observation: Health Check Timing
The skill documents "up to 20s" for port binding after container restart. In this session, health was unreachable at 15s and succeeded at 30s. The actual startup time was ~25-30s, exceeding the documented 20s upper bound.

**Recommendation**: After container restart + supervisord start, check health at 20s AND 30s intervals. If both fail, escalate — but don't panic at 20s failure alone.

## Perception Results
- `total_inferences: 1` → post-restart snapshot (not transition event)
- 前院: user visible (赤裸上身, black shorts, white slippers, walking/ sitting with food)
- 北院: white SUV + black sedan parked, no people
- 三楼书房: no people, clothes/bags piled
- No action taken (snapshot interpretation, not transition)

## Recovery Path
Standard Scenario A path as documented — no deviations, no surprises. The existing 3-level probe correctly identified the hang level. Container stop/start + supervisord restart worked cleanly.
