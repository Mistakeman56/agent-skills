# 2026-07-12 Cron: Pre-Run Timeout False Alarm

## Summary
Pre-run script timed out with `⚠️ 获取感知日志超时，PVE/CT <ID> 可能不可达`. Manual diagnosis revealed the service was healthy — the timeout was caused by slow `pct exec` wrapper latency, not a broken service.

## Timeline
- Pre-run script: timeout (service healthy but slow)
- Manual SSH to PVE: OK (echo OK)
- `pct status 310`: running
- `pct exec 310 -- echo HELLO`: timeout at 20s (wrapper slow, not container hang)
- `pct exec 310 -- ls /`: OK at 60s timeout
- `miloco-cli perceive --help`: OK at 120s timeout (discovered correct subcommand)
- `miloco-cli perceive logs --limit 10`: OK at 120s timeout (24880 entries, fresh data)

## Key Findings
1. The `bash -c` wrapper in `pct exec` adds significant latency (20-30s overhead) even for simple commands
2. The service was healthy the entire time — just needed longer timeouts
3. `miloco-cli perceive logs` with default `--limit` returned recent data (same-day timestamps)
4. Perception data: person sleeping in 三楼书房, outdoor areas (前院/北院) empty, nighttime scene

## Recovery Path
Simple: longer timeouts on existing commands. No restart needed.

## Lesson
Pre-run timeout with "获取感知日志超时" is the most common false alarm. Always attempt manual SSH recovery before assuming service failure.
