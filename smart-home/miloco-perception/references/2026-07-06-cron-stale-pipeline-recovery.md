# 2026-07-06: Cron Job — Stale Pipeline Recovery After Service Restart

## Context
Scheduled cron job (感知引擎监控) — pre-run script timed out fetching perception logs.

## Timeline
1. **Pre-run script**: Timed out (`获取感知日志超时，PVE/CT <ID> 可能不可达`)
2. **`pct status 310`**: Running ✓
3. **Health check**: `curl http://127.0.0.1:1810/health` → exit code 7 (connection refused)
4. **Process check**: supervisord running, `miloco-cli service start` already in R state (pid 7943), miloco.main running (pid 7945)
5. **Wait 10s**: Health recovered → `{"status":"ok"}`
6. **Perception logs**: Still showing June 24 timestamps (12 days stale), `total_inferences: 1`
7. **Soft restart** (`service stop && service start`): Succeeded, but logs still stale
8. **Nuclear restart** (`killall -9 supervisord/python3`): `pct exec` timed out at 20s — killall likely succeeded but wrapper hung
9. **Container restart** (`pct stop 310 && pct start 310`): Succeeded
10. **supervisord start**: Succeeded, health OK after 10s
11. **Perception logs**: Still June 24 — confirmed upstream pipeline issue
12. **`perceive query`**: Timed out (additional pipeline stall signal)
13. **`service logs`**: Timed out (additional pipeline stall signal)

## Key Observations
- `miloco-cli service start` already in R state = service partially alive, wait and re-check
- `pct exec` wrapper can time out even though killall works inside — escalate to container stop/start
- When pipeline is stuck: `perceive query`, `service logs`, AND `perceive logs` all exhibit different failure modes
- Soft restart → nuclear restart → container restart chain did NOT fix stale logs = upstream issue confirmed

## Resolution
Stopped at Scenario E boundary — service healthy, cameras online, but inference pipeline not generating new entries. Requires manual investigation of model API and camera feed accessibility.

## Camera Status (post-restart)
All 3 cameras online:
- 北院摄像头 (1176694677)
- 小米智能室外摄像机 4 Pro 三摄变焦版 (1179415436)
- 三楼监控 (1180976594)
