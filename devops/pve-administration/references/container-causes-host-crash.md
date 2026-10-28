# Container Causing PVE Host Crash — Cross-Level Debugging

## Scenario
A container (typically MC server with large JVM heap) consumes so much memory that the PVE host itself becomes unresponsive. All services degrade, web UI hangs, SSH times out.

## Symptoms in PVE Host Journal

When a container starves the host of memory, the PVE host journal shows a cascade of failures **before** the crash:

```
# 1. Memory pressure warnings (earliest sign)
systemd-journald: Under memory pressure, flushing caches.

# 2. Service timeouts
pvestatd: got timeout
pvestatd: status update time (590.168 seconds)   # 10 minutes for a status check!

# 3. HA agent lag
pve-ha-lrm: loop take too long (33 seconds)
pve-ha-lrm: loop take too long (59 seconds)

# 4. Firewall stalls (iptables/nftables lock contention under memory pressure)
pve-firewall: firewall update time (168.198 seconds)  # normally <1s

# 5. Scheduler lock failures
pvescheduler: replication: cfs-lock 'file-replication_cfg' error: got lock request timeout

# 6. Web proxy crash
pveproxy: Can't call method "unshift_read" on an undefined value at .../AnyEvent.pm line 1440.

# 7. SSH failures
sshd: Timeout before authentication for connection from ...
sshd-session: Connection closed by ... (before auth completes)
```

**Timeline from real incident (June 30, 2026):**
- 13:28 — firewall updates start slowing (34s)
- 13:29 — "Under memory pressure, flushing caches" begins
- 13:32 — scheduler lock timeout
- 13:35 — HA agent loop 59s
- 13:36 — firewall update 168s
- 13:38 — pvestatd status update 590s, pveproxy crashes
- 13:40 — SSH connections timeout
- System effectively dead, user had to hard-reboot

## Post-Mortem: Reading Pre-Crash Logs

After reboot, the live journal only contains post-boot entries. Pre-crash logs survive in **archived journal files**:

```bash
# List archived journals (files ending in .journal~ are pre-crash)
ls -la /var/log/journal/*/

# Key files:
# system@<timestamp>.journal     — current boot's journal
# system@<timestamp>.journal~    — previous boot's journal (CRASH SURVIVOR)
```

### Extracting pre-crash journal

```bash
# Find the most recent archived journal
ls -lt /var/log/journal/*/*.journal~ | head -3

# Copy to /tmp for analysis (journalctl --file needs read access)
cp /var/log/journal/*/system@<matching>.journal~ /tmp/crash.journal

# Search for memory/OOM events
journalctl --file=/tmp/crash.journal --no-pager | grep -i "oom\|memory pressure\|kill\|java" | tail -30

# Get the last 100 lines before the system died
journalctl --file=/tmp/crash.journal --no-pager | tail -100
```

### Checking reboot history

```bash
last reboot | head -5
# Look for "crash" status (vs clean "down" or "still running")
# Example:
# reboot   system boot  6.17.2-1-pve   Wed Jul  1 15:33 - still running
# reboot   system boot  6.17.2-1-pve   Mon Jun  8 21:17 - crash
```

### Checking container config for memory allocation

```bash
# Container memory vs JVM heap
grep -E 'memory|swap' /etc/pve/lxc/<VMID>.conf
pct exec <VMID> -- cat <server_dir>/user_jvm_args.txt | grep -E 'Xmx|Xms'

# Quick check: is JVM heap too close to container RAM?
# Rule: Xmx should be ≤ 75% of container memory
# Example: 10GB container → Xmx7G max (leave 3GB for OS + native)
```

## Prevention

### Memory Budget Rule
- **Container RAM** = JVM heap (Xmx) + OS overhead (1-2GB) + native memory (0.5-1GB)
- **Xmx ≤ 75% of container RAM** (not 80% — modded MC needs more headroom)
- **Total container allocations ≤ 80% of host physical RAM**

### Example Correct Sizing
| Host RAM | Container RAM | JVM -Xmx | Notes |
|----------|--------------|----------|-------|
| 16GB | 10GB | 6-7G | Safe — 3-4GB for OS |
| 16GB | 10GB | 8G | **Risky** — only 2GB for OS, will crash host |
| 32GB | 14GB | 10G | Comfortable |

### Monitoring
Add to the MC server's startup script or cron:
```bash
# Warn if container memory usage > 85%
pct exec <VMID> -- bash -c 'USED=$(free | awk "/Mem:/{print \$3/\$2*100}"); [ $(echo "$USED > 85" | bc) -eq 1 ] && echo "WARNING: CT<VMID> memory ${USED}% — risk of host crash"'
```

## Debugging Workflow (User-Corrected)

**⚠️ CRITICAL LESSON (fromassistant 2026-07-01):** When a container causes host-level issues, do NOT only check the container's logs. Check PVE host-level logs too.

**Correct workflow:**
1. Check container logs (MC latest.log, debug.log)
2. **Check PVE host journal** for memory pressure, OOM, service timeouts
3. **Check `last reboot`** for crash history
4. **Check archived journals** (`.journal~`) for pre-crash evidence
5. Compare container memory allocation vs JVM heap vs host RAM

**Wrong workflow (what I did first):**
- Only checked MC logs → found AllTheLeaks warnings but missed the host-level impact
- User had to tell me: "你不仅要看mc日志 他启动导致整个pve服务器都坏了 你应该看pve服务器日志"
