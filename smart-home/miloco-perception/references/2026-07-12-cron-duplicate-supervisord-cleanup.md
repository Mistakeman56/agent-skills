# 2026-07-12 Morning Cron — Duplicate Supervisord + Host-Level Cleanup

## Scenario
Pre-run script timed out. PVE host load 16.67 (>15 threshold). All `pct exec` commands hung.

## Root Cause
1. Pre-run script spawned multiple stuck `miloco-cli` processes (pileup)
2. Two supervisord processes running simultaneously (both PID 537149 and 537153 started at 07:54)
3. Each supervisord spawned its own miloco.main → duplicate miloco.main processes (PID 600431 at 78.5% CPU + PID 602969 at 47.5% CPU)

## Recovery Path (host-level only — pct exec hung)

### Step 1: Kill stuck CLI processes from host shell
```bash
sshpass -p "<PASSWORD>" ssh root@192.0.2.10 "kill -9 <CLI_PIDs>"
```
Killed: 609293, 607998, 607024, 610728, 610981, 611175, 611308, 611375, 610710

### Step 2: Check for duplicate supervisord + miloco.main
After CLI cleanup, `ps aux` revealed:
- PID 600431: miloco.main (81.2% CPU, original)
- PID 611984: NEW miloco.main (11.2% CPU, spawned by duplicate supervisord)
- PID 537149: supervisord (original)
- PID 537153: supervisord (duplicate — killed)

### Step 3: Kill duplicate supervisord + its spawned miloco.main
```bash
sshpass -p "<PASSWORD>" ssh root@192.0.2.10 "kill -9 611984 537153"
```

### Step 4: Verify
Load dropped from 16.67 → 12.22. Only 1 supervisord + 1 miloco.main remained.
Perception logs retrieved successfully after 15s wait.

## Key Learning
- **Two supervisord processes**: Can arise from concurrent recovery attempts. Both start their own miloco.main. Kill the duplicate supervisord (less CPU time = duplicate) and its miloco.main child.
- **Host-level kill works for container processes**: Container processes (UID 100000) visible in host `ps aux` are killable from host shell with `kill -9`.
- **Wrong subcommand `perception`** visible in host ps pileup — pre-run script bug contributes to pileup.

## Perception Data After Recovery
- total_inferences: 4 (warm-up phase)
- 三楼书房: person sleeping throughout
- 前院: shirtless man appeared ~08:29, sitting on chair
- 北院: vehicles parked, no people
- No home/away transition events — multiple people home
