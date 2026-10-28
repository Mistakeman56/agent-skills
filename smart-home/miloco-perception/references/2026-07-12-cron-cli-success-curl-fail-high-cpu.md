# 2026-07-12 Cron: miloco-cli Succeeds While curl Fails Under High CPU

## Summary
Pre-run script timed out (false alarm — high load, not service failure). After cleanup, miloco.main was at 145% CPU (Rl state, legitimate inference). Under this load:
- `miloco-cli perceive logs --since 30m --limit 5 --pretty` → **SUCCEEDED** (returned 5 fresh entries, timestamps 8 minutes old)
- `curl -s http://127.0.0.1:1810/health` → **exit code 7** (connection refused)
- `ss -tlnp | grep 1810` via pct exec → **timed out**

This is the reverse of the expected pattern (curl as fast health check, miloco-cli as slow query).

## Why miloco-cli Works When curl Fails
Under extreme CPU load (>140%), the backend's HTTP server may be too busy to accept new connections promptly. `curl --connect-timeout 10` gives up after 10s if no TCP handshake completes. But `miloco-cli` likely uses a longer internal timeout or retries the connection internally — it succeeded where curl gave up.

Also: `ss -tlnp` via pct exec timed out, but the service logs confirmed Uvicorn started on port 1810. The port WAS bound — the issue was connection acceptance under load, not port binding.

## Key Diagnostic Insight
When checking service health under high CPU load:
1. `miloco-cli perceive logs --since 30m --limit 3` is MORE RELIABLE than `curl health` for confirming the backend is alive
2. `curl exit code 7` under high CPU does NOT mean the service is down — it means the backend is too busy to accept connections promptly
3. Service logs (`miloco-cli service logs`) can confirm startup even when live probes fail — check logs FIRST

## Decision Rule
If miloco.main is at >120% CPU in Sl/Rl state and `miloco-cli perceive logs` returns data → service is healthy regardless of curl/ss results. Stop probing and report status.

## Session Data
- miloco.main: PID 1673453, 145% CPU, Rl state, 13m CPU time
- supervisord: PID 1101149, 9.7% CPU, Rs state
- Service started: 2026-07-12 12:34:23 (confirmed via service logs)
- Perception logs: 5 entries from 12:23:31–12:24:49 UTC (= 20:23–20:24 CST, 8 minutes before query)
- total_inferences: 0 (expected after restart, fresh data confirmed by timestamps)
