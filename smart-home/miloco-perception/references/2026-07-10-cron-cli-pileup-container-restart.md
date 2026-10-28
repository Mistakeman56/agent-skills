# 2026-07-10: miloco-cli Process Pileup → Container Restart Recovery

## Timeline
- 14:47–14:53: Person at computer in 三楼书房 (perception working)
- 14:53: Person left 三楼书房
- ~14:56: miloco.main CPU spiked to 123%, multiple miloco-cli processes stuck in R/D state
- 14:59–15:08: Pre-run script attempts pile up more stuck miloco-cli processes (sshpass → lxc-attach → miloco-cli perceive logs × multiple)
- 15:08: Pre-run script times out ("获取感知日志超时")
- 15:09: Agent diagnosis begins — PVE load 12.19, both pct exec and lxc-attach hang
- 15:10: Nuclear restart (kill supervisord + miloco.main, clear socket, restart supervisord) — health OK but CLI commands still hang
- 15:12: Container stop/start recovery — supervisord started manually, health OK at 25s
- 15:14: Fresh perception logs retrieved successfully

## Root Cause
miloco-cli process pileup (Scenario D variant). The pre-run script's multiple retry attempts (each spawning new miloco-cli perceive logs / service start processes) compounded the pileup. The existing stuck processes blocked new CLI commands from completing, creating a cascading timeout pattern.

Key observation: `miloco.main` at 123% CPU was NOT the direct cause — it was the backend doing inference. The stuck miloco-cli wrapper processes were consuming additional CPU and blocking the CLI's HTTP connection path.

## Recovery Path
1. `ps aux | grep miloco` on PVE host (works when lxc-attach hangs)
2. Kill all stuck miloco-cli processes by PID
3. Nuclear restart (kill supervisord + miloco.main, clear socket, restart supervisord)
4. If CLI commands still hang after nuclear restart → container stop/start
5. Manual supervisord start after container restart
6. Health check at 25-30s interval

## Key Lesson
When the pre-run script times out due to CLI process pileup, the nuclear restart alone may not clear the pipeline. Container stop/start is needed as a second recovery step. The 2-restart budget applies: nuclear restart = 1 attempt, container restart = 2nd attempt. If container restart also fails, report upstream failure.

## Post-Recovery Log Interpretation
- First logs after recovery show a snapshot (person left at 14:53, all areas empty)
- 14-minute gap in logs (14:57 → 15:11) corresponds to service downtime during recovery
- Only ~10 minutes of fresh data — insufficient to determine persistent away state
