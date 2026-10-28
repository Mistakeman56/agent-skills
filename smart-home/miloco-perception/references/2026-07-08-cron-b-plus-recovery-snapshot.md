# 2026-07-08 Cron: B+ zombie-bound socket recovery + snapshot interpretation

## Timeline
1. Pre-run script timed out (感知日志超时)
2. PVE reachable, CT <ID> running
3. `pct exec 310 -- ss -tlnp | grep 1810` → port 1810 LISTENING
4. `curl http://127.0.0.1:1810/health` → exit code 7 (connection refused)
5. `miloco-cli perceive logs` → "cannot connect to Miloco backend"
6. **Scenario B+ confirmed**: zombie-bound socket

### Recovery
7. `ps aux | grep miloco` → supervisord (324) + stuck `miloco-cli service start` (251982, 251988) + miloco.main (251991)
8. `kill -9 324 251982 251988 251991` → all processes gone (verified with re-check)
9. `rm -f supervisor.sock; supervisord -c ...` → supervisord started
10. Wait 10s → health still exit code 7, port not yet bound
11. Wait 10s more → health OK, port 1810 bound to fresh miloco.main (PID 252049)
12. `perceive logs --since 30m --limit 10` → 10 fresh entries, total_inferences: 1

### Post-recovery log analysis
All 10 entries showed:
- 三楼书房: 无人, 衣物堆满沙发, 电视关闭
- 前院: 无人/宠物, 台阶有纸箱杂物
- 北院: 白色SUV + 黑色轿车停放, 无人

**total_inferences: 1** — very low, confirms this is a fresh-start snapshot, not accumulated observations.

### Snapshot vs transition interpretation
- **Snapshot**: After service restart, first inference is a point-in-time view. All cameras show no people → "当前无人在家" is a state observation, NOT a "离家" transition event.
- **Transition**: Would require seeing people appear (回家) or disappear (离家) across consecutive inferences. With total_inferences: 1, there's no prior state to compare against.
- **Decision**: Do NOT trigger automatic actions (lights off) based on a post-restart snapshot alone. Wait for additional inferences to establish a baseline before interpreting transitions.

## Key finding: 20-second startup delay
After killing all processes + supervisord start, port 1810 took ~20 seconds to bind (first health check at 10s failed, second at 20s succeeded). The skill says "wait 8-10s" but this session needed 20s. Recommend checking at both 10s and 20s.

## Process kill verification
All PIDs were killed successfully on first attempt — no hidden zombies appeared. This contrasts with the reference case where zombie CLI processes were hidden until the main process was killed.
