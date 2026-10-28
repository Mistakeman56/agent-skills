# 2026-07-08 Cron: Partial pct exec hang + service restart recovery

## Timeline
1. Pre-run script timed out (PVE/CT <ID> perceived unreachable)
2. PVE SSH reachable, `pct status 310` → running
3. `pct exec 310 -- echo hello` → **works** (fast)
4. `pct exec 310 -- uptime` → **hangs** (>15s)
5. `pct exec 310 -- ls /usr/local/bin/` → **hangs** (>15s)
6. Fallback: `lxc-attach -n 310 -- ls /usr/local/bin/` → **works**, shows miloco-cli present
7. `miloco-cli perceive logs --limit 10` → `{"error": "cannot connect to Miloco backend at http://127.0.0.1:1810"}`
8. `supervisorctl status` → "http://localhost:9001 refused connection" (supervisord HTTP interface down)
9. `ps aux | grep miloco` → supervisord (PID 324), miloco-cli service start (PID 10338), miloco.main (PID 10356) — all running
10. `ss -tlnp | grep 1810` → no output (port unbound)
11. `miloco-cli service restart` → `{"code": 0, "message": "restarted", "pid": 11099}`
12. Wait 5s → port 1810 listening, `perceive logs --limit 10` returns data
13. Logs stale: timestamps from 2026-06-24 (~2 weeks old), `total_inferences: 0`

## Key Findings

### Partial pct exec functionality
`pct exec` was **not completely broken** — it handled `echo hello` (trivial command) but hung on `uptime`, `ls`, and any non-trivial command. This is a middle ground between "fully working" and "completely hung" that the existing skill didn't document.

**Pattern**: `pct exec` can pass through very simple commands (builtin echo, no subprocess) while hanging on anything that spawns a subprocess or does I/O inside the container. The container itself is responsive (lxc-attach works for all commands) — the issue is in the pct exec wrapper's handling of the container's process namespace.

**When encountering this**: Don't assume pct exec is either "working" or "broken" — test with a real command, not just echo. If echo works but uptime hangs, switch to lxc-attach immediately rather than wasting time on pct exec retries.

### supervisord HTTP interface down, but socket works
`supervisorctl status` failed with "http://localhost:9001 refused connection" — supervisord's inet_http_server was not bound. But `miloco-cli service restart` worked because it communicates via Unix socket (`/root/.openclaw/miloco/supervisor.sock`), not HTTP.

**Implication**: Don't use `supervisorctl status` failure as a signal that supervisord is dead. Supervisord can be alive and responsive via socket while the HTTP interface is down.

### `miloco-cli service restart` as single command
The skill only documented `miloco-cli service start` and `miloco-cli service stop` as separate commands. This session confirmed `miloco-cli service restart` works as a single atomic restart command. It's cleaner than stop+start for Scenario B recovery.

### Recovery path
This was a clean Scenario B recovery: port 1810 unbound, processes alive → `miloco-cli service restart` → port bound → logs available. No nuclear restart needed. The stale logs (2 weeks old, total_inferences: 0) indicate the perception pipeline was down before this session.

## vs Existing Scenarios
- **Not Scenario B0** (backend completely dead): processes were running
- **Not Scenario B+** (zombie-bound socket): port was NOT listening
- **Matches Scenario B** (port unbound, process alive): exact match, but with a cleaner fix via `miloco-cli service restart` instead of stop+start
- **Stale logs = Scenario E** was present but not diagnosed as active (no restart attempts to verify pipeline health)

## Data Quality Note
Logs returned by `--limit` were from 2026-06-24 with `total_inferences: 0` — confirming Scenario E (stale cached data, pipeline not inferring). The service was down for ~2 weeks before this session's restart.
