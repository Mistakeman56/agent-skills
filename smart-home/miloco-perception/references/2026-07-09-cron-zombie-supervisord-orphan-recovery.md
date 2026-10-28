# 2026-07-09 Cron: Zombie miloco.main + Orphaned Process Recovery

## Scenario
Pre-run script timed out. PVE reachable, CT <ID> running, but pct exec and lxc-attach echo both timed out.

## Key observation
- pgrep worked when echo/ps aux hung (partial lxc-attach hang)
- `pgrep -la python3` showed: `45889 [python3] <defunct>` (zombie miloco.main)
- `pgrep -la supervisord`: PID 324 alive
- `pgrep -la miloco`: `51302 /usr/bin/python3 /usr/local/bin/miloco-cli service start` (stuck)
- Port 1810: NOT listening

## Recovery steps
1. Killed supervisord (324), zombie (45889), stuck CLI (51302) via PID-targeted `kill -9`
2. **New orphaned miloco.main appeared (PID 51309)** — likely spawned by supervisord before the kill signal was fully processed. Supervisord was dead but its child was already spawned.
3. Killed orphaned miloco.main (51309) — it became defunct
4. Cleared socket: `rm -f /root/.openclaw/miloco/supervisor.sock`
5. Started supervisord fresh: `/usr/local/bin/supervisord -c /root/.openclaw/miloco/supervisord.conf`
6. Health OK after 15s wait
7. Perception logs retrieved successfully

## Pitfall: Orphaned miloco.main after supervisord kill
After killing supervisord during PID-targeted nuclear restart, a new orphaned miloco.main process may appear. This is because supervisord spawns its children asynchronously — the kill signal arrives but the child was already forked. **Always re-check `pgrep -la python3` after killing supervisord** and kill any new non-defunct miloco.main before clearing socket and restarting.

## Log analysis
7 inference entries from ~04:15-04:36 UTC (12:15-12:36 Beijing). All areas showed no people:
- 前院: empty
- 北院: cars parked, no people
- 三楼书房: empty

Post-restart snapshot phase — no transition events confirmed.
