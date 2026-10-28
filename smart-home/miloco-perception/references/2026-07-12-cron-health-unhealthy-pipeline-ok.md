# 2026-07-12 Late Night Cron — Health "unhealthy" but Pipeline Functional

## Summary
Pre-run script timed out (`⚠️ 获取感知日志超时`). Manual diagnosis revealed the service was healthy despite the health endpoint returning `{"status":"unhealthy"}`.

## Timeline
- 23:24 — Pre-run script timed out
- 23:24 — PVE reachable, host load 10.01
- 23:24 — `ps aux --sort=-%cpu`: miloco.main at 150% CPU, Sl state, 7:39 CPU time
- 23:24 — Applied False Alarm Shortcut (miloco.main doing inference)
- 23:24 — Killed 5 stuck CLI zombie processes from host shell (pre-run retry pileup)
- 23:25 — Health endpoint returned `{"status":"unhealthy"}`
- 23:25 — `perceive logs --since 30m --limit 5`: returned 5 fresh entries, `total_inferences: 7`
- 23:25 — `perceive devices`: all 3 cameras online (北院, 前院, 三楼书房)
- 23:25 — Load dropped to 8.39 after zombie cleanup

## Key Observations
1. **`{"status":"unhealthy"}` is not a restart trigger** — the pipeline was fully functional with fresh inferences
2. **HEVC frame drops coexist with working pipeline** — `service logs` showed `drop non-key frame` messages but some frames still decoded successfully
3. **miloco.main state changed from Sl to Dl** during the session — the D state was a brief I/O wait, not a stuck process (CPU time continued accumulating from 7:39 to 8:07)
4. **Zombie cleanup from host shell** worked as expected — container processes (UID 100000) are killable from PVE host

## Perception Data (from `perceive logs --since 30m`)
- 北院: Night view, white SUV and black sedan parked, no people
- 前院: Night view, BBQ grill, glass room, no people activity
- 三楼书房: No recent data in this window

## Service Logs
All 30 most recent log lines were HEVC decoder messages:
- `drop non-key frame, MIoTCameraCodec.VIDEO_HEVC` (27 entries)
- `video frame is empty` (3 entries)

Despite these errors, the pipeline produced 7 fresh inferences. The HEVC drops are degraded but not blocking.

## Environment
- PVE host load: 10.01 → 8.39 (after cleanup)
- Top CPU consumers: miloco.main (150%), Minecraft server (13.1%), supervisord (8.4%)
- Container: CT <ID> running
- All cameras online
