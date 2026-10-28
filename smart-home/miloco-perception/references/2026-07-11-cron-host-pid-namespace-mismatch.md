# 2026-07-11 Cron: Host PID Namespace Mismatch

## Summary
Pre-run script timed out ("获取感知日志超时"). Diagnosed and recovered successfully.

## Key Discovery: Host vs Container PID Namespace

When running `ps aux --sort=-%cpu` on the PVE host, container processes appear with **host-level PIDs**:
```
100000   2691778  146 12.7 5403480 2048100 ?     Sl   11:57   9:12 /usr/bin/python3 -m miloco.main
100000   2701471  17.5  0.0  12388  1048 ?        R    12:02   0:13 /usr/bin/python3 /usr/local/bin/miloco-cli perceive logs --limit 1
100000   2701627  16.8  0.0   3940   292 ?        R    12:02   0:10 bash -c miloco-cli perceive logs --limit 10 2>/dev/null
100000   2701904  16.3  0.0  12388   656 ?        R    12:03   0:04 /usr/bin/python3 /usr/local/bin/miloco-cli service start
```

When running `pct exec 310 -- ps aux | grep miloco`, the **same processes** appear with different PIDs:
```
root       37072  0.0  0.4  30944 10412 ?        Ss   03:06   5:48 /usr/bin/python3 /usr/local/bin/supervisord
root      101598  0.0  0.0  3940   256 ?        S    04:02   0:11 bash -c miloco-cli service start 2>&1
root      101603  0.0  1.6  42064 35576 ?        S    04:03   0:17 /usr/bin/python3 /usr/local/bin/miloco-cli service start
root      101610  0.0  0.1 42064  136756 ?      Sl   04:05   0:01 /usr/bin/python3 -m miloco.main
```

## What Happened
1. Host-level ps showed stuck miloco-cli processes at PIDs 2701471, 2701627, 2701904, 2701344, 2700992
2. Attempted `pct exec 310 -- kill -9 2701471 2701627...` → all "No such process"
3. Ran `pct exec 310 -- ps aux | grep miloco` → got different PIDs (101598, 101603, 101610)
4. Attempted kill of 101598, 101603 → also "No such process" (processes had already died between ps and kill)
5. Final ps showed only supervisord (37072) + miloco.main (101610) — clean state
6. Successfully retrieved perception logs

## Resolution
The stuck miloco-cli processes from pre-run retry pileup resolved themselves (likely timed out and exited). The service was functional after the pileup cleared.

## Perception Data Retrieved
- Timestamps: 03:36-03:43 UTC (cached, total_inferences: 0)
- 三楼书房: 无人, 灯亮着
- 北院: 白色SUV + 黑色轿车, 无人
- 前院: 空无一人
- No home/away transitions detected

## PVE State at Time of Check
- Load average: 11.22, 9.23, 8.77 (elevated but functional)
- miloco.main: 146% CPU (host-level view)
- Minecraft server: 13.3% CPU, 39.8% MEM (6.4GB)
- Container status: running
