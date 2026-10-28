# 2026-07-09 Cron: Service Restart Fail + lxc-attach Recovery

## Timeline
- Pre-run script timed out fetching perception logs
- PVE reachable, CT <ID> `pct status` shows `running`
- `pct exec 310 -- echo PVE_OK` → success (partial pct exec hang confirmed)
- `pct exec 310 -- bash -c 'ss -tlnp | grep 1810'` → timeout (subprocess hangs)
- `lxc-attach -n 310 -- pgrep -la python3` → PID 10030 (miloco.main alive)
- `lxc-attach -n 310 -- ss -tlnp | grep 1810` → no output (port 1810 unbound)
- `lxc-attach -n 310 -- pgrep -la supervisord` → PID 342 (supervisord alive)

## Soft Restart Attempt
- `lxc-attach -n 310 -- miloco-cli service restart` → `{"error": "supervisorctl restart failed: ""}`
- **Error message is empty** — supervisord's control interface is broken even though supervisord process is alive

## Recovery (PID-targeted via lxc-attach)
1. `lxc-attach -n 310 -- kill -9 10030 342` — killed miloco.main + supervisord
2. `lxc-attach -n 310 -- pgrep -la miloco` → revealed hidden zombie: `miloco-cli service start` (PID 10021)
3. `lxc-attach -n 310 -- kill -9 10021` — killed zombie
4. `lxc-attach -n 310 -- pgrep -la miloco` → empty (all cleared)
5. `lxc-attach -n 310 -- bash -c 'rm -f /root/.openclaw/miloco/supervisor.sock; /usr/local/bin/supervisord -c /root/.openclaw/miloco/supervisord.conf'`
6. Wait 12s → `curl http://127.0.0.1:1810/health` → `{"status":"ok"}`
7. `miloco-cli perceive logs --since 30m --limit 10` → fresh logs returned

## Key Learning: `supervisorctl restart failed: ""` Error
The `miloco-cli service restart` command returns `{"error": "supervisorctl restart failed: ""}` (note the empty error string) when:
- supervisord process is alive but its control interface is broken
- miloco.main may be alive but port 1810 unbound

This is NOT a "service not running" error — supervisord IS running but can't respond to control commands. The fix is PID-targeted nuclear restart, NOT retrying `service restart`.

**Diagnostic sequence when this error occurs:**
1. `pgrep -la supervisord` — if supervisord exists → control interface broken
2. `pgrep -la python3` — find miloco.main PID
3. Kill both by PID → clear socket → restart supervisord

## Scenario Classification
Variant of **Scenario B** (port not listening, processes alive) where supervisord's control interface is broken. The `supervisorctl restart failed: ""` error is a reliable signal that soft restart won't work — go directly to PID-targeted nuclear restart.
