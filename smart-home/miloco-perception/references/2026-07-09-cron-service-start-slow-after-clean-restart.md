# 2026-07-09: miloco-cli service start slow but works after clean container restart

## Context
Container CT <ID> was hung (`pct exec` hanging for all commands including `echo hello`).

## Recovery Sequence
1. `pct status 310` → `running` (container alive but unresponsive)
2. `rm -f /run/lock/lxc/pve-config-310.lock` → cleared lock file
3. `pct stop 310` → succeeded (exit 0)
4. `pct start 310` → succeeded, status confirmed `running`
5. Waited 8s → `pct exec 310 -- echo hello` → worked (exit 0)
6. `miloco-cli perceive logs --since 30m --limit 20` → "cannot connect to Miloco backend"
7. `miloco-cli service status` → `{"running": false}` — backend not running
8. `miloco-cli service start` → **timed out at 20s** (exit 124)
9. Checked `miloco-cli service logs` → saw initialization progress (ORT models loaded, cameras connecting, supervisord started)
10. Waited 15s → `miloco-cli service status` → `{"running": true, "uptime_seconds": 43}`
11. `miloco-cli perceive logs --since 30m --limit 20` → 12 fresh entries, `total_inferences: 1`

## Key Finding
After a **clean** container stop/start (not degraded), `miloco-cli service start` CAN succeed — it just takes 40+ seconds and the CLI times out at 20s. The service starts in the background while the CLI is waiting. Checking `service logs` during the timeout shows initialization progress (models loading, cameras connecting, home-scene subscriptions syncing).

## Service logs during startup
```
ORT session loaded (human_body_reid_v2.onnx)
backfill_reid_embeddings done
Application startup complete
Uvicorn running on http://0.0.0.0:1810
[multicam] cameras connected
device-meta subscriptions synced: +68 -0
home-scene subscriptions synced: +1 -0
RuleRunner init, rules: 5
EventEmbedder loaded (bge-small-zh-v1.5-int8.onnx)
```

## Perception logs after recovery
12 entries over 30 minutes. Areas: 北院 (parked cars, no people), 前院 (empty, wet ground), 三楼书房 (user present — sitting at computer, using phone). `total_inferences: 1` — pipeline had just started inferring.

## Duration from container restart to working perception logs: ~45 seconds
- Container restart: 0s
- `pct exec` functional: +8s
- `service start` attempted: +8s (timed out at 20s)
- Service running: +43s
- Perception logs working: ~45s

## Implication for skill
The existing pitfall "Do NOT use miloco-cli service start — it almost always hangs" is too strong for clean container restarts. The command works but needs 40+ seconds. Supervisord direct path is still more reliable, but `service start` is a valid fallback when you can see initialization progress in `service logs`.
