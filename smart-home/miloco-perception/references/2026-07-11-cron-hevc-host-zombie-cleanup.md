# 2026-07-11 13:35 — Pre-Run Parse Failure + HEVC Persistent Failure + Host-Level Zombie Cleanup

## Timeline
- 13:35 — Pre-run script output: "⚠️ 无法解析感知日志:" (unable to parse perception logs)
- 13:35 — PVE host load: **16.70** (critically overloaded)
- 13:35 — Host `ps aux --sort=-%cpu | head -15` revealed:

| Process | %CPU | %MEM | Notes |
|---------|------|------|-------|
| `miloco.main` (python3) | **116→107%** | 12.8% | D state (I/O wait), 2GB RSS |
| `miloco-cli service start` ×4 | 12.3+7.1+2.3+1.5% | ~0% | **Host-level zombies** from pre-run retries |
| `miloco-cli service logs --lines 100` | 17.8% | 0% | Agent diagnostic, D state |
| Minecraft server (java) | 13.3% | 39.9% (6.4GB) | Long-running since Jul06 |
| supervisord | 10.1% | 0% | Running normally |

- 13:36 — Killed 4 host-level `miloco-cli service start` zombies via `kill -9` on PVE host
- 13:36 — Load dropped: 16.70 → **9.8**
- 13:36 — Port 1810: ✅ listening (PID 169130)
- 13:36 — `perceive logs --since 1h --limit 5`: returned 5 entries, `total_inferences: 0`
- 13:36 — Latest timestamps: 04:56 UTC (8.5 hours stale)
- 13:37 — `service logs --lines 30`: all HEVC frame drops (`drop non-key frame, MIoTCameraCodec.VIDEO_HEVC`)
- 13:37 — Container commands started timing out (progressive degradation)
- 13:38 — Health check timed out, `ps aux` inside container timed out
- 13:39 — Stopped probing (progressive degradation under load)

## Root Cause
**Persistent HEVC decoder failure** — the camera's HEVC stream cannot be decoded. The decoder drops all non-key frames, resulting in empty video frames. The perception pipeline has not produced fresh inferences in 8.5+ hours.

## Key Learnings

### 1. Host-Level Pre-Run Zombies
The pre-run script spawns `miloco-cli service start` processes on the PVE **host** (not inside the container). These are SSH wrappers + CLI processes that run in the host's PID namespace. When they get stuck:
- They consume host CPU (10-15% each)
- They can be killed directly on the host shell with `kill -9 <PID>`
- This is DIFFERENT from container processes (which need container-internal PIDs)
- Check with `ps aux --sort=-%cpu | head -15` on the host
- Look for `miloco-cli service start` or `bash -c miloco-cli service start` with low CPU time

### 2. HEVC Failure + miloco.main D State
When miloco.main is in D state (Uninterruptible Sleep) at high CPU while HEVC decoder fails:
- The process is stuck waiting for video frames that never arrive
- This is NOT a computation loop — it's I/O wait on broken decoder
- `kill -9` still works despite D state
- Container becomes progressively degraded as miloco.main holds resources

### 3. Progressive Degradation Confirmation
Commands that worked initially (ss, curl, miloco-cli) timed out after repeated probing:
- 13:36: ss -tlnp ✅, perceive logs ✅
- 13:37: service logs ✅ (slow)
- 13:37: perceive logs --since 5m ❌ (timeout)
- 13:38: curl health ❌ (timeout), ps aux ❌ (timeout)
- Pattern: each probe adds load, container becomes slower

## Perception Data (Last Fresh Inferences — 04:56 UTC)
- 三楼书房: 一名男子坐在电脑前，戴着耳机，桌上有一只猫
- 前院: 空旷，无动态
- 北院: 停放绿色轿车和黑色轿车，远处有灰色SUV

## Recovery Status
- No restart attempted (HEVC failure is upstream, restart won't fix)
- Host load reduced from 16.70 to 9.8 by killing host-level zombies
- Container remains running but degraded
- Upstream investigation needed: camera HEVC encoding settings, firmware, network keyframe delivery
