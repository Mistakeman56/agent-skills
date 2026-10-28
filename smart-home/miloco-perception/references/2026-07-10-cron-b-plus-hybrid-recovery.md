# 2026-07-10 Cron — B/B+ Hybrid Recovery via pct exec

## Summary
Pre-run script failed with "⚠️ 无法解析感知日志:" (parse failure, not timeout). PID-targeted nuclear restart via `pct exec` (not lxc-attach) resolved the issue cleanly.

## Initial State
- PVE reachable, load elevated (12.78)
- Container CT <ID>: running
- Health check: exit code 7 (connection refused)
- Port 1810: not listening
- Processes found:
  - supervisord (PID 25833) — running since 05:36
  - Two `miloco-cli service start` zombies (PIDs 35117/35118 and 35132/35137) — stuck in S state
  - miloco.main (PID 35140) — **D state** (Uninterruptible Sleep), running since 05:51

## Diagnosis
B/B+ hybrid: port unbound (B characteristic) + zombie CLI processes present (B+ diagnostic) + miloco.main in D state. `pct exec` was fully functional (container alive, not hung).

## Recovery
PID-targeted nuclear restart via `pct exec`:
1. `kill -9 35117 35118 35132 35137 35140 25833` — some PIDs already gone (zombie processes that died between poll and kill)
2. Verified all processes killed: `ps aux | grep miloco | grep -v grep` → empty
3. `rm -f /root/.openclaw/miloco/supervisor.sock && /usr/local/bin/supervisord -c /root/.openclaw/miloco/supervisord.conf` → SUPERVISORD_STARTED
4. Waited 20s, health check: `{"status":"ok"}` ✅

## Post-Recovery Verification
- `perceive logs --since 1h`: returned 10 stale cached entries (timestamps from 04:55-05:23 UTC, before restart), `total_inferences: 0`
- `perceive logs --since 10m`: returned 1 fresh entry (05:51:55 UTC), `total_inferences: 1`
- `perceive devices`: all 3 cameras online (北院, 前院, 三楼书房)

## Key Observations
1. **`--since` wide window returns stale cached data**: After restart, `--since 1h` included pre-restart cached entries. `total_inferences: 0` confirmed they were stale. `--since 10m` excluded them and returned fresh data.
2. **pct exec works for B/B+ recovery**: When the container is alive (not hung), `pct exec` is fine for PID-targeted kills + supervisord restart. `lxc-attach` fallback is only needed when `pct exec` itself hangs.
3. **Some PIDs already dead**: Two of the four zombie CLI processes (35117, 35118) were already gone by the time kill was attempted. The other two (35132, 35137) and miloco.main (35140) + supervisord (25833) were killed successfully.
4. **Health check at 20s was sufficient**: Port binding happened within 20s of supervisord start (consistent with the 25-30s upper bound documented elsewhere).

## Perception Snapshot (post-recovery)
- North yard: 3 cars parked, no people/pets
- Front yard: empty, furniture visible
- 3rd floor study: person at computer (from cached data, confirmed fresh in subsequent runs)

No home/away transition events detected. Snapshot only (total_inferences ≤ 5).
