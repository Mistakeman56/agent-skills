# 2026-07-12 Cron: Host Zombie Cleanup + High CPU Warm-Up

## Summary
Pre-run script timed out (false alarm). Host-level zombie cleanup revealed miloco.main at 126% CPU doing legitimate inference. Service was healthy — stopped probing after confirming Sl state from host ps.

## Timeline
- Pre-run script: timeout (`⚠️ 获取感知日志超时`)
- PVE reachable: OK (echo PVE_OK)
- PVE host load: 9.06 (elevated but manageable)
- CT <ID> status: running
- Host ps aux: found 2 stuck `miloco-cli service start` zombies (PIDs 1385597, 1385159) from pre-run script
- Killed zombies from host shell: `kill -9 1385597 1385159`
- Health check: OK (`{"status":"ok"}`)
- Perception logs (--since 10m): 3 cached entries (total_inferences: 0), person in 三楼书房
- Attempted fresh logs: timed out (30s)
- Host ps check: miloco.main at 126% CPU, Sl state, 1:37 CPU time (started 1 min ago)
- Stuck miloco-cli perceive logs in D state (waiting for backend)
- Killed stuck CLI probe from host: `kill -9 1389904 1389870`
- Stopped probing — service healthy, inference in progress

## Key Findings
1. **Pre-run zombies are host-level processes** — killed directly from PVE host shell with `kill -9 <PID>`
2. **D-state miloco-cli in host ps is a diagnostic signal** — confirms CLI is waiting for backend (backend busy doing inference), not a failure
3. **High CPU in Sl state = healthy inference** — even with total_inferences: 0 during warm-up, the 126% CPU IS the inference happening
4. **Stop probing decision**: Health OK + Sl state at 126% CPU → no need to wait for total_inferences to increment

## Recovery Path
Lightest: host zombie cleanup only. No restart needed. Service auto-recovered.

## Lesson
After host-level zombie cleanup, if health passes and host ps shows miloco.main at high CPU in Sl state, the service is healthy and warming up. Stop probing — each additional query risks pileup. The high CPU IS the inference happening, even before total_inferences increments.
