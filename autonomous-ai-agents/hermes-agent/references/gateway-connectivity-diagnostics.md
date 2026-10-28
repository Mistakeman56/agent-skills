# Gateway Connectivity Diagnostics

## Symptom: Messaging platform (WeChat/Telegram/Discord) disconnects repeatedly

User reports "connection dropped" or "can't reach you". Gateway appears to restart multiple times.

## Diagnostic Flowchart

### Step 1: Check gateway logs for SIGTERM/restart events
```bash
grep -a "SIGTERM\|signal\|exit" ~/.hermes/logs/gateway.log | tail -20
```
Look for: `Received SIGTERM — initiating shutdown` with `loadavg_1m=` values.

### Step 2: Check system load
```bash
uptime
# or
cat /proc/loadavg
```
- loadavg > 2× CPU cores = overloaded
- loadavg > 10 on a 2-core system = critical

### Step 3: Check what's consuming resources
```bash
ps aux --sort=-%cpu | head -15
ps aux --sort=-%mem | head -15
```
Common culprits:
- Multiple MCP compressor processes (each ~85MB RAM, spawns child processes)
- brightdata MCP keepalive retry loops
- SSH connections to remote servers hanging

### Step 4: Check for DNS resolution failures
```bash
grep -a "name resolution\|Temporary failure" ~/.hermes/logs/errors.log | tail -10
```
High load can cause DNS resolver timeouts → WeChat API (`ilinkai.weixin.qq.com`) unreachable.

### Step 5: Check MCP server health
```bash
grep -a "keepalive failed\|initial connection failed" ~/.hermes/logs/errors.log | tail -20
```
Failed MCP servers in retry loops consume CPU and spawn zombie processes.

### Step 6: Check for crash details (advanced)
```bash
# Check exit diagnostics
cat ~/.hermes/logs/gateway-exit-diag.log | tail -30

# Check shutdown diagnostics (shows process tree at crash time)
cat ~/.hermes/logs/gateway-shutdown-diag.log | tail -30
```

### Step 7: Check systemd service configuration
```bash
cat /etc/systemd/system/hermes-gateway.service | grep -E "Restart|Timeout|KillMode"
```
Key settings:
- `RestartForceExitStatus=75` — systemd will restart on exit code 75
- `KillMode=mixed` — kills process group, not just main process
- `TimeoutStopSec=210` — allows 3.5 minutes for graceful shutdown

### Step 8: Check container resources (if running in LXC)
```bash
# From PVE host
pct config <VMID> | grep -E "memory|cores|swap"

# From inside container
free -h
nproc
```

### Step 9: Check PVE host for OOM kills
```bash
# From PVE host
journalctl -k --since "today" | grep -i "oom\|killed"
```
OOM kills affect the entire host, not just the container.

## Root Cause: System load spikes → systemd kills gateway

When system load exceeds thresholds, systemd's watchdog (or resource limits) sends SIGTERM to the gateway process. The gateway shuts down, WeChat disconnects. If systemd restarts it but load is still high, it gets killed again → cycle of connect/disconnect.

**Typical trigger:** Too many MCP servers running simultaneously, especially with `mcp-compressor` wrapping (each server spawns compressor + child process = 2-3 processes per MCP server).

**Key insight:** High loadavg does NOT always mean high CPU usage. Common pattern:
- CPU usage: 0-2% per process (low)
- Load average: 10-16 (very high)
- Root cause: Many processes in I/O wait or uninterruptible sleep (SSH connections, MCP initialization)

## Fix

### Immediate: Reduce MCP server count
```bash
# Check which MCPs are actually needed
hermes mcp list

# Disable unused ones in config.yaml
# Move them to a comments section or remove from mcp_servers
```

### Immediate: Kill stuck MCP processes
```bash
# Find zombie/retry loops
ps aux | grep -E "brightdata|cloakbrowser" | grep -v grep
kill <pid>  # kill stuck processes
```

### Immediate: Check if broken MCP is still in config
```bash
grep -n "brightdata\|mcp_servers" ~/.hermes/config.yaml | head -20
```
If MCP is not in config but still running, it's a leftover process from a previous config.

### Preventive: Disable broken MCP servers
If an MCP server is permanently broken (e.g. expired API key, 欠费), disable it in config.yaml to stop the retry loop from consuming resources.

### Preventive: Monitor load
```bash
# Add to crontab for early warning
*/5 * * * * uptime | awk -F'load average:' '{print $2}' | awk -F, '{if($1>8) print "LOAD WARNING:", $0}' >> /var/log/load-warning.log
```

## Verification after fix
```bash
# Confirm gateway is stable
grep "weixin connected" ~/.hermes/logs/gateway.log | tail -5
# Should show ONE connection, not multiple reconnect/disconnect cycles

# Confirm load is reasonable
uptime
# Should show loadavg < 2× CPU cores

# Confirm no MCP retry loops
grep -a "keepalive failed" ~/.hermes/logs/errors.log | tail -5
# Should show nothing or very old entries
```

## Container Resource Assessment Pattern

When diagnosing gateway issues, check if container resources are the bottleneck:

```bash
# 1. Check container allocation
pct config <VMID> | grep -E "memory|cores|swap"

# 2. Check actual usage
pct exec <VMID> -- free -h
pct exec <VMID> -- nproc

# 3. Check host available resources
ssh root@PVE_HOST "free -h && nproc"

# 4. Decision matrix
# If container RAM < 2GB and 11+ MCP servers → increase RAM
# If container cores < 4 and high load → increase cores
# If container has enough but load still high → reduce MCP count
```

**Typical resource allocation for Hermes with 11 MCP servers:**
- RAM: 6-8GB (MCP processes use ~85MB each × 11 = ~1GB + gateway + overhead)
- Cores: 4-6 (enough for parallel MCP initialization)
- Swap: 2-4GB (safety net)

## Related Pitfalls
- **Cron job trigger gateway self-destruction**: A cron job that tries `systemctl restart hermes` from within the gateway process kills the gateway + the restart command in the same cgroup. Never restart gateway from inside gateway.
- **Sideline daemons die with gateway cgroup**: Any process launched from gateway (sidecar relays, watchers) dies when gateway is killed. Run them as separate systemd services.
- **MCP process count vs resource usage**: Each MCP server spawns 2-3 processes (compressor + SSH + actual server). 11 MCP servers = 30+ processes. High process count causes high loadavg even if CPU usage is low.
- **DNS resolution under high load**: When loadavg > 10, DNS resolver may timeout, causing WeChat API (`ilinkai.weixin.qq.com`) to be unreachable. This is a symptom of high load, not a DNS configuration issue.
- **Leftover processes after config removal**: Removing an MCP from config.yaml doesn't kill already-running processes. They continue consuming resources until manually killed or gateway restarts.
