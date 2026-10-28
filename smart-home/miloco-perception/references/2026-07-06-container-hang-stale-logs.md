# 2026-07-06: Container Hang + Stale Perception Logs

## Timeline
- **Pre-check**: Cron job's pre-run script timed out fetching perception logs
- **Diagnosis**: `pct status 310` → running, but `pct exec 310 -- uptime` hung
- **CT <ID> IP**: Discovered as `192.0.2.10` via DHCP lease lookup
- **SSH to CT <ID>**: Timed out (port 22 unreachable from PVE host)
- **First fix attempt**: `pct stop 310 && pct start 310` — container restarted
- **After restart**: `miloco-cli service start` succeeded, health OK, but `pct exec` commands hung again within minutes
- **Second fix**: Full container stop → start → longer wait → service start
- **Result**: Service stable, health OK, but perception logs stuck at June 24 (12 days stale)

## Key Findings
1. `pct exec` hanging = container-level issue, not just miloco service
2. Container restart does NOT auto-start miloco service
3. `supervisord -c ...` inside pct exec exits with code 7 ("Failed to connect to host") — misleading error; the command actually works but supervisord daemonizes
4. Perception logs returning quickly ≠ logs being current; always check the `t` timestamp
5. `perceive query` can hang even when health is OK and logs return

## Camera Status
All 3 cameras online as of restart:
- 三楼监控 (1180976594) — 三楼书房
- 小米智能室外摄像机 4 Pro 三摄变焦版 (1179415436) — 前院
- 北院摄像头 (1176694677) — 北院

## Unresolved
- Perception inference pipeline not generating new entries despite service running
- Last inference: 2026-06-24T17:30:01+00:00
- Possible causes: model API issue, camera feed processing stuck, perception task misconfiguration
