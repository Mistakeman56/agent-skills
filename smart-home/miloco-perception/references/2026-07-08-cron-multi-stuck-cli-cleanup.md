# 2026-07-08 Cron: Multiple Stuck miloco-cli Processes + Extreme Load

## Incident Summary

Pre-run script timed out. Diagnosis revealed multiple `miloco-cli` processes stuck in R (Running) state:
- `miloco-cli perceive logs --limit 1` (multiple)
- `miloco-cli perception status` (multiple)
- `miloco-cli service start` (multiple)

Container load: **9-12** (extremely high for a small container).

## Key Observations

1. **PVE ping OK, SSH OK, pct exec hangs**: PVE at 192.0.2.10 was pingable and SSH connected, but `pct exec` commands timed out after 30-60s.

2. **Process pileup was visible via `ps aux`**: Running `pct exec 310 -- ps aux` showed 5+ miloco processes, all consuming CPU. Load average was 9-12.

3. **`pkill -9 miloco-cli` temporarily worked**: After killing stuck processes, `miloco-cli perceive logs --limit 5` returned data. But the container became unresponsive again within seconds (pct exec commands started timing out).

4. **Perception logs 2 weeks stale**: Retrieved logs were from June 24, 2026 (2 weeks prior). The perception pipeline had been broken for a long time. `total_inferences: 0` confirmed no fresh inference.

5. **Container degraded after cleanup**: Even after successfully killing processes and retrieving logs, subsequent `pct exec` commands (uptime, service status, service restart) all timed out. The container was under extreme load.

## What Happened

```
Timeline:
- 08:27-08:31: Multiple miloco-cli processes pile up (stuck in R state)
- 08:31: Agent SSHes in, runs ps aux → sees 5+ miloco processes, load 11.58
- 08:31: Agent runs pkill -9 miloco-cli → processes killed
- 08:31: Agent runs perceive logs --limit 5 → succeeds, returns June 24 data
- 08:31: Container load still 9+ → subsequent pct exec commands timeout
- Agent reports stale logs + high load to user
```

## Diagnosis Pattern

When you see this combination:
- Container running (`pct status` = running)
- `pct exec` commands timeout (30-60s)
- `ps aux` shows multiple `miloco-cli perceive logs` and/or `miloco-cli perception status` in R state
- Container load > 5

→ It's a **miloco-cli process pileup** causing CPU starvation. The CLI processes are stuck in infinite loops or I/O waits, consuming all available CPU.

## Recovery

1. Kill stuck processes: `pkill -9 miloco-cli`
2. Verify killed: `ps aux | grep miloco | grep -v grep`
3. If container is still responsive, check logs: `miloco-cli perceive logs --limit 5`
4. If container degrades after cleanup (load stays high), it may need container stop/start

## Why It Happened

The miloco-cli perception subsystem seems to have a bug where multiple concurrent `perceive logs` or `perception status` calls can hang indefinitely. The supervisord may have been restarting failed CLI processes, creating a pileup.

The 2-week stale logs suggest the perception pipeline has been fundamentally broken — likely an upstream issue (camera HEVC decoder, model API, or inference pipeline). The stuck CLI processes are a symptom of the broken pipeline, not the root cause.

## Relation to Existing Scenarios

This is a variant of **Scenario D** (stuck processes) combined with **Scenario E** (stale pipeline). The key difference from standard Scenario D:
- Standard D: typically one stuck process type
- This incident: multiple process types stuck simultaneously
- Container load much higher (9-12 vs typical 3-5)
- Container degrades rapidly after cleanup

## Lesson

When miloco-cli processes pile up with extreme load (>5), the container may be too degraded to recover via CLI commands alone. Consider container stop/start as the primary recovery path rather than trying to clean up processes individually.
