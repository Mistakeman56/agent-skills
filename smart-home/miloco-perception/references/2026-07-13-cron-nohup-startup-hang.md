# 2026-07-13 Cron: nohup Start Causes Container Hang

## Timeline
- Pre-run script timed out: `⚠️ 获取感知日志超时`
- PVE reachable, CT <ID> running, but `miloco-cli perceive logs` returned `cannot connect to Miloco backend`
- Checked supervisord: backend was not running (no miloco-backend service found via systemctl)
- **Mistake**: Started backend manually with `nohup miloco-backend &>/tmp/miloco-backend.log &`
- Backend started, health check returned `{"status":"ok"}`
- Device list worked: 60+ devices, all online
- Perception logs retrieved: last event from 2026-06-24 (19 days stale)
- **Problem**: After nohup start, all subsequent `pct exec 310 -- ...` commands timed out
- Even `pct exec 310 -- uptime` hung — container became unresponsive
- Had to stop troubleshooting and report findings

## Root Cause
Starting `miloco-backend` with `nohup` bypasses supervisord's process management. The nohup process may:
1. Hold file locks or resources that supervisord expects to control
2. Interfere with pct exec's ability to spawn new processes in the container
3. Leave orphan processes that consume container resources

## Correct Approach
Always use supervisord to manage miloco-backend:

```bash
# ✅ Correct — use supervisord
pct exec 310 -- supervisorctl -c /root/.openclaw/miloco/supervisord.conf start miloco-backend

# ❌ Wrong — don't use nohup
pct exec 310 -- bash -c 'nohup miloco-backend &>/tmp/miloco-backend.log &'
```

## Recovery When nohup Causes Hang
If pct exec hangs after a nohup start:
1. From PVE host, kill the nohup process: `pct exec 310 -- killall miloco-backend`
2. Wait 5 seconds
3. Start via supervisord: `pct exec 310 -- supervisorctl -c /root/.openclaw/miloco/supervisord.conf start miloco-backend`
4. Verify: `pct exec 310 -- supervisorctl -c /root/.openclaw/miloco/supervisord.conf status`

## Lesson
miloco-backend is managed by supervisord, not systemd. Always use `supervisorctl` commands to start/stop/restart. Manual process management (nohup, direct execution) can cause container-level hangs.
