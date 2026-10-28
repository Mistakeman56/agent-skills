# Perception Logs for Cron Jobs — Patterns

## Fetching Recent Logs

```bash
# Get last 1h of logs (standard cron check)
sshpass -p "<PASSWORD>" ssh -o StrictHostKeyChecking=no root@192.0.2.10 \
  "pct exec 310 -- bash -c 'export PATH=/usr/local/bin:$PATH; miloco-cli perceive logs --since 1h --limit 20 2>&1'"
```

**Flags:**
- `--since 1h` — relative time window (supports h/m/s/d, combos like `2h30m`)
- `--limit N` — cap number of returned logs
- `--jsonl` — one JSON object per line (for agent parsing)
- `--pretty` — human-readable formatting

## Health Check

```bash
curl -s http://127.0.0.1:1810/health
# Returns: {"status":"ok"} when backend is up
```

**After restart**, the backend takes ~30s to come up. Retry the health check before fetching logs.

## Common Failure: Backend Not Responding

```
{"error": "cannot connect to Miloco backend at http://127.0.0.1:1810"}
```

**Cause:** supervisord is running but backend process hasn't started yet, or backend crashed.

**Fix:** Wait for startup or restart:
```bash
miloco-cli service start 2>&1
```

## Log Structure

Each log entry has:
- `id` — UUID
- `t` — ISO timestamp (UTC)
- `d` — dict of `{area: description}` where:
  - Keys: area names (前院, 北院, 三楼书房, etc.)
  - Values: natural-language description of camera observations

**No structured "event type" field** — must parse descriptions for 回家/离家 patterns.
