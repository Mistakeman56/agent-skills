# 2026-07-09: True container-level hang — pgrep confirms diagnosis

## Scenario
Pre-run script timeout. `pct exec` hung. `lxc-attach echo` also hung. `pgrep -la python3` via lxc-attach **also** hung. Confirmed true container-level hang (not partial hang, not miloco deadlock).

## Diagnostic Sequence
1. `pct status 310` → `running` (fast, <2s)
2. `pct exec 310 -- echo HELLO` → timeout (20s)
3. `lxc-attach -n 310 -- echo HELLO` → timeout (20s)
4. `lxc-attach -n 310 -- pgrep -la python3` → timeout (20s)

**Key distinction**: In partial hang scenarios, pgrep works even when ps aux hangs (see 2026-07-09-cron-pgrep-over-ps-aux.md). When pgrep ALSO hangs, it's a true container-level hang — all process inspection is impossible, so PID-targeted kills are ruled out. Container stop/start is the only option.

## Recovery
1. **Preemptive lock file clear** (zero-cost, prevents `pct stop` timeout):
   ```bash
   sshpass -p "<PASSWORD>" ssh root@192.0.2.10 "rm -f /run/lock/lxc/pve-config-310.lock"
   ```
2. Container stop/start:
   ```bash
   pct stop 310 && sleep 3 && pct status 310  # verify stopped
   pct start 310 && sleep 10 && pct exec 310 -- echo PVE_OK  # verify exec works
   ```
3. Start miloco (NOT via `miloco-cli service start`):
   ```bash
   pct exec 310 -- bash -c 'rm -f /root/.openclaw/miloco/supervisor.sock; /usr/local/bin/supervisord -c /root/.openclaw/miloco/supervisord.conf'
   ```
4. Wait for health:
   - 15s: health check failed (exit code 7)
   - ~30s: health check succeeded → `{"status":"ok"}`

## Outcome
- Service running, uptime 46s
- All 3 cameras online (三楼书房, 前院, 北院)
- Fresh inference at 10:19 AM Beijing time
- No home/away events — user at desk in 三楼书房

## Timing Calibration
- Health check after container restart: took **30s** (not 20s as previously observed)
- This extends the documented upper bound from 20s to 30s
- Per the skill: "After a container restart, port binding can take up to 20-30s" — this session confirms the 30s end

## Recovery Classification
Clean Scenario A recovery — true container-level hang, all access methods unresponsive, container stop/start with supervisord restart. No restart budget consumed (this was the only recovery attempt).
