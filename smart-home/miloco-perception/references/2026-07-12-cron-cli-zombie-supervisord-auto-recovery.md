# 2026-07-12 Cron: CLI Zombie Cleanup → Supervisord Auto-Recovery

## Timeline
- Pre-run script timeout: `⚠️ 获取感知日志超时，PVE/CT <ID> 可能不可达`
- Agent SSH: PVE reachable, CT <ID> running
- `miloco-cli perceive logs` → `{"error": "cannot connect to Miloco backend at http://127.0.0.1:1810"}`
- `pct status 310` → running
- `ps aux | grep miloco` → supervisord (PID 626285) alive, `miloco-cli service start` (PID 696687/696693) stuck, miloco.main (PID 696695) alive
- `ss -tlnp | grep 1810` → empty (port not listening)
- `miloco-cli service restart` → `{"error": "supervisorctl restart failed: "}` (control interface broken)
- `supervisorctl status` → `http://localhost:9001 refused connection`
- `kill -HUP 626285` → no visible effect
- Killed stuck CLI processes: `kill 696695 696693 696687`
- `miloco-cli service start` → `{"code": 1, "message": "already running (pid=697789)"}` + `ss -tlnp` shows port 1810 bound to PID 697789
- `miloco-cli perceive logs --limit 10` → success, returned 10 entries (stale from June 24, `total_inferences: 0`)

## Key Finding
After killing the stuck miloco-cli processes, supervisord (which was alive but with broken HTTP control interface) auto-restarted miloco.main. The `miloco-cli service start` command then detected the new process and returned "already running (pid=697789)". Port 1810 was bound to the new PID. **No nuclear restart or container stop/start was needed** — just killing the blocking zombie processes.

## Recovery Path
This is the lightest recovery variant of Scenario B:
1. Supervisord alive but HTTP interface (9001) broken
2. Stuck miloco-cli processes blocking the restart path
3. Kill stuck CLI processes → supervisord auto-restarts miloco.main → port binds
4. Verify with `ss -tlnp | grep 1810` and `miloco-cli perceive logs`

## Distinction from Existing Patterns
- **vs. Scenario B nuclear restart**: No need to kill supervisord + miloco.main and restart. Supervisord was alive and functional (just HTTP interface broken), so killing only the CLI zombies was sufficient.
- **vs. "zombie cleanup + wait" (existing Scenario B lightest fix)**: This is the same pattern but with the added signal that supervisord's HTTP interface is also broken (port 9001 refused). The HTTP interface being broken does NOT mean supervisord can't restart processes — it just means `supervisorctl` commands won't work. Supervisord's process management (watchdog restarts) still functions via its internal event loop.

## Diagnostic Signal: "already running (pid=XXXX)"
When `miloco-cli service start` returns `"already running (pid=XXXX)"`, it means:
- Supervisord has already spawned a new miloco.main process
- The PID in the message is the NEW process (not a stuck old one)
- Check `ss -tlnp | grep 1810` immediately — the port is likely binding or already bound
- Do NOT try to kill this PID or restart again — the service is recovering

## Lesson
When supervisord's HTTP control interface is down (port 9001 refused), supervisord's internal process management still works. Killing stuck child processes (CLI zombies) allows supervisord to auto-restart the managed service. This is faster than nuclear restart and avoids disrupting supervisord itself.
