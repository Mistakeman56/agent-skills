# CT <ID> Container Recovery Patterns

## Container Unresponsive: `pct exec` Hangs but `pct status` Works

When `pct exec 310 -- <anything>` times out but `pct status 310` returns `status: running`, the container init is stuck. The container appears running but cannot accept exec commands.

**Recovery sequence**:
```bash
# 1. Submit reboot (fire-and-forget, since pct exec hangs)
sshpass -p "<PASSWORD>" ssh root@192.0.2.10 \
  "nohup pct reboot 310 >/dev/null 2>&1 & echo REBOOT_SENT"

# 2. Wait for reboot to complete
sleep 20

# 3. Verify container is alive
sshpass -p "<PASSWORD>" ssh root@192.0.2.10 "pct status 310"
# → status: running

# 4. Test exec works
sshpass -p "<PASSWORD>" ssh root@192.0.2.10 \
  "timeout 15 pct exec 310 -- echo CT310_ALIVE"
```

**Pitfall**: `pct reboot 310` without `nohup &` will also hang because it waits for the container to shut down. Always use `nohup pct reboot 310 &` with a separate wait.

## Supervisord Not Running After Container Reboot

After rebooting CT <ID>, supervisord does NOT auto-start, so miloco-backend won't start either. You'll see `miloco-cli perceive logs` return `"cannot connect to Miloco backend"` even though the container is alive.

**Diagnosis**:
```bash
pct exec 310 -- bash -c 'export PATH=/usr/local/bin:$PATH; supervisorctl status 2>&1'
# → "http://localhost:9001 refused connection" = supervisord not running
```

**Recovery**:
```bash
pct exec 310 -- bash -c 'export PATH=/usr/local/bin:$PATH; \
  supervisord -c /root/.openclaw/miloco/supervisord.conf 2>&1; \
  sleep 3; \
  supervisorctl -c /root/.openclaw/miloco/supervisord.conf status 2>&1'
# → "miloco-backend RUNNING pid XXXX, uptime 0:00:03"
```

**Full recovery from container hang → perception logs** (single script):
```bash
# All-in-one: reboot, wait, start supervisord, fetch logs
sshpass -p "<PASSWORD>" ssh root@192.0.2.10 \
  "nohup pct reboot 310 >/dev/null 2>&1 &"
sleep 25
sshpass -p "<PASSWORD>" ssh root@192.0.2.10 \
  "timeout 20 pct exec 310 -- bash -c 'export PATH=/usr/local/bin:\$PATH; \
    supervisord -c /root/.openclaw/miloco/supervisord.conf 2>/dev/null; \
    sleep 5; \
    miloco-cli perceive logs --since 1h --limit 10 2>&1'"
```

**Root cause**: The supervisord config has `nodaemon=false` but no systemd/service wrapper, so it doesn't start on boot. The `autorestart=true` only helps once supervisord itself is running. Consider adding supervisord to CT <ID>'s `/etc/rc.local` or a systemd service for auto-start.

## Diagnostic Decision Tree for Container Issues

```
pct status 310 → "running" but pct exec hangs?
  └─ Container init stuck → nohup pct reboot 310 & (fire-and-forget)
      └─ After reboot: supervisord not running?
          └─ supervisord -c /root/.openclaw/miloco/supervisord.conf
              └─ miloco-backend should start (autorestart=true)
```

## Key Paths Reference

| Item | Path |
|------|------|
| Supervisord config | `/root/.openclaw/miloco/supervisord.conf` |
| Supervisord log | `/root/.openclaw/miloco/log/supervisord.log` |
| Backend log | `/root/.openclaw/miloco/log/miloco-backend.log` |
| Supervisord PID file | `/root/.openclaw/miloco/supervisord.pid` |
| Supervisord socket | `/root/.openclaw/miloco/supervisor.sock` |
| Backend binary | `/usr/local/bin/miloco-backend` |
| CLI binary | `/usr/local/bin/miloco-cli` |
