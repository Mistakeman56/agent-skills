# Pitfall: Never Start Backend with `nohup`

## Problem
Starting `miloco-backend` with `nohup miloco-backend &` bypasses supervisord and can cause **pct exec to hang indefinitely** — even simple commands like `pct exec 310 -- uptime` will time out.

## Correct Approach
Always use supervisord to manage miloco-backend:

```bash
# ✅ Correct — use supervisord
pct exec 310 -- supervisorctl -c /root/.openclaw/miloco/supervisord.conf start miloco-backend

# ❌ WRONG — causes container hang
pct exec 310 -- bash -c 'nohup miloco-backend &>/tmp/miloco-backend.log &'
```

## Recovery When nohup Causes Hang
If pct exec hangs after a nohup start:
1. From PVE host, kill the nohup process: `pct exec 310 -- killall miloco-backend`
2. Wait 5 seconds
3. Start via supervisord: `pct exec 310 -- supervisorctl -c /root/.openclaw/miloco/supervisord.conf start miloco-backend`
4. Verify: `pct exec 310 -- supervisorctl -c /root/.openclaw/miloco/supervisord.conf status`

## Why This Happens
miloco-backend is managed by supervisord, not systemd. The nohup process may:
1. Hold file locks or resources that supervisord expects to control
2. Interfere with pct exec's ability to spawn new processes in the container
3. Leave orphan processes that consume container resources

## Session Reference
See `references/2026-07-13-cron-nohup-startup-hang.md` for the full session where this was discovered.
