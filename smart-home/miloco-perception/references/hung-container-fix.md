# Hung CT <ID> Container — Diagnosis & Fix

**Date discovered**: 2026-07-13
**Symptom**: CT <ID> shows `status: running` from PVE but all `pct exec` commands time out (30s+).
**Root cause**: Stuck `lxc-attach` processes inside CT <ID> blocking new exec commands and preventing clean shutdown/reboot.

## Diagnosis

```bash
# Check for stuck lxc-attach processes
sshpass -p "<PASSWORD>" ssh -o StrictHostKeyChecking=no root@192.0.2.10 \
  "ps aux | grep -E 'lxc-attach.*310' | grep -v grep"
```

Look for processes like:
- `lxc-attach -n 310 -- bash -c miloco-cli perceive logs ...`
- `lxc-attach -n 310 -- bash -c miloco-cli service start ...`

These are usually from previous monitoring attempts that didn't complete.

## Fix Sequence

```bash
# 1. Kill all stuck lxc-attach processes (use PIDs from diagnosis)
sshpass -p "<PASSWORD>" ssh -o StrictHostKeyChecking=no root@192.0.2.10 \
  "kill -9 <PID1> <PID2> ..."

# 2. Wait 30s for reboot to complete (reboot may already be in progress)
sleep 30

# 3. Verify CT <ID> is back
sshpass -p "<PASSWORD>" ssh -o StrictHostKeyChecking=no root@192.0.2.10 \
  "pct status 310"

# 4. Start miloco service
sshpass -p "<PASSWORD>" ssh -o StrictHostKeyChecking=no root@192.0.2.10 \
  "pct exec 310 -- bash -c 'export PATH=/usr/local/bin:$PATH; miloco-cli service start 2>&1'"

# 5. Verify cameras online
sshpass -p "<PASSWORD>" ssh -o StrictHostKeyChecking=no root@192.0.2.10 \
  "pct exec 310 -- bash -c 'export PATH=/usr/local/bin:$PATH; miloco-cli perceive devices 2>&1'"
```

## Pitfalls

- **Do NOT run `pct stop` or `pct reboot` while stuck processes exist** — it will hang waiting for the lock file (`/run/lock/lxc/pve-config-310.lock`). Kill processes first.
- The reboot command itself may already be running (check `ps aux | grep pct`). If so, just wait and kill stuck processes to unblock it.
- After reboot, the miloco service needs to be manually started — it doesn't auto-start from supervisord immediately.
- Perception logs may be stale (days/weeks old) if the engine was down. New events will start appearing after the service is restarted.
