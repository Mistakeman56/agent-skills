# 2026-07-08 Cron: Mis-escalation from miloco deadlock to container stop/start

## Scenario
Pre-run script timeout → perception logs unreachable.

## Diagnosis Path
1. PVE reachable ✅
2. CT <ID> status: running ✅
3. `pct exec 310 -- uptime` → hangs (15s timeout)
4. `lxc-attach -n 310 -- echo HELLO` → works
5. `lxc-attach -n 310 -- ps aux` → works (shows supervisord PID 324, stuck `miloco-cli service start` PIDs 40907/40909, miloco.main PID 40916 in Rl state)
6. `lxc-attach -n 310 -- ss -tlnp | grep 1810` → empty (port not listening)
7. `lxc-attach -n 310 -- curl health` → exit code 7 (connection refused)

## Classification
**Container alive, miloco deadlocked** — lxc-attach echo AND ps aux work, but ss/curl hang.

Per the skill's 3-level probe, this maps to: "kill stuck processes by PID, clear socket, restart supervisord. **Do NOT do container stop/start**."

## What Actually Happened
Agent escalated to `pct stop 310` / `pct start 310` (container stop/start) instead of PID-targeted nuclear restart. Recovery succeeded but took ~35s for port binding + supervisord restart, when PID-targeted kill + socket clear + supervisord restart would have been faster.

## Why the Mis-escalation
The Cron Job Recovery quick-reference (step 3) jumped from "pct exec hangs" to "container stop/start" without surfacing the ps aux probe. The correct path is buried in Scenario A's 3-level probe section. The agent followed the quick-reference rather than reading the full Scenario A details.

## Correct Action for This Scenario
```bash
# 1. Get PIDs (ps aux works via lxc-attach)
lxc-attach -n 310 -- ps aux | grep miloco | grep -v grep
# 2. Kill by PID
kill -9 <supervisord_PID> <stuck_cli_PID> <miloco_main_PID>
# 3. Verify killed, kill any hidden zombies
lxc-attach -n 310 -- ps aux | grep miloco | grep -v grep
kill -9 <newly_found_PIDs>
# 4. Clear socket + restart supervisord
lxc-attach -n 310 -- bash -c 'rm -f /root/.openclaw/miloco/supervisor.sock; /usr/local/bin/supervisord -c /root/.openclaw/miloco/supervisord.conf'
```

## Process State at Diagnosis
- supervisord: PID 324 (running since 13:47)
- `miloco-cli service start`: PID 40907 (bash wrapper, S state, since 14:22)
- `miloco-cli service start`: PID 40909 (python3, S state, since 14:23)
- `miloco.main`: PID 40916 (Rl state, started 14:24, <1s CPU time — just started but port unbound)

## Post-Recovery
- Health OK at ~35s after container restart
- Fresh inferences confirmed: `--since 5m` returned 14:26 UTC data
- All areas empty in latest snapshot — no home/away transitions to act on
