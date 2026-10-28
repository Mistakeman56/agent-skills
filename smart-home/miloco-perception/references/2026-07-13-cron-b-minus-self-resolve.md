# 2026-07-13 Cron: B− Self-Resolve

## Timeline
- Pre-run script timed out: `⚠️ 获取感知日志超时`
- SSH into CT <ID>: supervisord + miloco.main running, port 1810 NOT listening
- Service logs showed: `Uvicorn running on http://0.0.0.0:1810` → `Shutting down` → restart sequence
- Re-checked port: 1810 now listening (service recovered during diagnostics)
- `perceive logs --since 5m` returned 1 fresh entry: person sleeping in 三楼书房

## Key Observations
- Service auto-recovered without intervention — classic B− self-resolve
- The startup log sequence (bind → shutdown → restart → rebind) is a normal self-healing pattern
- Logs from `--since 1h` were stale (June 24) while `--since 5m` was fresh — demonstrates importance of short `--since` windows post-restart
- Perception data: person sleeping at ~02:00 Beijing time (normal nighttime behavior)
- No home/away transitions detected — all areas stable

## Diagnostic Path
1. `miloco-cli perceive logs --limit 10` → returned stale data from June 24
2. `miloco-cli perceive logs --help` → learned `perceive` (not `perception`), `logs` (not `log`)
3. `miloco-cli perceive logs --since 1h --limit 20` → stale data, `total_inferences: 0`
4. `miloco-cli perceive logs --since 5m --limit 10` → fresh data, `total_inferences: 1`
5. Port check confirmed 1810 listening

## Lesson
When pre-run times out, the service may be mid-self-recovery. Short `--since` windows reveal fresh data while long windows return stale cache. The B− state (process alive, port unbound) can self-resolve during the diagnostic window.
