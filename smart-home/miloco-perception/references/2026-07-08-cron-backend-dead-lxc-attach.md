# 2026-07-08 Cron: Backend Dead + pct exec Hang + lxc-attach Fallback

## Summary
Pre-run script timed out. Backend completely dead (no processes). `pct exec` hung but container was running. Recovered via `lxc-attach` + standalone `nohup` backend restart.

## Timeline
1. Pre-run script timeout: "获取感知日志超时"
2. PVE ping OK, SSH OK, `pct status 310` → "running"
3. `pct exec 310 -- echo hello` → hung (15s timeout)
4. `pct exec 310 -- uptime` → hung
5. Lock file blocking `pct stop`: `/run/lock/lxc/pve-config-310.lock`
6. `rm -f` cleared lock file → `pct stop` still failed ("CT <ID> already running")
7. Discovered `lxc-attach -n 310 -- echo hello` → worked instantly
8. `ps aux | grep miloco` → no miloco processes (backend completely dead)
9. `nohup /usr/local/bin/miloco-backend &` → port 1810 bound within 5s
10. `miloco-cli perceive logs` initially failed ("cannot connect to backend") — retried 10s later → success
11. Logs returned: 10 entries from 2026-06-24 (14 days old), `total_inferences: 1`

## Key Learnings

### lxc-attach as pct exec fallback
When `pct exec` hangs for simple commands but `pct status` shows running, the container is alive — the `pct exec` wrapper itself is the problem. `lxc-attach -n 310 --` bypasses the Proxmox wrapper and connects directly.

Evidence: `pct exec 310 -- echo hello` → 15s timeout, but `lxc-attach -n 310 -- echo hello` → instant success.

### Lock file issue
`/run/lock/lxc/pve-config-310.lock` can get stuck after `pct exec` hangs, blocking `pct stop`. Manual `rm -f` clears it.

### Backend dead without supervisord
No supervisord was running inside CT <ID>. The miloco-backend was completely absent. A standalone `nohup /usr/local/bin/miloco-backend &` worked — it bound port 1810 and served requests. This is faster than restarting supervisord but unmanaged.

### Transient CLI connection failure
`miloco-cli perceive logs` failed immediately after backend started (connection refused), but succeeded on retry ~10s later. The backend needs a few seconds to fully initialize after binding the port.

### Stale data (14 days old)
Logs returned from June 24 with `total_inferences: 1`. This suggests the perception pipeline either never started fresh inferences, or the backend had cached data from before the crash. The backend was down for an unknown period.

## Recovery Commands Used
```bash
# Clear lock file
sshpass -p "<PASSWORD>" ssh root@192.0.2.10 "rm -f /run/lock/lxc/pve-config-310.lock"

# lxc-attach fallback
lxc-attach -n 310 -- bash -c 'export PATH=/usr/local/bin:$PATH; <command>'

# Standalone backend restart
lxc-attach -n 310 -- bash -c 'nohup /usr/local/bin/miloco-backend > /var/log/miloco-backend.log 2>&1 &'

# Verify
lxc-attach -n 310 -- bash -c 'ss -tlnp | grep 1810'
lxc-attach -n 310 -- bash -c 'export PATH=/usr/local/bin:$PATH; miloco-cli perceive logs --limit 5'
```
