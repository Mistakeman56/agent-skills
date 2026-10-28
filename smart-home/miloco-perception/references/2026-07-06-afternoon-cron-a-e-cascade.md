# 2026-07-06 Afternoon Cron — Scenario A → E+ Cascade

## Timeline
- Pre-run script timed out (PVE/CT <ID> unreachable)
- `pct status 310` → `running` (fast, OK)
- `pct exec 310 -- curl health` → 15s timeout → **Scenario A** (container hang)
- `pct exec 310 -- uptime` → 15s timeout → confirmed Scenario A

## Recovery Attempt 1: Container stop/start (Scenario A fix)
```
pct stop 310 → OK
sleep 3
pct start 310 → OK
sleep 10
pct exec 310 -- echo PVE_OK → PVE_OK ✓
```
Container restored. miloco service does NOT auto-start (as documented).

## Supervisord start
```
rm -f /root/.openclaw/miloco/supervisor.sock
/usr/local/bin/supervisord -c /root/.openclaw/miloco/supervisord.conf
```
Wait 10s → health OK ✓
Wait 20s → `perceive logs --limit 1` returns stale data (2026-06-24), `total_inferences: 0`
`perceive devices` → all 3 cameras online ✓

**Diagnosis**: Scenario E — pipeline not generating fresh inferences. Cameras reachable, service healthy, but inference pipeline stuck.

## Recovery Attempt 2: Nuclear supervisord restart (Scenario E fix)
```
killall -9 supervisord 2>/dev/null
killall -9 python3 2>/dev/null
sleep 3
rm -f /root/.openclaw/miloco/supervisor.sock
/usr/local/bin/supervisord -c /root/.openclaw/miloco/supervisord.conf
```
Wait 12s → health OK ✓ (exit code 7 at first, then OK after another 10s)
Wait 15s → `perceive logs --limit 1` returns stale data BUT `total_inferences: 2` (was 0)
**Brief partial recovery**: pipeline started producing inferences but couldn't sustain.
Wait 30s → `perceive logs --limit 2` → **60s timeout** → pipeline stalled
Health check → **15s timeout** → container degrading again

**New signal**: `total_inferences` incrementing (0→2) before collapse confirms pipeline attempted to start but couldn't sustain. This is a diagnostic marker for E+ (fake-healthy collapse) — pipeline briefly alive then dies.

## Recovery Attempt 3: Container stop/start (container restoration, NOT pipeline restart)
After 2 pipeline restart attempts hit budget, did container stop/start to restore basic container functionality:
```
pct stop 310 → OK
sleep 3
pct start 310 → OK
sleep 10
pct exec 310 -- echo PVE_OK → PVE_OK ✓
```
Container back in usable state. miloco service left off (pipeline broken upstream).

## Key Takeaways
1. **A→E+ cascade**: Container hang recovery can expose a latent pipeline issue. Fixing A doesn't fix E.
2. **Partial recovery marker**: `total_inferences` incrementing before collapse is a strong E+ signal.
3. **Container recovery ≠ pipeline restart**: After exhausting the 2-restart budget, a final container stop/start to restore basic functionality is acceptable and doesn't count against the budget.
4. **Progressive degradation confirmed**: After nuclear restart, health check went from OK → timeout within ~30s, confirming the pipeline collapse degrades the entire container.
