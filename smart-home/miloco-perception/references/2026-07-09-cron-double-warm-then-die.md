# 2026-07-09 Cron: Double Warm-then-Die Pattern

## Summary
Two consecutive container stop/start recoveries both produced the warm-then-die pattern. Pipeline briefly works (health OK, first query returns fresh data with total_inferences > 0), then collapses within ~60s. Restart budget exhausted after 2 attempts.

## Timeline
1. **Pre-run script timeout** — perception logs unreachable
2. **Initial diagnosis** — PVE reachable, CT <ID> container in true hang (pct exec + lxc-attach + pgrep all timeout)
3. **First recovery** — container stop/start + supervisord → health OK at 30s → first query returns fresh data (10 entries, total_inferences:1) → second query times out → health times out → collapse
4. **Second recovery** — container stop/start + supervisord → health OK at 20s → first query returns stale cached data (total_inferences:0) → second query times out → health times out → collapse
5. **Restart budget exhausted** — stopped per policy

## First Recovery — Fresh Data Observed
```json
{
  "logs": [
    {"t": "2026-07-09T13:34:55+00:00", "d": {"三楼书房": "一名男子坐在三楼书房的电脑桌前..."}},
    {"t": "2026-07-09T13:35:21+00:00", "d": {"前院": "前院地面潮湿...", "北院": "夜晚的北院...", "三楼书房": "一名男子坐在三楼书房的电脑椅上..."}},
    ...
  ],
  "total_inferences": 1
}
```
This was genuine inference output (not stale cache) — timestamps from today, real scene descriptions. But pipeline collapsed before second query.

## Second Recovery — Stale Cache Only
```json
{
  "logs": [{"t": "2026-07-09T13:59:35+00:00", "d": {"北院": "夜晚的北院..."}}],
  "total_inferences": 0
}
```
`total_inferences: 0` confirmed pipeline never started producing fresh inferences.

## Key Observations
- **Service logs were NOT gathered** before reporting — this was a gap. Should have run `miloco-cli service logs --limit 50` to capture HEVC drops, model API errors, or other root cause indicators.
- Both recoveries followed the same pattern: container hang → stop/start → brief health → collapse
- The pattern is consistent with upstream pipeline failure (not service failure)
- Container degradation was severe — even `pgrep` via lxc-attach timed out in both hang states

## Lesson
When hitting restart budget, ALWAYS gather service logs before reporting. The skill was updated to include this as a mandatory pre-reporting step.
