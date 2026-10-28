# Miloco Perception Engine — Recovery Procedures

## Backend Restart Detection & Auto-Recovery

### Symptom
`miloco-cli perceive logs` returns:
```json
{"error": "cannot connect to Miloco backend at http://127.0.0.1:1810"}
```

### Diagnosis Steps
1. **Check if PVE/CT <ID> is reachable**: `ping -c 3 192.0.2.10`
2. **SSH into PVE and check container**: `sshpass -p "<PASSWORD>" ssh -o StrictHostKeyChecking=no root@192.0.2.10`
3. **Check miloco process**: `pct exec 310 -- ps aux | grep miloco`
4. **Check supervisord status**: `pct exec 310 -- supervisorctl -c /root/.openclaw/miloco/supervisord.conf status`
5. **Check port 1810**: `pct exec 310 -- ss -tlnp | grep 1810`

### Common Patterns

#### Backend Just Restarted
- supervisord shows `miloco-backend RUNNING pid XXXXX, uptime 0:00:25`
- Port 1810 not yet listening
- **Action**: Wait 10-15 seconds, then retry
- The backend needs time to initialize after supervisord restarts it

#### Backend Not Running
- supervisord shows `miloco-backend STOPPED` or `FATAL`
- **Action**: `pct exec 310 -- supervisorctl -c /root/.openclaw/miloco/supervisord.conf restart miloco-backend`

#### CT <ID> Unreachable
- Ping fails
- **Action**: Check PVE status, restart container if needed

### Recovery Command Sequence
```bash
# 1. Check connectivity
ping -c 3 192.0.2.10

# 2. SSH and check service status
sshpass -p "<PASSWORD>" ssh -o StrictHostKeyChecking=no root@192.0.2.10 \
  "pct exec 310 -- supervisorctl -c /root/.openclaw/miloco/supervisord.conf status"

# 3. If backend just restarted (uptime < 30s), wait and retry
sleep 10

# 4. Verify port is listening
sshpass -p "<PASSWORD>" ssh -o StrictHostKeyChecking=no root@192.0.2.10 \
  "pct exec 310 -- ss -tlnp | grep 1810"

# 5. Test health endpoint
sshpass -p "<PASSWORD>" ssh -o StrictHostKeyChecking=no root@192.0.2.10 \
  "pct exec 310 -- curl -s http://127.0.0.1:1810/health"

# 6. Fetch logs
sshpass -p "<PASSWORD>" ssh -o StrictHostKeyChecking=no root@192.0.2.10 \
  "pct exec 310 -- bash -c 'export PATH=/usr/local/bin:$PATH; miloco-cli perceive logs --limit 10'"
```

### Log Freshness Check
Perception logs may be stale. After fetching, check the `t` (timestamp) field:
- Current logs: within last 5 minutes
- Stale logs: hours or days old → perception pipeline may not be running
- Empty logs: no perception events captured recently
