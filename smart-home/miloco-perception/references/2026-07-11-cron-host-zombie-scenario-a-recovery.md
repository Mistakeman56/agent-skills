# 2026-07-11 Cron Session — Host Zombie Cleanup + Scenario A Recovery

## Timeline
- 20:05 — Pre-run script timeout ("获取感知日志超时")
- 20:06 — PVE reachable, load 9.59. Host `ps aux` revealed 15+ stuck processes: miloco.main (127% CPU), supervisord (D state, 9.6%), 6+ miloco-cli zombies (R/D state), ssh/lxc-attach wrappers
- 20:06 — Killed all 15 host-level PIDs directly on host shell → load dropped to 4.95
- 20:07 — pct exec and lxc-attach both completely unresponsive (echo HELLO hangs) → true Scenario A
- 20:07 — Lock file cleared, container stop/start executed → container running, pct exec works
- 20:07 — No python3 processes inside container → supervisord did NOT auto-start (degraded restart)
- 20:07 — Started supervisord manually via pct exec
- 20:08 — Waited 30s → health OK → perceive logs returned stale cached data (total_inferences: 0)
- 20:08 — Waited 20s more → perceive logs returned 1 fresh entry (total_inferences: 1, 三楼书房 empty)
- 20:09 — All 3 cameras online, pipeline recovering

## Key Decisions
1. **Host zombie cleanup BEFORE container diagnostics** — critical ordering. Cleaning host wrappers first reduced load from 9.59 to 4.95, making subsequent container commands faster.
2. **Scenario A confirmed** — both pct exec and lxc-attach completely hung (even echo HELLO). Container stop/start was the only option.
3. **supervisord did NOT auto-start** — degraded container restart (both access methods fully hung) meant auto-start was unlikely. Manual supervisord start required.
4. **Health check timing** — took ~30s after supervisord start for port 1810 to bind. First health check at 15s would have failed.

## Host-Level Processes Killed
All 15 PIDs were killed directly on the PVE host shell with `kill -9`:
- sshpass wrappers (×3)
- ssh client processes (×3)
- lxc-attach wrappers (×3)
- bash -c miloco-cli wrappers (×3)
- miloco-cli python3 processes (×3): perceive logs ×2, service start ×1

## Post-Recovery State
- miloco.main at 108% CPU (doing legitimate inference, not stuck)
- Minecraft server at 13.2% CPU, 6.3GB RAM (normal)
- Host load: 4.95 (down from 9.59)
- All 3 cameras online: 前院, 北院, 三楼书房
- Pipeline: 1 fresh inference (三楼书房 empty, night mode), warming up

## Lesson
When PVE host load is elevated (8-10) and pre-run script times out, the first action should ALWAYS be cleaning host-level zombie processes before attempting any container diagnostics. The wrappers from failed pre-run attempts accumulate on the host and inflate load, making container commands slower or unresponsive.
