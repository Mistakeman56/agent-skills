# Scenario C: Service Stuck in STARTING with D-State Python Processes

## Problem

When `miloco-cli service status` shows `"supervisor_state": "STARTING"` (not RUNNING, not STOPPED) and `ps aux` reveals multiple `miloco-cli` python3 processes in D (uninterruptible sleep) or R (running) states piled up inside the container, the supervisor is stuck in a startup loop — it keeps launching new processes that immediately block.

This is a distinct failure from Scenario A (zombie lxc-attach on PVE host) and Scenario B (lock contention). Here the processes are **inside** the container and the supervisor cannot complete initialization.

## Diagnosis

```bash
# 1. Check service status
pct exec 310 -- bash -c 'export PATH=/usr/local/bin:$PATH; miloco-cli service status'
# Shows: {"running": false, "managed": true, "supervisor_state": "STARTING"}

# 2. Check for stuck processes
pct exec 310 -- ps aux | grep miloco
# Multiple D-state or R-state python3 / miloco-cli entries = this scenario
```

Typical `ps aux` output in this state:
```
root  139770  0.3  14016  7744 ?  D  02:51  0:26 /usr/bin/python3 /usr/local/bin/miloco-cli perceive logs --limit 1
root  139773  0.3  14016  8272 ?  D  02:53  0:07 /usr/bin/python3 /usr/local/bin/miloco-cli perception status
root  139774  0.3  13884  8008 ?  R  02:53  0:03 /usr/bin/python3 /usr/local/bin/miloco-cli perception log --limit 5
root  139776  0.3  14016  8356 ?  D  02:54  0:00 /usr/bin/python3 /usr/local/bin/miloco-cli service start
```

Key: processes in `D` state (uninterruptible sleep) or `R` state (running but not completing) pile up as the supervisor keeps restarting them.

## Fix

```bash
# 1. Kill all python3 processes in the container
sshpass -p "<PASSWORD>" ssh -o StrictHostKeyChecking=no root@192.0.2.10 \
  "pct exec 310 -- killall -9 python3 2>/dev/null; echo done"
# Wait for service to register as STOPPED
sleep 3

# 2. Verify service is now STOPPED (not STARTING)
pct exec 310 -- bash -c 'export PATH=/usr/local/bin:$PATH; miloco-cli service status'
# Shows: {"running": false, "managed": true, "supervisor_state": "STOPPED"}

# 3. Start the service fresh
pct exec 310 -- bash -c 'export PATH=/usr/local/bin:$PATH; miloco-cli service start 2>&1'

# 4. Wait for initialization, then verify
sleep 20
pct exec 310 -- bash -c 'export PATH=/usr/local/bin:$PATH; miloco-cli service status'
# Shows: {"running": true, "managed": true, "pid": N, "uptime_seconds": N}
```

## ⚠️ Pitfall: `pkill -9 -f miloco-cli` Kills the SSH Session

The `-f` flag matches the full command line, which includes the `miloco-cli` string in the `pct exec 310 -- miloco-cli ...` command itself. This sends SIGKILL to the parent shell, terminating your SSH connection (exit code 137).

**Always use `killall -9 python3` instead** — it targets only the python3 processes without matching the SSH command line.

## Distinction from Other Scenarios

| Scenario | Where are stuck processes? | supervisor_state | Fix |
|----------|---------------------------|-----------------|-----|
| A (zombie lxc-attach) | PVE host (outside container) | N/A (host-level) | Kill on host + optional container restart |
| B (lock contention) | PVE host (lock files) | N/A (host-level) | Kill lock holder |
| **C (D-state startup loop)** | **Inside container** | **STARTING** | **killall python3 in container + service start** |
| B− (stuck init) | Inside container (single process) | RUNNING | Restart service |

## Recovery Log Example (2026-07-15)

```
02:51 - Processes start piling up in D/R state
02:54 - ps aux shows 8+ miloco-cli processes in D/R state
02:54 - killall -9 python3 → all processes killed
02:54 - supervisor_state transitions: STARTING → STOPPED
02:54 - miloco-cli service start → service starts fresh
02:55 - Perception engine started, cameras connected, Uvicorn running
02:55 - GET /health 200 — service fully operational
```
