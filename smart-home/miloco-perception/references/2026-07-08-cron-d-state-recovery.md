# 2026-07-08 Cron: D-State Process + Service Start Zombie Recovery

## Timeline
- Pre-run script timed out fetching perception logs
- PVE reachable, CT <ID> `pct status` shows `running`
- `pct exec 310 -- echo HELLO` → success (container alive)
- `pct exec 310 -- ps aux` → success, revealed:
  - supervisord (PID 8183) — alive
  - `miloco-cli service start` (PID 34490/34502) — stuck, running 1+ minutes
  - miloco.main (PID 34504) — **D state** (uninterruptible sleep), running 1+ minutes
- Port 1810: NOT listening
- `curl http://127.0.0.1:1810/health` → exit code 7 (connection refused)

## Recovery
1. `kill -9 34490 34502 34504 8183` — killed all 4 PIDs via `pct exec`
2. Verified all miloco processes gone (`ps aux | grep miloco` → empty)
3. `rm -f /root/.openclaw/miloco/supervisor.sock; /usr/local/bin/supervisord -c /root/.openclaw/miloco/supervisord.conf`
4. Waited 10s → health OK
5. Waited 10s more → fresh perception logs returned

## Key Diagnostic: The Container Probe Technique

When `pct exec` hangs on miloco-related commands but `pct status` shows running, **don't assume the container is hung**. Try these simple commands first:

```bash
# Level 1: Basic exec test
pct exec 310 -- echo HELLO
# Level 2: Process inspection (always works if container is alive)
pct exec 310 -- ps aux
# Level 3: Port check
pct exec 310 -- ss -tlnp | grep 1810
```

If Level 1 succeeds but Level 3 hangs, the container is alive but something inside is blocking. `ps aux` (Level 2) is the key diagnostic — it almost always works and shows exactly what's stuck.

**This avoids unnecessary container stop/start** (Scenario A) when the container is actually fine but miloco processes are deadlocked.

## Scenario Classification
This is a **Scenario B0** (backend dead, port not listening) caused by miloco.main stuck in D state. The stuck `miloco-cli service start` was a zombie from a prior failed start attempt — it consumed resources but did nothing useful. The D-state miloco.main process was blocked on I/O and unrecoverable without a kill.
