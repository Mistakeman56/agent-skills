# 2026-07-06 Evening Cron — HEVC Upstream Pipeline Failure

## Summary
Scheduled perception monitor found PVE/CT <ID> unreachable (script timeout). Manual intervention performed: nuclear restart + container stop/start. Service recovered cleanly but perception pipeline still producing stale logs. Diagnosed as upstream HEVC decoder failure.

## Timeline
1. Pre-run script timed out fetching perception logs
2. `pct status 310` → running (container alive)
3. `ps aux | grep miloco` → stuck processes: supervisord in Ds state, multiple miloco-cli perceive logs in R/D states
4. **Nuclear restart** (killall -9 supervisord/python3/miloco-cli + socket clear + supervisord start):
   - Health OK after restart
   - `perceive logs --limit 1` returned stale data (2026-06-24, 12 days old, `total_inferences: 0`)
   - `perceive devices` timed out → progressive degradation
5. **Container stop/start** (pct stop 310 → pct start 310 + supervisord start):
   - Health OK, supervisord + miloco.main clean (2 processes)
   - `perceive logs --limit 1` still stale (same 2026-06-24 timestamp)
   - `service logs` showed: `drop non-key frame, MIoTCameraCodec.VIDEO_HEVC` (dozens/sec)

## Root Cause
HEVC decoder cannot process the camera stream. The camera sends video but the decoder drops all non-key frames, so no video frames get decoded for inference. This is an upstream codec/encoding issue, not a miloco service problem.

## Restart Budget
Used 2/2 attempts (nuclear restart + container stop/start). Stopped per budget rule.

## Key Diagnostic Signal
`miloco-cli service logs` showing repeated `drop non-key frame, MIoTCameraCodec.VIDEO_HEVC` messages indicates the HEVC decoder is the bottleneck. The camera is online and sending data, but the stream format is incompatible with the decoder.

## Next Steps (for user)
- Check camera HEVC encoding settings (keyframe interval, profile)
- Verify camera firmware version (recent update may have changed encoding)
- Test with a different camera or H.264 fallback if available
- Check network conditions — keyframes are larger, more prone to packet loss

## Environment
- PVE: 192.0.2.10 (ssh password: <PASSWORD>)
- CT <ID>: LXC container, miloco service on port 1810
- Service manager: supervisord at /root/.openclaw/miloco/supervisord.conf
