# 2026-07-12 Cron: Supervisord Alive + CLI Zombie Cleanup → Auto-Recovery

## Timeline
- ~11:36 UTC — Pre-run script timed out ("获取感知日志超时")
- ~11:46 — Agent SSH to PVE, `pct exec` full-path command timed out at 120s
- ~11:46 — `pct status 310`: container running
- ~11:46 — Host `ps aux --sort=-%cpu` revealed:
  - miloco.main at 123% CPU (PID 870030, Sl state — legitimate inference)
  - supervisord alive (PID 626148, running since 08:57, 10.2% CPU)
  - 5 stuck CLI zombie processes from pre-run pileup:
    - PID 876603: `bash -c miloco-cli perceive logs --limit 1` (R, 10.7%)
    - PID 876888: `bash -c miloco-cli service start` (R, 9.7%)
    - PID 877221: `bash -c miloco-cli perceive logs --limit 10` (R, 9.4%)
    - PID 877654: `bash -c miloco-cli perception log --limit 10` (R, 8.4%)
    - PID 877923: `python3 miloco-cli perceive logs --since 30m` (D, 7.8%)
  - Minecraft server at 13.2% CPU (normal)
- ~11:46 — Killed host-level PIDs: `kill -9 876603 876888 877221 877654 877923`
- ~11:46 — Post-cleanup: miloco.main restarted (new PID 879035, D state, 20.1% CPU, initializing)
- ~11:47 — Health OK: `{"status":"ok"}`
- ~11:47 — `perceive devices`: all 3 cameras online (前院, 三楼书房, 北院)
- ~11:47 — `perceive logs --since 5m`: 1 fresh entry (total_inferences: 1), front yard empty

## Key Pattern: Supervisord Alive + Zombie Cleanup

Unlike the earlier reference (2026-07-12-cron-pre-run-pileup-host-kill-recovery.md) where supervisord was killed along with zombies, in this session:

1. **supervisord was alive** (not killed — only CLI zombies were targeted)
2. **supervisord auto-restarted miloco.main** after the old one died
3. **No manual restart command needed** — cleanup alone was sufficient
4. **New miloco.main started in D state** (initializing, not stuck)

This is the **lighter and more common variant**: when supervisord is alive, killing only the CLI zombies is sufficient. Supervisord handles miloco.main lifecycle automatically.

## Diagnostic Sequence
1. Pre-run timeout → PVE reachable → `pct exec` full-path also times out
2. `pct status 310` confirms container running
3. Host `ps aux --sort=-%cpu` — check miloco.main state (Sl = healthy inference, Dl = stuck init)
4. Identify stuck CLI zombies (low CPU time despite long runtime = stuck)
5. Kill host-level PIDs (container processes visible in host ps are killable from host shell)
6. Verify: new miloco.main PID appears, health OK, total_inferences > 0

## Key Diagnostic: miloco.main State Matters

| STAT | CPU Time | Meaning |
|------|----------|---------|
| Sl | High (minutes) | Healthy, doing legitimate inference |
| Dl | Low (<5s) | Stuck during initialization |
| Ds | Low | Uninterruptible sleep, likely stuck I/O |
| Ss+ | Low | supervisord or CLI wrapper, check context |

In this session, old miloco.main was Sl at 123% CPU (healthy). New miloco.main was D state at 20.1% CPU with 0:00 time (initializing). Both are normal for their respective phases.

## Also Noted: `service status` FileNotFoundError

`miloco-cli service status` failed with `FileNotFoundError: supervisorctl` — the `supervisorctl` binary is not on the container's default PATH. This is a PATH issue, not a supervisord failure. Used `curl health` instead.

## Outcome
- Service fully recovered via zombie cleanup only
- No nuclear restart needed
- No container stop/start needed
- All 3 cameras online
- 1 fresh inference confirmed (pipeline warming up)
- Recovery took ~2 minutes total (including wait for fresh inference)

## Lessons
- When supervisord is alive, killing CLI zombies is sufficient — supervisord handles miloco.main restart
- `sl` STAT with high CPU = healthy inference, do NOT escalate
- `supervisorctl` not on PATH → fall back to `curl health` for health checks
- `--since 5m` with `total_inferences: 1` confirms fresh inference
- Stop probing after confirming health OK + total_inferences > 0
