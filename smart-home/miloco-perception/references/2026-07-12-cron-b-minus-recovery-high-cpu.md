# 2026-07-12 Cron: B− Recovery + High CPU Probe Timeout

## Timeline
- Pre-run script timed out: `⚠️ 获取感知日志超时`
- PVE reachable, backend unreachable (`perceive logs` → "cannot connect to Miloco backend")
- `service status` failed with `FileNotFoundError: supervisorctl` (PATH issue, not supervisord down)
- `ps aux` showed: supervisord running, miloco.main running (0:01 CPU, Sl state), stuck `miloco-cli service start` zombie
- Port 1810 not listening → **Scenario B−** (stuck during initialization)

## Recovery
1. Nuclear restart via pct exec: `kill -9 <supervisord> <miloco.main> <zombie CLI>`
2. Verified all processes gone
3. `rm -f supervisor.sock && supervisord -c ...`
4. Health check at 30s: `{"status":"ok"}` ✅
5. First `perceive logs --since 10m` returned 3 entries, `total_inferences: 1` ✅
   - 三楼书房: user坐在电脑前 (fresh inference)
   - 北院: 停放车辆, 无人 (cached)
   - 前院: 空无一人 (cached)

## Post-Recovery: High CPU Probe Timeout
After confirming health OK + 1 fresh inference, subsequent queries timed out:
- `perceive logs --since 5m`: 60s timeout
- `curl health`: 20s timeout
- Host `ps aux`: miloco.main at 128% CPU, 5:57 accumulated CPU time, Sl state

**Root cause**: miloco.main was doing legitimate high-CPU inference (128%, Sl state, accumulated minutes of CPU). Backend too busy to respond to CLI queries. NOT a container hang or pipeline failure.

**Agent-inflicted pileup**: Diagnostic probes (`miloco-cli perceive logs`, `curl`) accumulated as stuck processes in R state inside container. Killed from host shell with `kill -9 <host_PIDs>`.

**Key lesson**: After confirming health OK + at least 1 fresh inference, STOP PROBING. The service is working — it's just busy.

## Key Distinguishing Signals
- miloco.main Sl state (not Dl/Ds) = healthy process doing inference
- Accumulated CPU time in minutes (not seconds) = legitimate processing
- First query returned fresh data = pipeline working
- High CPU from host `ps aux --sort=-%cpu` = normal, not stuck

## What NOT to Do
- Do NOT escalate to container stop/start when miloco.main is at 128% CPU
- Do NOT keep querying `perceive logs` to "verify stability" when backend is busy
- Do NOT kill miloco.main — it's doing its job
