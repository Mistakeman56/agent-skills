# 2026-07-06 Morning Cron — Restart Budget Exhaustion

## Timeline
- Pre-run script failed to parse perception logs (backend down)
- `perceive logs --limit 5` → "cannot connect to Miloco backend at http://127.0.0.1:1810"
- `ps aux` showed: 2 supervisord processes, miloco.main, stuck `miloco-cli service start`, second miloco.main — classic Scenario D process pileup
- Port 1810 not bound

## Attempt 1: Nuclear Restart (Scenario D)
- `killall -9 supervisord` → `killall -9 python3` → sleep 3 → clear socket → supervisord start
- Result: health OK, port 1810 listening
- **But**: `perceive logs --limit 10` timed out after 45s
- **And**: `perceive devices --timeout 10` timed out after 30s
- Even `ps aux | grep miloco` started timing out after a few CLI attempts

## Attempt 2: Container Stop/Start (Scenario A)
- `pct stop 310` → `pct start 310` → `pct exec 310 -- echo PVE_OK` ✓
- Clear socket + supervisord start → health OK after 12s
- Process count clean: just supervisord + miloco.main (2 processes)
- **But**: `perceive logs` still timed out after 30s timeout wrapper
- **And**: `perceive devices` timed out after 15s timeout wrapper
- **Key observation**: after a few CLI attempts, even `ps aux` inside CT <ID> started hanging (container became unresponsive again)

## Decision: Stop per restart budget
After 2 failed attempts, stopped restarting per the hard budget rule.

## Diagnosis
Upstream pipeline failure (Scenario E). Service starts and reports healthy, but perception pipeline cannot produce fresh inferences. CLI commands cause progressive container degradation — possibly the CLI subprocesses enter uninterruptible sleep or block on I/O, exhausting container resources.

## New Pattern Observed: Progressive Degradation After Restart
After a successful container restart + health OK:
1. First few commands work (curl health, ps aux)
2. Running `perceive logs` or `perceive devices` causes them to hang
3. Subsequent commands (even `ps aux`) also start timing out
4. Container becomes effectively unresponsive

This suggests the `miloco-cli perceive` commands themselves trigger a blocking path in the backend that cascades to container resource exhaustion. The container isn't just "stuck" — it actively degrades when perception queries are attempted.

## Takeaway
When health passes but both `perceive logs` AND `perceive devices` hang, stop immediately. Do NOT retry with different timeout values or "wait longer" — it just makes the container progressively worse. The 2-restart budget correctly prevented further wasted attempts.
