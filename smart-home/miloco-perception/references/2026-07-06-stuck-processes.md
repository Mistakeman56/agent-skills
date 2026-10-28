# Miloco Service Restart — Incident Log (2026-07-06)

## Problem
Pre-run cron job timed out: `⚠️ 获取感知日志超时，PVE/CT <ID> 可能不可达`

## Diagnosis Steps
1. **Ping PVE**: OK (0.035ms avg) — host is reachable
2. **SSH port check**: `nc -z -w5 192.0.2.10 22` → open
3. **SSH connect + pct status**: `pct status 310` → `running` (fast, succeeds)
4. **SSH + pct exec miloco-cli perceive logs**: HANGS (25s+ timeout)
5. **SSH + pct exec curl health**: Initially also HANGS (20s timeout)
6. **SSH + pct exec ss + ps**: Found the issue

## Root Cause
Multiple `miloco-cli perceive logs` processes stuck in R/D state:
- `miloco-cli perceive logs --limit 1` (PID 1376786, R state, 30:12 CPU time!)
- `miloco-cli service start` (PID 1376788, R state, started 18:08)
- `miloco-cli perceive logs --limit 5` (PID 1376789, R state, started 18:09)
- `miloco-cli perceive logs --limit 5` (PID 1376790, D state — uninterruptible!)
- Plus 3 more stuck processes

**This is a DIFFERENT failure mode from 2026-07-05**: Port 1810 was listening, supervisord was running, but the perception CLI commands were hung in a zombie pileup. The previous incident had port 1810 not listening at all.

## Fix Applied
```bash
miloco-cli service stop    # returned {"code":0,"message":"stopped","pid":null}
sleep 2
miloco-cli service start   # spawned new supervisord + miloco.main
```

## Verification
- Health check: `{"status":"ok"}` (responded immediately)
- `perceive logs --limit 3`: returned 3 entries successfully
- `perceive devices`: returned 3 cameras, all online

## Observations
- Logs still from 2026-06-24 (12 days stale) — same as 07-05 incident
- The perception engine appears to lose its inference state on restart, reverting to the last cached data
- Cameras are online but no fresh inferences are being generated
- Worth monitoring whether new logs appear after the next perception cycle

## Key Diagnostic Commands (add to skill)
```bash
# Fast pre-check (avoids hanging on pct exec)
pct status 310

# Stuck process detection
ps aux | grep miloco | grep -v grep
# Look for: many miloco-cli perceive logs entries, high CPU time, R/D state

# Quick connectivity test (works even when logs hang)
miloco-cli perceive devices
```
