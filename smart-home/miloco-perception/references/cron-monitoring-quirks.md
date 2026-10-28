# Cron Monitoring Quirks — Miloco Perception

## Issue: Initial CLI Command Error

When running `pct exec 310 -- miloco-cli ...` directly, the command may fail with:
```
lxc-attach: 310: ../src/lxc/attach.c: lxc_attach_run_command: 1845 No such file or directory - Failed to exec "miloco-cli"
```

**Root cause**: The `pct exec` command does NOT inherit the container's full PATH. Even if `miloco-cli` is at `/usr/local/bin/miloco-cli`, `pct exec` may not find it without explicit path.

**Fix**: Always use the full path:
```bash
pct exec 310 -- /usr/local/bin/miloco-cli <command>
```
OR set PATH inline:
```bash
pct exec 310 -- bash -c 'export PATH=/usr/local/bin:$PATH; miloco-cli <command>'
```

**Note**: The skill's existing "Correct CLI Subcommands" section documents the correct command names (`perceive logs` not `perception log`), but the PATH issue is a separate concern that can cause false "command not found" errors even with the right subcommand name.

## Issue: Backend Not Listening on Port 1810

The miloco-backend process may be running (visible in `ps aux`) but NOT listening on port 1810.

**Diagnostic steps**:
1. Check process: `pct exec 310 -- ps aux | grep miloco`
2. Check port: `pct exec 310 -- ss -tlnp | grep 1810`
3. Check logs: `pct exec 310 -- tail -20 /root/.openclaw/miloco/log/miloco-backend.log`

**Common cause**: Backend crashed during initialization (e.g., ONNX model loading error). The log will show "Server is ready" and "Uvicorn running on http://0.0.0.0:1810" when healthy.

**Recovery**: The supervisord should auto-restart. If not:
```bash
pct exec 310 -- /usr/local/bin/miloco-cli service restart
```

## Issue: Script Timeout vs Manual Success

The pre-run script may report "感知日志超时" even when the system is healthy. This is often a transient SSH/network issue during cron execution.

**Resolution**: Retry manually with explicit timeouts. The perception engine may have recovered by the time you check.

## Perception Log JSONL Format

When using `--jsonl` flag, output format is:
```
<ISO timestamp>: {<JSON object>}
```

The JSON object maps area names (前院, 北院, 三楼书房, etc.) to human-readable descriptions.

**Example**:
```
2026-07-14T12:43:11+00:00: {"前院": "前院夜晚，一名女子坐在椅子上进食..."}
```

**Time conversion**: Timestamps are UTC+0. Beijing time = UTC+8. So `12:43 UTC` = `20:43 北京时间`.
