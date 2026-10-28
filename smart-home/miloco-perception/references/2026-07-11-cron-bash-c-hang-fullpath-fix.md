# 2026-07-11 Cron: bash -c Hang, Full-Path Fix

## Symptom
Pre-run script failed with "⚠️ 无法解析感知日志:" (unable to parse perception logs).

## Investigation
Agent tried `pct exec 310 -- bash -c 'export PATH=/usr/local/bin:$PATH; miloco-cli perceive logs ...'` — hung for 30s+ repeatedly. Container was responsive (`pct exec 310 -- echo ok` worked, `pct status 310` showed `running`).

## Root Cause
The `bash -c` wrapper inside `pct exec` intermittently hangs, even when the container is alive and responsive to direct commands. This is a known but undocumented pattern.

## Fix
Switched to direct full-path execution:
```bash
pct exec 310 -- /usr/local/bin/miloco-cli perceive logs --since 2h --limit 5 --pretty
```
This worked on first try — no `bash -c`, no PATH export needed.

## Key Commands That Worked
- `pct exec 310 -- echo ok` ✓
- `pct exec 310 -- id` ✓
- `pct exec 310 -- /usr/local/bin/miloco-cli perceive logs --since 2h --limit 5 --pretty` ✓
- `pct exec 310 -- /usr/local/bin/miloco-cli perceive logs --since 1h --limit 5 --pretty` ✓

## Commands That Hung
- `pct exec 310 -- bash -c 'export PATH=/usr/local/bin:$PATH; miloco-cli ...'` ✗ (30s timeout)
- `pct exec 310 -- find /usr/local/bin -name 'miloco*'` ✗ (30s timeout)
- `pct exec 310 -- ls /usr/local/bin/miloco*` ✗ (30s timeout)

## Perception Logs Retrieved
All areas empty at 10:58 local time. 三楼书房灯亮着 but无人. Agent recommended turning off三楼灯 (DID: 2042769877).

## Transient "cannot connect" Error
`miloco-cli perceive logs --since 30m` failed with "cannot connect to Miloco backend at http://127.0.0.1:1810" once, but port 1810 was confirmed listening via `ss -tlnp`. Retry succeeded — this is the documented transient connection failure pattern.
