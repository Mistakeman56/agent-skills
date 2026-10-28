# 2026-07-07 Cron: Pre-Run Script Timeout Recovery

## Symptoms
- Pre-run script output: `⚠️ 获取感知日志超时，PVE/CT <ID> 可能不可达`
- PVE SSH: OK (PVE_OK returned)
- CT <ID> `pct status`: `running`
- CT <ID> `pct exec` initially: timeout (first curl health check)
- CT <ID> `pct exec` later: `uptime` works (load avg 9.54)
- `ps aux | grep miloco`: supervisord (PID 328, started 16:45) + `miloco-cli service start` (PID 271092, started 18:21) + `miloco.main` (PID 271101, started 18:23, Dl state)

## Diagnosis
- Container was not fully hung (pct exec worked for `uptime`)
- `miloco-cli service start` was already in progress — likely a prior automated restart attempt
- Port 1810 was not listening during initial check (miloco.main still initializing)
- After waiting ~8s, health check returned OK
- `perceive logs --limit 5`: returned stale June 24 data, `total_inferences: 0`
- After 15s wait, `perceive logs --limit 3`: still stale data but `total_inferences: 1`
- `perceive logs --since 30m`: fresh July 6 data (17:55–18:25 UTC), 25 entries, `total_inferences: 1`

## Recovery Action Taken
- Container stop/start (pct stop 310 → sleep 3 → pct start 310 → sleep 5 → verify)
- Supervisord restart (clear socket + start)
- Health confirmed OK after ~18s total init time
- Perception pipeline producing fresh inferences

## Key Learning
1. `perceive logs --limit N` vs `--since 30m` — the former returns stale cached data, the latter filters to fresh entries only. Always use `--since` to diagnose freshness.
2. `total_inferences: 0` is the definitive signal that no fresh inference has occurred — don't trust timestamps alone.
3. The miloco-cli service start was already running when we checked — this may indicate a previous automated recovery attempt that was in progress.

## Outcome
- All 3 cameras online (前院, 北院, 三楼书房)
- No home/away events detected
- System functional, no action needed
