# 2026-07-08 Cron: lxc-attach Probe + Hidden Zombie Process Recovery

## Timeline
- Pre-run script timed out fetching perception logs
- PVE reachable, CT <ID> `pct status` shows `running`
- `pct exec 310 -- echo HELLO` → **timed out** (20s)
- `lxc-attach -n 310 -- echo HELLO` → success (container alive)
- `lxc-attach -n 310 -- ps aux` → **timed out** (15s)
- `lxc-attach -n 310 -- curl http://127.0.0.1:1810/health` → exit code 7 (connection refused)
- `lxc-attach -n 310 -- pgrep -la python3` → showed 1 process: miloco.main (PID 58433)
- `lxc-attach -n 310 -- pgrep -la supervisord` → showed supervisord (PID 324)

## Recovery
1. Killed initial PIDs: `kill -9 324 58433`
2. Re-checked: `ps aux | grep miloco` → **2 additional zombie processes revealed**:
   - PID 58417: `bash -c miloco-cli service start 2>&1` (S state, running since 04:12)
   - PID 58420: `/usr/bin/python3 /usr/local/bin/miloco-cli service start` (S state, running since 04:13)
3. Killed zombies: `kill -9 58417 58420`
4. Verified all gone: `pgrep -la python3` → `NO_PYTHON`
5. Cleared socket + restarted supervisord:
   ```bash
   rm -f /root/.openclaw/miloco/supervisor.sock
   /usr/local/bin/supervisord -c /root/.openclaw/miloco/supervisord.conf
   ```
6. Waited 10s → health OK (`{"status":"ok"}`)
7. Waited 10s more → `perceive logs --since 30m` returned fresh data (`total_inferences: 1`)

## Key Observations

### pct exec hangs completely, lxc-attach works
In this incident, `pct exec` timed out for ALL commands (echo, ps aux, ss), but `lxc-attach` worked for basic commands. The probe technique must use lxc-attach when pct exec is completely unresponsive.

### Hidden zombie processes
The initial `pgrep -la python3` only showed 1 process (miloco.main). After killing miloco.main, `ps aux | grep miloco` revealed 2 additional stuck `miloco-cli service start` zombie processes that were not visible in the initial pgrep. These zombies had been running for ~30+ minutes and were consuming resources.

**Why they were hidden**: The zombies were `bash` and `python3` processes, but `pgrep -la python3` may not have matched them if they were in a different process group or if the pgrep filter didn't catch them. The `ps aux | grep miloco` command was more reliable at finding all miloco-related processes.

### Clean recovery on first try
After killing ALL processes (including hidden zombies) and restarting supervisord, the service recovered cleanly with health OK and fresh perception logs on the first attempt. The key was being thorough in the kill step — if the hidden zombies had been left alive, they might have interfered with the fresh supervisord start.

## Scenario Classification
This is a **Scenario B+ variant**: port not listening (exit code 7 on curl), but the root cause was miloco.main in a dead state with hidden zombie CLI processes. The recovery followed the B+ nuclear restart pattern but required the lxc-attach fallback for the probe and an extra kill round for hidden zombies.

## Comparison with Other Incidents
- `2026-07-08-cron-d-state-recovery.md`: Similar B0 recovery, but pct exec worked for echo/ps. Used PID-targeted kill, clean recovery.
- `2026-07-08-cron-zombie-bound-port.md`: B+ with port LISTENING. Similar PID-targeted kill approach.
- `2026-07-08-cron-b-plus-to-a-cascade.md`: B+ with partial kill (supervisord left alive) → cascade. This incident killed ALL processes including supervisord, avoiding the cascade.
- **This incident**: pct exec completely hangs → lxc-attach fallback → hidden zombie discovery → thorough kill → clean recovery.
