# Miloco Service Restart — Incident Log (2026-07-05)

## Problem
Perception log fetch timed out. Pre-run script reported:
```
⚠️ 获取感知日志超时，PVE/CT <ID> 可能不可达
```

## Diagnosis
1. PVE host (192.0.2.10) was reachable (ping OK)
2. CT <ID> container accessible via `pct exec 310`
3. `miloco-cli perception log` failed → wrong subcommand (should be `perceive logs`)
4. After correcting command: `{"error": "cannot connect to Miloco backend at http://127.0.0.1:1810"}`
5. `ps aux` showed miloco process running (PID 942419, started 12:03)
6. `ss -tlnp | grep 1810` → **port not listening** despite process running
7. `curl http://127.0.0.1:1810/health` → connection failed

## Root Cause
Miloco backend process was alive (supervisord-managed) but the HTTP server on port 1810 was not bound — likely a hung/zombie state where the Python process exists but the server socket never bound or was released.

## Fix Applied
```bash
miloco-cli service stop   # killed PID 942429
sleep 2
miloco-cli service start  # spawned new PID 943117
```

## Verification
- Port 1810 bound: `LISTEN 0 2048 0.0.0.0:1810` (PID 943117)
- Health check: `{"status":"ok"}`
- Logs fetched successfully: 10 entries returned, latest from 2026-06-24

## Note on Log Freshness
Logs returned were from June 24 (11 days old). The perception engine may not be actively generating new inferences — cameras may be disconnected or inference pipeline paused. Worth monitoring in future runs.
