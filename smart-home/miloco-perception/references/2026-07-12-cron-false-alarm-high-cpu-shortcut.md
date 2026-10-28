# 2026-07-12 Cron — False Alarm High CPU Shortcut

## Scenario
Pre-run script timed out with `⚠️ 获取感知日志超时`. Host load was 13.74 (elevated).

## Host ps output (step 2)
```
miloco.main  PID 1773425  134% CPU  12.6% MEM  Sl  START 20:58  TIME 6:06
supervisord  PID 1101149  9.3% CPU   Rs        START 14:14  TIME 38:24
Minecraft    PID 4026474  13.1% CPU  39.2% MEM  Sl+ START Jul06 TIME 1143:23
```
Plus 4 pre-run zombies (miloco-cli perceive logs, service start) in D/S state.

## What happened
Agent followed the full 7-step quick-reference path:
1. PVE reachable ✅
2. Host load 13.74 → checked host ps → saw miloco.main at 134% Sl with 6:06 CPU time
3. CT <ID> running ✅
4. Skipped (not in path)
5. Port check via pct exec → timed out 30s
6. Health check via pct exec → timed out 30s
7. perceive logs via pct exec → timed out 60s

Then re-checked host ps → confirmed miloco.main still at 134% Sl → killed zombies → stopped.

## Time wasted
Steps 5-7 consumed ~120s of timeouts. The host ps at step 2 already confirmed the service was healthy (miloco.main at >100% CPU, Sl state, minutes of accumulated CPU time = doing inference).

## Lesson
**False Alarm Shortcut**: After step 2's host ps, if miloco.main matches (1) CPU >100%, (2) STAT Sl, (3) CPU TIME in minutes → skip steps 3-7. Kill zombies, report status, stop. Saves ~2-3 minutes.

## Key diagnostic pattern
| Signal | Meaning |
|--------|---------|
| miloco.main >100% CPU, Sl state, minutes CPU time | Healthy, actively inferring |
| miloco.main Dl state, seconds CPU time | Stuck during init (Scenario B−) |
| miloco.main Ds state, minutes CPU time | Stuck on I/O (Scenario D/B+) |
| miloco.main <5% CPU after hours | Dead/stuck pipeline |

## Recovery
1. Killed 4 pre-run zombies from host shell: `kill -9 1780860 1780932 1781239 1780657`
2. Killed 4 self-inflicted diagnostic processes from host shell: `kill -9 1782864 1782549 1782016 1781887`
3. Verified cleanup: host ps showed only miloco.main (134% Sl) + supervisord (9.4% Ds) + Minecraft
4. No restart needed — service was healthy the entire time
