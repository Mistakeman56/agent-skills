# 2026-07-12 Cron: Container-Internal Zombie Cleanup → Port Recovery

## Timeline
- 05:32 UTC — Pre-run script timed out ("获取感知日志超时")
- 05:32 — PVE reachable, load 11.02, CT <ID> running
- 05:32 — Host `ps aux --sort=-%cpu`: miloco.main at 147% CPU (PID 345010), plus 3 stuck bash/miloco-cli wrappers
- 05:32 — Container `ps aux` via `pct exec`: supervisord running (PID 69504, started 20:21), stuck `miloco-cli service start` (PIDs 152506/152509, started 21:38-21:40), fresh miloco.main (PID 152512, started 21:40, 1s CPU time)
- 05:32 — Port 1810: not listening. Health: exit code 7 (connection refused). Service status: failed
- 05:33 — Killed container-internal zombies: `pct exec 310 -- kill -9 152506 152509`
- 05:33 — Waited 15s for miloco.main to bind port
- 05:33 — Health: `{"status":"ok"}`. Port 1810 listening.
- 05:33 — `perceive logs --since 30m --limit 10`: 10 entries, `total_inferences: 1`
  - 三楼书房: person sleeping (night mode,侧卧床上)
  - 前院: dark cat walking, otherwise empty
  - 北院: white SUV + black sedan parked, no people

## Key Pattern: Container-Internal Kill + Wait (No Host Kill, No Restart)

Unlike the earlier 2026-07-12 session (pre-run-pileup-host-kill-recovery) where host-level `kill -9` was used, this session cleaned up from **inside the container** via `pct exec kill -9`. The miloco.main process was already running (started by supervisord) but couldn't bind port 1810 because the stuck CLI process was interfering. After killing the zombies, a 15-second wait was sufficient for the port to bind.

**When to use container-internal kill vs host-level kill**:
- **Container-internal** (via `pct exec kill -9`): Use when `pct exec` is responsive (not hanging). Cleaner — targets only the container's PID namespace without affecting host processes. Requires container-internal PIDs from `pct exec 310 -- ps aux`.
- **Host-level** (via `ssh root@PVE "kill -9 <host_PID>"`): Use when `pct exec` hangs but you can see stuck processes from host `ps aux`. The host shell's kill operates on the host PID namespace, which includes container processes (UID 100000).

## Host vs Container PID Mismatch

The host `ps aux --sort=-%cpu` showed miloco.main as PID 345010, but container `ps aux` showed it as PID 152512. These are different PID namespaces:
- Host PID 345010: the host-level view of the container's miloco.main process (visible in host ps as UID 100000)
- Container PID 152512: the container-internal PID (what `pct exec 310 -- ps aux` sees)

**Important**: The container-internal PID 152512 had only 1s CPU time despite being "started" at 21:40 (hours earlier). This indicates the process was freshly spawned by supervisord after the previous one was killed — not the long-running process shown in host ps. The host-level PID 345010 at 147% CPU is the actual long-running miloco.main doing inference.

## Diagnostic Sequence
1. Pre-run timeout → PVE reachable? → CT <ID> running?
2. Host `ps aux --sort=-%cpu` → identify miloco.main CPU + stuck processes
3. Container `ps aux` via `pct exec` → check supervisord state, fresh vs stuck miloco.main, zombie CLI processes
4. Port 1810 check (curl health or ss -tlnp)
5. If port not listening + stuck CLI present → kill zombies inside container (preferred) or on host (fallback)
6. Wait 15s → re-check health

## Outcome
- Service recovered without nuclear restart
- Pipeline produced 1 fresh inference (person sleeping in三楼书房, cat in前院)
- No device control actions needed (no home/away transitions)

## Lessons
- Container-internal `kill -9` via `pct exec` works when `pct exec` is responsive
- A fresh miloco.main (low CPU time) may need port to be cleared before binding
- 15-second wait after zombie cleanup is typically sufficient for port binding
- `total_inferences: 1` with recent timestamps confirms fresh inference despite stale-looking log entries
- Host-level miloco.main (high CPU, hours of runtime) and container-level miloco.main (low CPU, fresh PID) can coexist in different PID namespaces — don't assume they're the same process
