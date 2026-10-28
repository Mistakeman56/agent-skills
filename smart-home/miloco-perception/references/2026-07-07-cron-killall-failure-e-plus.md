# 2026-07-07 Cron: killall Failure + E+ Cascade

## Summary
Perception pipeline startup failure with `killall -9` unreliable for all process types. Two restart attempts exhausted; container restored via stop/start; upstream pipeline failure declared.

## Timeline

| Time | Event |
|------|-------|
| pre-run | Script timeout — perception logs unreachable |
| +0s | Port 1810 not listening. `ps aux` shows 2 supervisord (PIDs 114843, 114849) + 2 miloco.main (PIDs 175849, 177774) — all stale |
| +5s | **Restart attempt 1**: `killall -9 supervisord; killall -9 python3` + supervisord restart |
| +15s | Port 1810 bound, health OK — but OLD miloco.main (PID 175849) holds port. New supervisord + 2 new miloco.main also started. 6 processes total |
| +20s | **Restart attempt 2**: PID-targeted kill (`kill -9 114843 114849 175849 178478 180478 178381`) + supervisord restart |
| +30s | Clean state (1 supervisord + 1 miloco.main). Port 1810 bound, health OK |
| +40s | `perceive logs --limit 5 --pretty` returns stale data (2026-06-24), `total_inferences: 1` |
| +50s | `perceive devices` — all 3 cameras online |
| +80s | `perceive logs` again — **hangs** (40s timeout). Pipeline collapsed |
| +90s | Port 1810 still bound, health OK, but `perceive logs` and `service logs` both hang |
| +100s | Container degrades — `pct exec` commands start timing out |
| +110s | Container stop/start to restore basic functionality |
| +120s | Supervisord restart, health OK |
| +140s | `perceive logs` hangs again — **confirmed upstream pipeline failure** |
| +150s | Container stop/start final cleanup, supervisord started, health OK |

## Key Observations

1. **killall -9 failed for ALL process types** — not just supervisord (as documented 2026-07-06), but also python3/miloco.main. The `pct exec` wrapper's signal delivery is systematically unreliable.

2. **PID-targeted kill worked** — `kill -9 <PID>` succeeded where `killall -9` failed. This is the correct escalation path.

3. **E+ pattern repeated** — after clean restart, pipeline briefly appeared healthy (port bound, health OK, cameras online) then collapsed within 30s. `perceive logs` hung, container degraded.

4. **Progressive degradation confirmed** — after pipeline collapse, even `curl health` and `ps aux` started timing out. The perception pipeline's failure cascades to container health.

5. **Restart budget correctly exhausted** — 2 pipeline restart attempts (killall-based + PID-based), both failed. Container stop/start used only for restoration, not counted against budget.

## Restart Budget Accounting

| Attempt | Method | Result | Counts? |
|---------|--------|--------|---------|
| 1 | killall -9 + supervisord | Partial (stale processes survived) | Yes |
| 2 | PID-targeted kill + supervisord | Clean start, pipeline collapsed | Yes |
| Container stop/start | pct stop/start + supervisord | Restored container only | No (restoration) |

## Diagnosis
- Service healthy: port 1810 bound, health OK, cameras online
- Perception pipeline broken: `perceive logs` hangs, stale cached data
- Upstream failure: not fixable by restarting miloco service
- Root cause unknown — needs manual investigation of model API, HEVC decoder, camera streams
