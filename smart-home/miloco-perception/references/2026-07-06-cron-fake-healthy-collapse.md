# 2026-07-06 Cron — Fake-Healthy Collapse After Nuclear Restart

## Context
Scheduled cron job. Pre-run script timed out getting perception logs.

## Timeline
1. `pct status 310` → running ✓
2. `pct exec` echo → OK ✓ (container responsive)
3. `ss -tlnp | grep 1810` → no output (port not listening)
4. `ps aux | grep miloco` → supervisord + `miloco-cli service start` in progress + miloco.main started
5. Wait 10s → port 1810 bound, health OK ✓
6. `perceive logs --limit 3` → returns data, but timestamps from **2026-06-24** (12 days stale), `total_inferences: 0`
7. `perceive devices` → all 3 cameras online ✓
8. Wait 30s, retry `perceive logs --limit 1` → `cannot connect to Miloco backend`
9. Retry → same connection error
10. `ss -tlnp | grep 1810` → port NOT listening anymore (dropped!)
11. `ps aux | grep miloco` → supervisord + miloco.main running, port unbound
12. **Nuclear restart** (killall supervisord, killall python3, rm socket, supervisord start)
13. Wait 12s → port 1810 bound ✓, health OK ✓, `total_inferences: 1`
14. Wait 30s, retry `perceive logs --limit 1` → **timed out** (45s)
15. `curl health` → **timed out** (20s) — container degraded
16. **STOPPED** — declared upstream failure, restart budget exhausted (2 attempts)

## Key Pattern: "Fake-Healthy Collapse"
The service appears healthy briefly after startup, then collapses:

1. Port binds → health responds → stale logs returned (cached)
2. Shortly after: port drops, CLI connection fails
3. After nuclear restart: same pattern — brief health, then degradation to timeout

This is distinct from Scenario E (stable but stale logs). Here the backend:
- Binds port 1810 briefly
- Returns cached/stale data
- Drops the port (process alive but server socket gone)
- Subsequent requests time out, container degrades

**Diagnostic signature**: `perceive logs` returns stale data → next attempt fails → port drops.

## Cameras (all online)
- 三楼监控 (1180976594): online
- 北院摄像头 (1176694677): online
- 前院 (1179415436): online

## Resolution
Declared upstream pipeline failure after 2 restarts. The backend cannot sustain port binding — likely the inference pipeline crashes during startup, which takes down the server socket.

## Lesson
When `perceive logs` returns stale cached data (timestamps days/weeks old) right after a fresh startup, the pipeline is not actually working. The stale data is from a cache, not live inference. If the next `perceive logs` call fails or times out, the pipeline has collapsed. Do not wait for it to "warm up" — it won't.
