# Cron Job Pre-Run Script Debugging

## Problem

The cron job for Miloco perception monitoring includes a pre-run script that collects perception events. When it fails, the cron job reports "获取感知日志超时，PVE/CT <ID> 可能不可达" — but the actual cause may be different.

## Common Failure Modes

### 1. Wrong CLI Subcommand (Most Common)

The cron job prompt may reference `miloco-cli perception events` — this is NOT a valid subcommand. The CLI accepts it silently and hangs forever (no error, no timeout).

**Correct command**: `miloco-cli perceive logs --limit N`

**Diagnosis**: If the script times out but PVE/CT <ID> are reachable, try running the correct command directly:

```bash
sshpass -p "<PASSWORD>" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=8 root@192.0.2.10 \
  "pct exec 310 -- timeout 12 /usr/local/bin/miloco-cli perceive logs --limit 5 2>&1 || echo COMMAND_FAILED"
```

**Key pitfall**: The CLI does NOT reject invalid subcommands with an error — it just hangs. You must use `--help` or check the subcommand list to verify.

### 2. PATH Not Including /usr/local/bin

In the CT <ID> container, `which miloco-cli` may fail even though `/usr/local/bin/miloco-cli` exists. Always use the full path:

```bash
❌ miloco-cli perceive logs
✅ /usr/local/bin/miloco-cli perceive logs
```

Or export PATH explicitly:
```bash
export PATH=/usr/local/bin:$PATH
```

### 3. High Container Load

CT <ID> may have high load (e.g., 15.30, 12.03, 10.41) from `miloco.main` inference. This causes all `pct exec` commands to be slow. Check load first:

```bash
sshpass -p "<PASSWORD>" ssh -o ConnectTimeout=5 root@192.0.2.10 "pct exec 310 -- uptime"
```

If load > 10, CLI commands may timeout even with correct syntax. Wait for inference to complete.

### 4. Stale Perception Logs

Even with the correct command, logs may be days/weeks old. The default `perceive logs` (without `--since`) uses a cursor that may be stale after restarts. Always use `--since`:

```bash
❌ miloco-cli perceive logs --limit 5       # May return 3-week-old events
✅ miloco-cli perceive logs --since 24h --limit 5  # Guaranteed recent window
```

## Diagnostic Sequence

When the pre-run script fails:

1. **Check PVE reachability**: `ping -c 2 192.0.2.10`
2. **Check CT <ID> basic responsiveness**: `pct exec 310 -- uptime`
3. **Check container load**: If load > 10, wait for inference
4. **Try the correct CLI command with full path**: `pct exec 310 -- timeout 12 /usr/local/bin/miloco-cli perceive logs --since 1h --limit 5`
5. **If CLI hangs**: Check backend status, read log files directly

## Correct Full Command for Cron Jobs

```bash
sshpass -p "<PASSWORD>" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=8 root@192.0.2.10 \
  "pct exec 310 -- bash -c 'export PATH=/usr/local/bin:\$PATH; export MILOCO_TOKEN=95ac63403f1f45a38f66f72bd085b27b81c2352c3f1546f991c03c07f3f7a082; miloco-cli perceive logs --since 1h --limit 10 2>&1'"
```

Note: `\$PATH` escaping is required when nesting bash -c inside pct exec.
