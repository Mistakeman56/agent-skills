# 2026-07-15 Cron: Supervisord Not Auto-Starting After Container Reboot

## Scenario
Pre-run script timed out getting perception logs. CT <ID> was reachable (ping OK, SSH OK) but `miloco-cli perceive logs` hung.

## Diagnosis Path
1. `ping 192.0.2.10` → OK (0.038ms)
2. `ssh echo OK` → OK
3. `pct status 310` → running
4. `pct exec echo hello` → OK
5. `ss -tlnp | grep 1810` → empty (backend not listening)
6. `supervisorctl status` → "http://localhost:9001 refused connection"

## Root Cause
After previous container issues, supervisord was not running. The miloco backend process was alive but the port was not bound (backend stuck or in zombie state).

## Recovery
1. `pct stop 310 && sleep 3 && pct start 310` (full container restart)
2. Wait 60s for container boot
3. `supervisord -c /root/.openclaw/miloco/supervisord.conf` (manual supervisord start)
4. `miloco-cli service start` (starts backend)
5. Wait 20s for port binding
6. `ss -tlnp | grep 1810` → port 1810 now listening
7. `miloco-cli perceive logs --since 3h --limit 10` → success

## Key Learning
- Supervisord does NOT auto-start after `pct stop/start`
- `miloco-cli service start` handles supervisord internally — prefer it over manual supervisord startup
- After restart, backend needs ~20-25s to bind port 1810
- `echo hello` being fast proves container is alive; port not listening means backend needs manual start

## Log Analysis
Latest perception logs from 2026-07-14 18:11 UTC (02:11 Beijing time):
- All areas: no people, no pets, nighttime monitoring
- Normal nighttime status — no action needed
