# 2026-07-15 Cron: Container Hung Without Zombies, Supervisord Not Auto-Started

## Timeline

1. Pre-run script timed out getting perception logs
2. `pct exec 310 -- echo hello` hung (30s+ timeout)
3. `pct status 310` returned "running" — container appeared healthy
4. No zombie lxc-attach processes found
5. No lock holders found
6. `pct stop 310 && sleep 5 && pct start 310` succeeded
7. After restart: supervisord NOT running, miloco-backend NOT started
8. `miloco-cli service start` not tried first — used manual supervisord:
   ```
   supervisord -c /root/.openclaw/miloco/supervisord.conf
   ```
9. supervisord started miloco-backend, port 1810 bound after ~15s
10. `miloco-cli perceive logs --since 30m` returned 7 events successfully

## Key Observations

- **Scenario C confirmed**: Container hung without zombies or locks. `pct reboot 310` was NOT attempted (would likely hang too).
- **Supervisord did NOT auto-start**: Consistent with degraded restart behavior. The container was fully stuck (not just partially hanging), so auto-start didn't trigger.
- **Manual supervisord worked**: `supervisord -c supervisord.conf` started cleanly, backend came up. This is the fallback path documented in ct310-recovery.md.
- **PATH issue**: `supervisord` and `supervisorctl` are at `/usr/local/bin/` which is NOT in default PATH inside CT <ID>. Must use `export PATH=/usr/local/bin:$PATH` or full path.
- **Perception logs were fine after recovery**: 7 events in last 30m, all from 三楼书房 and 前院/北院 cameras. No "回家" or "离家" events detected.

## Recovery Command Sequence (for reference)

```bash
# 1. Stop/start container
sshpass -p "<PASSWORD>" ssh root@192.0.2.10 \
  "pct stop 310 && sleep 5 && pct start 310"

# 2. Wait for boot
sleep 10

# 3. Start supervisord directly (not miloco-cli service start)
sshpass -p "<PASSWORD>" ssh root@192.0.2.10 \
  "pct exec 310 -- bash -c 'export PATH=/usr/local/bin:\$PATH; cd /root/.openclaw/miloco; supervisord -c supervisord.conf 2>&1; sleep 5; supervisorctl -c supervisord.conf status 2>&1'"

# 4. Wait for backend init
sleep 15

# 5. Verify
sshpass -p "<PASSWORD>" ssh root@192.0.2.10 \
  "pct exec 310 -- bash -c 'export PATH=/usr/local/bin:\$PATH; miloco-cli perceive logs --since 30m --pretty 2>&1'"
```

## Perception Events (for context)

All events were routine — no action needed:
- 三楼书房: 无人, 灯亮着 (07:29-07:41 Beijing time)
- 前院: 一名男子走过 (07:44)
- 北院: 三辆车停放, 无人 (07:46)
- 前院: 空无一人 (07:49-07:57)

Note: 三楼书房灯亮着但无人 was noted as a potential energy-saving action, but not urgent for early morning.
