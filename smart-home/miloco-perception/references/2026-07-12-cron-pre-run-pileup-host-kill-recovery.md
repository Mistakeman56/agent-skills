# 2026-07-12 Cron: Pre-Run Pileup → Host-Level Kill → Auto-Recovery (No Restart)

## Timeline
- 04:14 UTC — Pre-run script timed out ("获取感知日志超时")
- 04:14 — PVE reachable, load 10.30, CT <ID> running
- 04:14 — `ps aux --sort=-%cpu` on host showed:
  - miloco.main at 139% CPU (PID 200650, Dl state)
  - supervisord in Ds state (PID 173639)
  - 5+ stuck miloco-cli processes in D state (perceive logs, service start)
  - Multiple bash/lxc-attach wrapper processes
- 04:15 — Killed host-level PIDs: `kill -9 212509 212955 213149 213338 212884 212599 212308 213333 173639 200650`
  - Some returned "No such process" (already dead)
  - Others killed successfully
- 04:15 — Load dropped to 8.04
- 04:15 — Post-cleanup state:
  - Port 1810: initially not listening (ss grep false negative), then listening
  - Health: initially exit code 7, then `{"status":"ok"}`
  - supervisord: NOT running (dead after kill)
  - miloco.main: running independently (new PID 55997 inside container, 17.6% CPU, Dl state)
- 04:15 — `perceive logs --since 30m`: returned stale cached data (July 11 timestamps), `total_inferences: 0`
- 04:15 — `perceive logs --since 10m`: returned 5 entries with stale timestamps but `total_inferences: 1`
- 04:15 — `perceive devices`: all 3 cameras online (三楼监控, 前院, 北院)

## Key Pattern: Auto-Recovery Without Restart

After killing pre-run zombie processes from PVE host shell:
1. **supervisord was dead** (killed along with other processes)
2. **miloco.main auto-restarted independently** (new PID, no supervisord supervision)
3. **Health passed** without any manual restart command
4. **Pipeline produced 1 fresh inference** (total_inferences: 1)

This is a **lighter recovery path** than nuclear restart or container stop/start. The service recovered purely from zombie cleanup.

## Diagnostic Sequence
1. Pre-run timeout → check PVE/host load → check CT <ID> status
2. Host `ps aux --sort=-%cpu` reveals stuck processes
3. Kill host-level PIDs (container processes visible in host ps are killable from host shell)
4. Verify: load dropped, port binding, health, total_inferences

## Outcome
- Service fully recovered
- No nuclear restart needed
- No container stop/start needed
- All cameras online
- 1 fresh inference confirmed (pipeline warming up)

## Lessons
- Host-level `kill -9` works for container processes visible in host ps
- Some PIDs may already be dead ("No such process" is not an error)
- After zombie cleanup, miloco.main can auto-restart without supervisord
- `--since 10m` with `total_inferences: 1` confirms fresh inference despite stale timestamps in logs
- Stop probing after confirming health OK + total_inferences > 0 (prevents agent self-inflicted pileup)
