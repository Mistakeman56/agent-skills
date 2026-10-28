# 2026-07-09 Cron — Repeated Warm-Then-Die (Multiple Cycles)

## Scenario
- Pre-run script timed out (perception logs unreachable)
- PVE reachable, CT <ID> running, but pct exec hanging on non-trivial commands
- lxc-attach worked: supervisord + miloco.main alive, but port 1810 unbound
- Service status showed uptime_seconds: 17 → backend still initializing (NOT dead)

## Key New Finding: Warm-Then-Die Repeated Twice

### Cycle 1
1. Waited 15s for initialization → health OK, port 1810 bound
2. `perceive logs --since 30m --limit 10 --pretty` → **SUCCESS** — 10 entries, total_inferences: 1, fresh timestamps (07:14–07:32 UTC)
3. 20s later, `perceive logs --since 10m --limit 3 --pretty` → **TIMEOUT** (30s)
4. `miloco-cli service status` → **TIMEOUT** (20s)
5. `curl health` via lxc-attach → **TIMEOUT** (20s)
6. Container degraded: pct exec and lxc-attach pgrep both timing out

### Recovery 1 (Container stop/start)
1. Container stopped, supervisord started directly
2. Health OK at 30s, service status: running, uptime_seconds: 34
3. `perceive logs --since 3m --limit 5 --pretty` → **SUCCESS** — 2 entries, total_inferences: 1

### Cycle 2
4. 20s later, `perceive logs --since 5m --limit 3 --pretty` → **TIMEOUT** (40s)
5. Container degraded again

### Recovery 2 (Container stop/start — purely for container health)
1. Container stopped/started again
2. supervisord started, health OK at 30s
3. `perceive logs --since 3m --limit 5 --pretty` → **SUCCESS** — 3 entries, total_inferences: 2
4. 20s later, `perceive logs --since 5m --limit 3 --pretty` → **SUCCESS** — 3 entries, total_inferences: 2 (stable!)

## What's Different from Previous Session

| Previous (2026-07-09 reference) | This Session |
|---|---|
| True container hang (pct exec + lxc-attach both hanging) | Partial hang: pct exec hung, lxc-attach worked |
| Backend dead, processes stuck | Backend alive but initializing (uptime_seconds: 17) |
| 1 cycle of warm-then-die | 2 consecutive cycles of warm-then-die |
| Didn't retry after first collapse | Eventually stabilized after 2nd container recovery |

## Critical Insight: Service Status False Positive

`miloco-cli service status` returned `running: true, uptime_seconds: 17` when the backend was still initializing. The health endpoint was not yet accepting connections (exit code 7). **Always verify with `curl health` before trusting service status — and if health fails, wait and retry (up to 30s) before escalating.**

## Revised Restart Budget Interpretation

The skill says "container stop/start done purely to restore basic container functionality after degradation does NOT count against the budget." However, when the pipeline collapses AFTER a container stop/start and the container degrades again, the NEXT container stop/start IS a pipeline restart attempt because you're restarting to fix the pipeline, not just container health.

In this session:
- Recovery 1 (container stop/start to restore degraded container) → counts as restart #1 (pipeline collapsed after)
- Recovery 2 (container stop/start after pipeline collapsed again) → counts as restart #2
- Pipeline stabilized after Recovery 2 → success, but if it hadn't, this would have exhausted the budget

**Rule**: If you do a container stop/start to fix degradation, and the pipeline subsequently collapses, the next container stop/start counts as a pipeline restart attempt. Track collapses after each recovery, not just the recovery itself.

## Recovery Pattern
- 2 container stop/starts total
- Pipeline stabilized after 2nd recovery with total_inferences: 2
- All areas: no people/pets detected (snapshot, not transition event)
- No device control actions triggered
