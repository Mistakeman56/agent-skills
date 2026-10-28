# 2026-07-12 Cron: Auto-Recovery Without Manual Intervention

## Timeline
- 03:02 — Pre-run script timeout: `⚠️ 获取感知日志超时`
- 03:03 — Agent SSH: PVE reachable, CT <ID> running (load 10.38)
- 03:03 — `miloco-cli service status`: `running: true, uptime_seconds: 11` — service had JUST restarted
- 03:03 — Backend logs: `Uvicorn running on http://0.0.0.0:1810`, cameras connecting
- 03:04 — `miloco-cli perceive logs --limit 5`: success, returned 5 entries (from June 24, `total_inferences: 0`)

## Key Finding
The pre-run script timed out because the service was in the middle of restarting. By the time the agent SSH'd in (~1 minute later), the service had already completed its restart and was operational. **No manual intervention was needed** — just waiting.

## Distinction from Existing Patterns
- **vs. "pre-run false alarm" (2026-07-12 earlier)**: That session required manual SSH recovery with longer timeouts. This session required ZERO intervention — the service auto-recovered between the pre-run timeout and the agent's SSH check.
- **vs. Scenario B− (stuck init)**: The service was not stuck — it was actively restarting (uptime 11s, logs showing initialization progress). B− processes show near-zero CPU time after hours; this was 11s uptime with active initialization.

## Lesson
When `service status` shows `running: true` with low `uptime_seconds` (< 30s), the backend is still initializing. **Do not escalate** — wait 15-20s and retry. The service may complete its restart on its own without any intervention. The pre-run timeout is often caused by the service being mid-restart, not by the service being broken.

## Stale Logs After Fresh Restart
Logs returned were from 2026-06-24 (18 days old) with `total_inferences: 0`. This is expected after a fresh restart — the pipeline hasn't produced new inferences yet. The logs are cached from before the restart, not live. This matches the documented "stale cache" behavior. The pipeline needs time to warm up and start inferring fresh data.
