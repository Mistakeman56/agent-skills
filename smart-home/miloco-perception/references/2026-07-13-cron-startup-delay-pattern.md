# 2026-07-13 Cron: Startup Delay Pattern

## Timeline
- Pre-run script timed out: `⚠️ 获取感知日志超时`
- SSH into CT <ID>: supervisord + miloco.main running, port 1810 NOT listening
- Backend uptime showed only 19 seconds — process had just started
- Waited 10 seconds, retried — port 1810 now bound and logs accessible
- Logs showed normal activity: person at computer, pets roaming, no transitions

## Key Observations
1. **Process alive ≠ backend ready** — miloco.main PID existed but port 1810 wasn't bound yet
2. **Supervisorctl confirms status** — `supervisorctl status` showed RUNNING with uptime 0:00:19
3. **Wait-and-retry works** — 10 second sleep was sufficient for port binding
4. **CLI worked without explicit MILOCO_TOKEN** — either auto-detected or token requirement changed
5. **No home/away transitions** — all areas stable, no device control needed

## Diagnostic Commands Used
```bash
# Check if backend process exists
ps aux | grep miloco.main | grep -v grep

# Check supervisor status
supervisorctl -c /root/.openclaw/miloco/supervisord.conf status

# Check port binding
ss -tlnp | grep 1810

# Wait and retry
sleep 10 && ss -tlnp | grep 1810
```

## Lesson
When pre-run times out and backend process is running but port isn't bound, the backend may be in early startup phase. Check `supervisorctl status` for uptime — if very recent (<30s), wait and retry rather than escalating to restart.