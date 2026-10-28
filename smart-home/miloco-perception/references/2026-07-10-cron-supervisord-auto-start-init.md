# 2026-07-10 — Supervisord Auto-Start After Clean Container Restart

## Timeline
- Cron pre-run script timeout (感知日志超时)
- PVE reachable: OK
- CT <ID> status: `running`
- pct exec commands mostly hanging (echo works, uptime/ps aux/cat hang)
- Lock file cleared → `pct stop 310` → `pct start 310`
- After restart: supervisord already running (tried to start, got "Another program is already listening")
- `supervisorctl -c /root/.openclaw/miloco/supervisord.conf status` → `miloco-backend RUNNING pid 325, uptime 0:00:24`
- Waited ~15s → `perceive logs --since 30m --limit 30` returned fresh data successfully

## Key Finding: Supervisord Auto-Starts After Clean Container Restart

After a **clean** `pct stop` → `pct start` cycle, supervisord and miloco-backend may auto-start without manual intervention. This contradicts the skill's general guidance that "the miloco service does not auto-start."

**When this happens**:
1. You try to start supervisord → get "Another program is already listening on a port"
2. Use `supervisorctl -c /root/.openclaw/miloco/supervisord.conf status` to check backend state
3. If backend shows `RUNNING` with low `uptime_seconds` (< 30s), it's still initializing
4. Wait 15-20s, then retry `perceive logs`

**When this does NOT happen**:
- After a **degraded** container restart (pct exec was hanging badly before restart)
- After a nuclear restart (kill supervisord + python3)
- When the container was in a truly broken state (both pct exec AND lxc-attach hanging)

## Diagnostic: "Another program is already listening"

This error from `supervisord -c <config>` is a **positive diagnostic** — it confirms supervisord is running. Don't treat it as a failure. Follow up with `supervisorctl -c <config> status` to check the backend's state.

## Timing: Backend Initialization

After supervisord confirms the backend is `RUNNING`, the HTTP server on port 1810 may not be ready immediately:
- **0-10s**: Backend starting, port 1810 not bound
- **10-20s**: Port 1810 binding, health endpoint may respond
- **20-30s**: Backend fully initialized, `perceive logs` works reliably

In this session, the first successful `perceive logs` was at ~15s after confirming supervisord was running.

## Perception Logs
Timestamps: 2026-07-10T04:35-05:04 UTC (12:35-13:05 CST)
- 三楼书房: person at computer (戴眼镜男子), using phone, putting on headphones
- 前院: empty throughout
- 北院: cars parked, dog briefly passed
- No home/away transitions → no device control needed
