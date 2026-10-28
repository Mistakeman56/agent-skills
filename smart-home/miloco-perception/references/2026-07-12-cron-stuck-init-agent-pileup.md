# 2026-07-12 Cron: Stuck Initialization + Agent Self-Inflicted Pileup

## Timeline

- **03:54 UTC** — Pre-run script times out fetching perception logs
- **03:54** — PVE load 12.81; miloco.main at 138% CPU (host ps); supervisord running
- **03:54** — Multiple stuck miloco-cli processes from pre-run pileup visible on host
- **03:54** — Container responsive: `pct exec 310 -- echo HELLO` works
- **03:54** — Port 1810 NOT listening (`ss -tlnp | grep 1810` empty)
- **03:54** — `curl http://127.0.0.1:1810/health` returns exit code 7 (connection refused)
- **03:54** — Service logs show backend started at 19:54:29 UTC but never completed initialization (no "Application startup complete" or "Uvicorn running" messages)
- **03:54** — miloco.main PID 26492: Dl state, 1s CPU time despite 8 hours uptime = stuck during init
- **03:54** — Nuclear restart: `kill -9 <supervisord> <miloco.main>` → clear socket → restart supervisord
- **03:55** — Health OK at 25s after supervisord restart; miloco.main at 54% CPU
- **03:55** — First `perceive logs --since 30m` returned stale cache (total_inferences: 0)
- **03:56** — Second query `--since 5m` returned 2 fresh inferences (total_inferences: 2) ✅
- **03:56–03:59** — Agent continued probing → miloco-cli queries piled up → container degraded
- **03:57** — Container partial hang: echo OK but ps aux/pgrep timeout
- **03:57** — Host ps shows stuck miloco-cli (D state, 24% CPU) + curl (R state, 11% CPU)
- **03:57** — Killed stuck processes from PVE host shell: `kill -9 <host_PIDs>` ✅
- **03:58–03:59** — Agent probed again → another pileup → killed again
- **03:59** — Stopped probing; pipeline confirmed working (fresh inferences produced)

## Root Cause: Stuck Initialization

The backend process (miloco.main) started but got stuck during manager initialization. Service logs show:
```
19:54:29 - Starting Miloco backend...
19:54:29 - Database initialization completed
19:54:29 - Manager initialization started
19:54:29 - Retrieved 4 kv as dict
19:54:29 - init i18n, zh-Hans
```
Then nothing — no "Application startup complete", no "Uvicorn running". The process sat in Dl state for 8 hours with only 1s of CPU time. This is distinct from Scenario B (port unbound with alive processes) because the process never finished initializing.

## New Pattern: Agent Self-Inflicted Diagnostic Pileup

After successful recovery, the agent's own diagnostic commands via `pct exec` piled up as stuck processes:

| PID | Command | State | CPU |
|-----|---------|-------|-----|
| 180772 | `miloco-cli perceive logs --since 5m --limit 10` | R | 25% |
| 181438 | `miloco-cli perceive logs --since 5m --limit 5` | D | 24% |
| 181711 | `curl -s --connect-timeout 5 http://127.0.0.1:1810/health` | R | 11% |
| 181399 | `lxc-attach -- miloco-cli perceive logs` | S | — |

This is distinct from pre-run retry pileup because:
- Pre-run pileup: spawned by the pre-run script before the agent runs
- Agent pileup: spawned by the agent's own diagnostic attempts after recovery

**Lesson**: After confirming health OK + fresh inferences, STOP PROBING. Each additional miloco-cli query via pct exec risks pileup when miloco.main is at high CPU.

## Host-Level Kill of Container Processes

Container processes visible from PVE host `ps aux` (UID 100000) CAN be killed from the PVE host shell:
```bash
# This WORKS (host shell kill operates in host PID namespace):
ssh root@192.0.2.10 "kill -9 <host_PID>"

# This DOES NOT WORK (pct exec runs inside container, PID namespace mismatch):
pct exec 310 -- kill -9 <host_PID>
```

The existing pitfall about "Host-level PIDs don't work with pct exec kill" is correct but incomplete. Host-level kill FROM THE HOST SHELL works because the processes are visible in the host PID namespace.

## Fresh Perception Data

After recovery, 2 fresh inferences confirmed:
- 北院: Three vehicles parked (white SUV + two dark sedans), no people
- Pipeline producing fresh data (total_inferences: 2)

Previous cached data (from ~8h earlier) showed someone sleeping in 三楼书房.
