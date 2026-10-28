# 2026-07-07 Cron — Transient HEVC Recovery

## Timeline
- Pre-run script failed: `⚠️ 无法解析感知日志:` (script timeout)
- Diagnosis: container running, port 1810 initially not listening, `ps aux` showed supervisord (since 01:00) + `miloco-cli service start` + `miloco.main` (since 15:45)
- Health re-check: OK (service had finished starting during diagnosis)
- `perceive logs --since 30m`: returned stale cached data (timestamps 15:17-15:32), `total_inferences: 0`
- `service logs`: showed HEVC frame drops at 15:45:37 → empty frames at 15:45:38 → successful `realtime_perceive` at 15:45:45 (`total_inferences: 1`)
- Final `perceive logs --since 5m`: fresh data at 15:45:35, `total_inferences: 1`

## Key Observations
1. **HEVC frame drops were transient**: 8 `drop non-key frame` messages followed by empty frames, then self-recovery within ~8 seconds. No intervention needed.
2. **Pre-run script failure ≠ service failure**: The script timed out while the service was still starting up. Health check passed during diagnosis.
3. **Stale cached data can contain useful observations**: The cached logs (before restart) showed "三楼书房: 一人躺在床上睡觉" — this was still the accurate house state even though the data was cached.

## Recovery Pattern
- Container was running, service was starting up (supervisord running, miloco.main starting)
- No restart needed — service self-recovered
- Fresh inferences appeared within ~20s of service start
- Transient HEVC drops are normal on startup; distinguish from persistent HEVC failure (Scenario E upstream)
