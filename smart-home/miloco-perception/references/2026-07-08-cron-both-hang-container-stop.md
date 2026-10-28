# 2026-07-08 Cron: Both pct exec AND lxc-attach Hang → Container Stop/Start

## Scenario
Pre-run script timed out ("获取感知日志超时"). Both `pct exec` and `lxc-attach` hung for basic commands (`echo HELLO`), confirming true container-level hang — not just miloco deadlock or pct exec wrapper issue.

## Diagnostic Sequence
1. `pct status 310` → `running` (fast, <2s)
2. `pct exec 310 -- bash -c 'ss -tlnp | grep 1810'` → timeout (20s)
3. `lxc-attach -n 310 -- echo HELLO` → timeout (15s)

**Key distinction**: When lxc-attach ALSO hangs for simple commands, it's not a pct exec wrapper issue or miloco deadlock — the container itself is unresponsive. This requires container stop/start, not PID-targeted kills.

## Recovery
```bash
pct stop 310 && sleep 3 && pct status 310  # verify stopped
pct start 310 && sleep 10 && pct exec 310 -- echo PVE_OK  # verify exec works
```

Then start miloco service (NOT via `miloco-cli service start` which hangs after container restart):
```bash
pct exec 310 -- bash -c 'rm -f /root/.openclaw/miloco/supervisor.sock; /usr/local/bin/supervisord -c /root/.openclaw/miloco/supervisord.conf'
```

Wait 10-20s for port 1810 to bind. Health check may take up to 20s after container restart.

## Outcome
- Container recovered cleanly
- Supervisord started, health OK after ~20s
- Perception logs returned fresh data (11 entries, timestamps from current session)
- No stale cached data — `--since 30m` returned live inferences
- No home/away events detected — user confirmed at computer

## Lessons
- When both pct exec AND lxc-attach hang, don't waste time on PID-targeted kills (you can't even get in to find PIDs). Go straight to container stop/start.
- Port binding after container restart can take up to 20s — first health check at 10s may fail, retry at 20s before escalating.
- Using `--since 30m` instead of `--limit N` avoids stale cached data confusion after restart.
