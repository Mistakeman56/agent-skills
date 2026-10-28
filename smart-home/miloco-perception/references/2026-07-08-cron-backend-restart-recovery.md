# 2026-07-08 Cron: Backend Restart During Pre-Run

## Symptoms
- Pre-run script output: `⚠️ 获取感知日志超时，PVE/CT <ID> 可能不可达`
- `miloco-cli perceive logs` returned: `{"error": "cannot connect to Miloco backend at http://127.0.0.1:1810"}`
- `miloco-cli service status` showed: `running: true, pid: 1177469, uptime_seconds: 18`

## Diagnosis
- Backend was still initializing after a restart (uptime < 30s)
- Port 1810 not yet accepting connections despite supervisord reporting running
- `pct status 310`: `running` (container healthy)

## Recovery
- Waited 10 seconds, retried `perceive logs --since 10m --limit 10 --jsonl`
- Backend had initialized, logs returned successfully
- Total recovery time: ~20s from first failure

## Key Learnings
1. **`uptime_seconds` from `service status`** is the key diagnostic: if < 30s, the backend is still initializing — wait and retry, don't escalate.
2. **`--jsonl` + `--since` work together** — the skill previously said they were mutually exclusive, but `--since 10m --limit 10 --jsonl` returns JSONL-format output within the time window.
3. **One log entry from 三楼书房**: person sleeping in bed (23:51-00:34 Beijing time), then room empty from 00:35 onwards. No home/away events detected.
4. **Cat spotted** in 前院 at 00:34 Beijing time, moved on quickly.

## Outcome
- Perception engine recovered after brief restart
- No actionable home/away events
- System functional, no action needed
