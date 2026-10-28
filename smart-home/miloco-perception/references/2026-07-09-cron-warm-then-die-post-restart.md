# 2026-07-09 Cron — Warm-Then-Die Post-Restart Recovery

## Scenario
- Pre-run script timed out ("获取感知日志超时")
- Diagnosis: true container-level hang (both pct exec AND lxc-attach hanging on echo HELLO)
- Recovery: container stop/start → supervisord restart → health OK at 30s

## Key Observation: First Query Succeeds, Then Collapses

Timeline after container recovery:
1. `pct exec echo` → OK (container alive)
2. supervisord started directly (not via miloco-cli service start)
3. Health check: exit code 7 at 15s → OK at 30s (normal 30s binding delay)
4. `miloco-cli perceive logs --since 30m --limit 5 --jsonl` → **SUCCESS** — 5 entries with FRESH timestamps (05:24–05:42 UTC, same day), real observations (前院, 北院, 三楼书房)
5. `miloco-cli perceive devices` → timeout (30s)
6. `miloco-cli perceive logs --limit 1` → timeout (30s)
7. `curl -s http://127.0.0.1:1810/health` via pct exec → timeout (15s)
8. `pct exec echo` → still works (container alive, miloco backend dead)

## What's Different from Existing Patterns

| Existing Pattern | This Session |
|---|---|
| E+ (2026-07-06): First query returns stale cached data (total_inferences: 0) → collapses | First query returns FRESH data (total_inferences > 0, same-day timestamps) → collapses |
| Post-restart pipeline failure (2026-07-08): ALL CLI commands timeout from the start | First query succeeds with real inference data, subsequent queries fail |
| Progressive degradation (existing pitfall): "running perceive logs when pipeline is broken causes degradation" | Pipeline was briefly WORKING (produced real inferences), then died |

## Diagnosis

The pipeline produced at least 5 fresh inferences (real scene descriptions with timestamps within 30m), confirming it was genuinely running. But it could not sustain — collapsed within ~60s of the first successful query.

This is NOT a "stale cache" issue. The data was fresh and real. The pipeline started, ran briefly, then the backend process became unresponsive (health check timed out, port likely dropped).

## Implications

1. **First successful query does NOT confirm pipeline stability** — even fresh, real data can be followed by collapse
2. **Do not assume recovery is complete just because first perceive logs returns fresh data** — verify with a second query 30-60s later
3. **Query ordering may matter** — the first `perceive logs --since 30m --limit 5 --jsonl` succeeded, but `perceive devices` (supposed to be fast) triggered or coincided with collapse. Possibly the `perceive devices` query loaded additional backend resources that destabilized the fragile pipeline.
4. **This counts as a failed restart** — the pipeline did not sustain. If this was the first restart attempt, a second attempt (nuclear restart or container stop/start) is warranted. If second attempt also fails, declare upstream failure per restart budget.

## Recovery Path
- Used 1 restart (container stop/start). Pipeline briefly worked then collapsed.
- Did NOT attempt second restart — sufficient data was captured for the cron job's purpose (no people detected, light-on-in-empty-room observation).
- In general: if pipeline collapses after brief success, treat as failed restart #1. Try nuclear restart as #2. If that also fails, stop and report upstream issue.
