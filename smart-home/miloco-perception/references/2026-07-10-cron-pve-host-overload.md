# 2026-07-10: PVE Host Overload Causes All pct exec to Hang

## Summary
Pre-run script timeout → manual investigation → PVE host load 19.91 → all pct exec commands timeout → CT <ID> unreachable via CLI → perception logs unavailable.

## Key Finding
**PVE HOST load** (not container load) was 19.91/16.76/16.23. This caused ALL `pct exec 310` commands to hang indefinitely, including trivial ones like `echo hello`. Even `pct reboot 310` timed out.

## Diagnostic Sequence
1. `ping 192.0.2.10` — OK (0.05ms RTT)
2. `ssh ... "pct status 310"` — OK (`status: running`)
3. `ssh ... "pct exec 310 -- echo hello"` — TIMEOUT (30s)
4. `ssh ... "uptime"` — load average: 19.91, 16.76, 16.23

## Distinction from Container-Level Load
- Container load affects commands INSIDE CT <ID> (perceive logs slow, miloco-cli hangs)
- PVE host load affects the `pct exec` WRAPPER itself — even passing through commands to a healthy container fails
- Container can be perfectly healthy but unreachable due to PVE host overload

## Resolution
No resolution possible from agent side. PVE host needs manual investigation:
- Check which process/VM/container is consuming CPU
- May need to restart the offending workload
- Miloco perception monitoring is offline until PVE load normalizes

## Lesson
Add PVE host load check to the quick-reference diagnostic path — it should come BEFORE container-level checks when pct exec hangs for all commands.
