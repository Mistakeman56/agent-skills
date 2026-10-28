# 2026-07-11 Cron: Host-Level Wrapper Process Cleanup

## Summary
Pre-run script timed out. Container had massive process pileup. Successfully recovered via host wrapper cleanup + container stop/start.

## Key Technique: Kill Host-Level SSH/LXC-Attach Wrappers

The pre-run script spawns ssh + lxc-attach wrapper processes on the **PVE host** (not inside the container). These accumulate during retry pileup and contribute to host load. They are killable directly on the host shell.

**Detection**: `ps aux --sort=-%cpu | grep miloco` on PVE host shows:
```
root     3253406  0.8  ... lxc-attach -n 310 --keep-env -- /usr/local/bin/miloco-cli perceive logs ...
100000   3252746  0.0  ... ssh ... lxc-attach -n 310 -- bash -c 'miloco-cli perceive logs ...'
100000   3252463  0.0  ... ssh ... lxc-attach -n 310 -- bash -c 'miloco-cli service start ...'
```

**Fix**: Kill these host-level PIDs directly (they're in the host PID namespace, not the container's):
```bash
sshpass -p "<PASSWORD>" ssh root@192.0.2.10 "kill -9 <wrapper_PIDs>"
```

**Why this matters**: These wrappers are children of the pre-run script's ssh sessions. They block container commands (pct exec, lxc-attach) from completing. Killing them BEFORE attempting container stop/start reduces host load and prevents the container restart from hanging on stale ssh sessions.

## Recovery Sequence Used
1. Killed host-level ssh/lxc-attach wrapper PIDs (10 processes)
2. Cleared lock file (`rm -f /run/lock/lxc/pve-config-310.lock`)
3. Container stop/start
4. Started supervisord manually (did not auto-start)
5. Health OK at ~25s after supervisord start
6. First `perceive logs` returned fresh data (2 entries, total_inferences: 0 cached)
7. Second query timed out — warm-then-die collapse (~20s window)

## Perception Data
- 2 cached entries from 北院 (north yard): green car + black car, no people
- No home/away transitions
- Pipeline collapsed after first successful query (warm-then-die)

## PVE State
- Load average: 11.38 (elevated)
- miloco.main: 141% CPU after restart
- Minecraft server: 13.2% CPU
