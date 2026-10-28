# 2026-07-11 Cron — Rapid Warm-Then-Die (15s Collapse)

## Scenario
- Pre-run script timed out ("获取感知日志超时")
- PVE reachable, load 13.15 (elevated but functional)
- CT <ID> running but pct exec/lxc-attach partially hanging
- miloco.main at 134% CPU (consistent across restarts)

## Recovery Attempts (2 total — budget exhausted)

### Attempt 1: Container Stop/Start
1. Lock file cleared → container stopped → started
2. supervisord started manually (service status: running=false)
3. Health OK at 30s
4. First query: `perceive logs --since 5m --limit 3 --jsonl` → **SUCCESS** — 3 fresh entries
   - 02:21 UTC: 北院, no people
   - 02:25 UTC: 前院, man squatting by wall cleaning
5. Second query 15s later → **TIMEOUT** (collapse)
6. Container degraded again (pct exec hanging)

### Attempt 2: Container Stop/Start
1. Same recovery sequence
2. Health OK at 30s
3. First query: `perceive logs --since 5m --limit 3 --jsonl` → **SUCCESS** — 3 fresh entries
4. Second query 15s later → **TIMEOUT** (collapse)
5. Restart budget exhausted → reported upstream failure

## Key Observation: 15-Second Collapse Window

Previous warm-then-die references (2026-07-09) documented collapse within ~60s. This session showed collapse in **~15 seconds** — significantly faster.

Timeline:
- T+0s: First query succeeds (fresh data, total_inferences > 0)
- T+15s: Second query times out
- T+30s: Health check times out
- T+45s: pct exec hanging

This suggests the pipeline can collapse much faster than previously documented. The "30-60s" window may be an upper bound; the actual collapse time depends on the underlying failure mode.

## Diagnostic Signal: Persistent High miloco.main CPU

| Restart | miloco.main CPU | Outcome |
|---|---|---|
| Before restart 1 | 134% | Pipeline collapsed |
| After restart 1 | 129% | Pipeline collapsed |
| After restart 2 | 129% | Pipeline collapsed |

The consistent >129% CPU across multiple container restarts is a strong indicator of upstream pipeline failure. When miloco.main runs hot (>100% CPU) AND the pipeline collapses after brief success, the inference process is likely stuck in a computation loop or doing excessive redundant work.

**Contrast with healthy high CPU**: In the 2026-07-10 incident, miloco.main at 123% CPU was NOT the cause — it was doing legitimate inference. The difference: in that case, the pipeline sustained (produced logs for 14+ minutes before pileup). Here, the pipeline collapses within 15s despite the CPU load.

## Perception Data Captured Before Collapse

| Time (UTC+8) | Area | Observation |
|---|---|---|
| 09:51 | 北院 | Two cars parked, no people |
| 10:10 | 前院 | Man in white short-sleeve, black shorts, standing at workbench |
| 10:21 | 北院 | No people, same cars |
| 10:25 | 前院 | Man squatting by wall, cleaning, water stains and metal basin |

No "回家" or "离家" transition detected — ongoing activity by what appears to be a family member.

## Implications

1. **Warm-then-die can be faster than documented** — verify stability with queries spaced 30-60s apart, not just one success
2. **Persistent high miloco.main CPU (>129%) across restarts = upstream failure signal** — don't keep restarting
3. **First query success is necessary but not sufficient** — always verify with a second query
4. **When both pct exec and lxc-attach partially hang** (echo works, subprocess commands hang) → container stop/start is the only option (PID-targeted kills impossible)
