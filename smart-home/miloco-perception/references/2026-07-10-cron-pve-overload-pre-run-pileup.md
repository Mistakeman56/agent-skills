# 2026-07-10 19:50 — PVE Host Overload + Pre-Run CLI Pileup

## Timeline
- 19:50 — Pre-run script timeout ("获取感知日志超时")
- 19:50 — Agent diagnostic: PVE reachable, `pct exec echo HELLO` works, but `uptime`/`ls`/`ps aux` all hang → **partial pct exec hang**
- 19:50 — `lxc-attach uptime` also hangs → **partial lxc-attach hang**
- 19:50 — PVE host `uptime`: load average **16.39, 11.63, 9.58** → critically overloaded
- 19:50 — PVE host `ps aux --sort=-%cpu | head -15` revealed:

| Process | %CPU | %MEM | Notes |
|---------|------|------|-------|
| `miloco.main` (python3) | **116%** | 12.5% | Main perception backend |
| `miloco-cli service start` | 14.2% | 0.0% | Stuck (pre-run or agent diagnostic) |
| `miloco-cli perceive logs --limit 10` | 13.5% | 0.0% | D state, stuck |
| Minecraft server (java) | 13.4% | 40.4% (6.5GB) | Long-running since Jul06 |
| `miloco-cli perceive logs --limit 1` | 13.2% | 0.0% | R state, stuck |
| `miloco-cli perception logs --limit 20` | 12.6% | 0.0% | R state, stuck (wrong subcommand!) |
| `miloco-cli device list` | 11.4% | 0.0% | R state, stuck |
| `miloco-cli --help` | 11.2% | 0.0% | R state, stuck |
| supervisord | 10.3% | 0.0% | Running normally |

## Root Cause
Two compounding issues:
1. **miloco.main at 116% CPU** — perception backend consuming excessive CPU (possibly stuck in inference loop or processing heavy load)
2. **Pre-run retry pileup** — the cron pre-run script spawned multiple `miloco-cli` processes that got stuck. The agent's own diagnostic attempts (pct exec → lxc-attach → miloco-cli perceive logs × N) piled up MORE stuck processes on top. Each stuck CLI process consumed 10-14% CPU.

The combined CPU load from miloco.main + 6+ stuck CLI processes + Minecraft server pushed PVE host load to 16.39, which caused ALL container commands (pct exec, lxc-attach) to hang — even `uptime` and `ps aux`.

## Key Learning
- **PVE host-level `ps aux --sort=-%cpu`** is the critical diagnostic when container commands hang — it shows the full picture across all CTs/VMs without needing container access
- The `perception logs` (noun) command was attempted — wrong subcommand, should be `perceive logs` (verb). This generated stuck processes that contributed to the pileup
- When PVE load >15, stop all container-level diagnostics immediately — each additional probe makes the overload worse
- Minecraft server (CT100) is a persistent resource consumer (6.5GB RAM, 13.4% CPU) that should be considered when evaluating total PVE load

## Recovery Recommendation
Container stop/start (not nuclear restart — too many piled-up CLI wrappers for PID-targeted kills to be effective):
```bash
sshpass -p "<PASSWORD>" ssh root@192.0.2.10 "rm -f /run/lock/lxc/pve-config-310.lock && pct stop 310 && sleep 3 && pct start 310"
# Wait 30s for supervisord auto-start + backend initialization
sleep 30
# Verify
sshpass -p "<PASSWORD>" ssh root@192.0.2.10 "pct exec 310 -- bash -c 'export PATH=/usr/local/bin:\$PATH; curl -s http://127.0.0.1:1810/health'"
```
