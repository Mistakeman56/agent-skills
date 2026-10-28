# 2026-07-10 Cron — `ss -tlnp | grep 1810` False Negative

## Summary
Pre-run script timed out. During manual diagnosis, `ss -tlnp | grep 1810` via `pct exec` returned empty (exit code 1), suggesting port 1810 was not listening (Scenario B). However, running `ss -tlnp` without grep revealed the port WAS listening on PID 154995. The backend was healthy (`{"status":"ok"}`).

## Timeline
- `02:00` UTC — CT <ID> load: 12.69, 13.59, 14.89
- `pct exec 310 -- uptime` → success (load 12.69)
- `pct exec 310 -- bash -c 'ss -tlnp | grep 1810'` → empty output, exit code 1
- `pct exec 310 -- bash -c 'ss -tlnp'` → port 1810 LISTEN on PID 154995
- `pct exec 310 -- bash -c 'curl -s --connect-timeout 5 http://127.0.0.1:1810/health'` → `{"status":"ok"}`
- `miloco-cli perceive logs --since 30m --limit 10 --pretty` → 10 fresh entries, total_inferences: 1

## Root Cause
Pipe through `pct exec` can corrupt or reformat `ss` output such that `grep` fails to match. The port was healthy the entire time. High container load (12.69) may contribute to output timing/buffering issues in the pct exec wrapper.

## Lesson
When `ss -tlnp | grep 1810` returns empty via `pct exec`, verify with `curl` health check before assuming Scenario B. Piped grep through pct exec is unreliable for port binding checks.

## Perception Data Retrieved
- 01:45 UTC (09:45 Beijing): Person entered through glass door (home event)
- 01:46 UTC: Third vehicle (dark SUV) appeared in north yard
- 01:49 UTC: Study empty, patio empty
