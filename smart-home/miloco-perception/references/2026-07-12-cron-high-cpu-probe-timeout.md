# 2026-07-12 Cron: Legitimate High CPU Causes Probe Timeouts

## Summary
Pre-run script timed out. After host-level cleanup of pre-run pileup, miloco.main was running at 128-132% CPU doing legitimate inference. ALL probe methods timed out — including `echo CONTAINER_OK` via pct exec, `echo LXC_OK` via lxc-attach, and `miloco-cli perceive logs`. Service was healthy; timeouts were due to CPU contention, not container hang.

## Sequence
1. Pre-run script timeout → "获取感知日志超时"
2. PVE reachable, load 11.85 (elevated but <15)
3. Host `ps aux`: miloco.main at 131% CPU, multiple stuck miloco-cli processes (pre-run pileup)
4. Host-level `kill -9` of stuck CLI PIDs → load dropped to 8.50
5. `pct exec 310 -- echo CONTAINER_OK` → timed out (15s)
6. `lxc-attach -n 310 -- echo LXC_OK` → timed out (15s)
7. `lxc-attach -n 310 -- ss -tlnp | grep 1810` → succeeded (port bound)
8. `lxc-attach -n 310 -- curl health` → exit code 7 (connection refused)
9. `lxc-attach -n 310 -- ss -tlnp | grep 1810` → empty (port dropped)
10. Service collapsed, supervisord auto-restarted miloco.main (new PID, 17.9% CPU during init)
11. Waited 20s → health OK, miloco.main at 86% CPU
12. First `perceive logs --since 10m --limit 5` → SUCCESS (3 entries, total_inferences: 1, fresh timestamps)
13. Second `perceive logs --since 5m --limit 3` → timed out (30s)
14. Health check → timed out (15s)
15. Host `ps aux`: miloco.main at 128% CPU (doing inference), supervisord alive
16. Service alive, just slow under load

## Key Observation
When miloco.main is at 128-132% CPU doing legitimate inference:
- `pct exec 310 -- echo OK` can timeout (10-15s)
- `lxc-attach -n 310 -- echo OK` can timeout (10-15s)
- `ss -tlnp | grep 1810` may succeed (fast kernel call)
- `curl health` may fail (connection refused during brief window)
- `miloco-cli perceive logs` may timeout (60s+)

This is NOT a container hang. The container is alive but slow under CPU contention from the inference process. Do NOT escalate to container stop/start.

## Correct Action
1. Confirm miloco.main is at high CPU doing inference (not stuck in D state with low CPU time)
2. Confirm supervisord is alive
3. If both true → service is healthy, stop probing
4. If you need perception data, wait for CPU to drop (inference bursts are periodic) then try once

## Anti-pattern: Probe Escalation Creates Pileup
After cleaning up pre-run pileup, the agent escalated probe methods (pct exec → lxc-attach → host shell), each creating new stuck processes:
- `miloco-cli perceive logs` via pct exec → stuck in R state
- `miloco-cli perceive logs` via lxc-attach → stuck in D state
- `curl -s http://127.0.0.1:1810/health` via lxc-attach → stuck in D state
- `pgrep -la python3` via lxc-attach → stuck in D state (even lightweight commands fail under >115% CPU)
- `ss -tlnp | grep 1810` via lxc-attach → stuck in D state
- Each probe added ~1-5% CPU load and a new stuck process

**Recovery of self-inflicted pileup**: stuck lxc-attach wrapper processes CAN be killed from the PVE host shell (`kill -9 <host_PID>`) — same as pre-run zombies. This works because lxc-attach wrappers run in the host PID namespace.

The correct action after confirming service health (supervisord alive, miloco.main doing inference) is to STOP PROBING and report status. Even `pgrep` via lxc-attach times out under extreme CPU — do NOT assume lxc-attach is lighter than pct exec in this scenario.
