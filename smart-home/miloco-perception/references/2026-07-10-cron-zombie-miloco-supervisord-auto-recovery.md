# 2026-07-10 Cron: Zombie miloco.main + Supervisord Auto-Recovery

## Symptoms
- PVE host load 15.04, miloco.main at 119% CPU
- `pct exec 310` timed out, `lxc-attach -n 310 -- echo HELLO` timed out
- `lxc-attach -n 310 -- pgrep -la python3` worked (partial hang — pgrep succeeds, echo/pidof don't)
- pgrep output: `58936 [python3] <defunct>` — miloco.main is a zombie
- `lxc-attach -n 310 -- pgrep -la supervisord` returned: `18424 /usr/bin/python3 /usr/local/bin/supervisord ...` — supervisord running
- `lxc-attach -n 310 -- pgrep -la miloco` returned: two stuck `miloco-cli service start` processes (PIDs 64780, 64791)

## Diagnosis
- Supervisord is alive and running
- miloco.main is dead (zombie/defunct)
- Stuck miloco-cli processes from pre-run retry pileup are blocking supervisord from restarting miloco.main

## Recovery (no nuclear restart needed)
```bash
# Kill only the stuck miloco-cli processes
sshpass -p "<PASSWORD>" ssh root@192.0.2.10 \
  "lxc-attach -n 310 -- kill -9 64780 64791 2>/dev/null"

# Wait for supervisord to auto-restart miloco.main
sleep 15

# Verify
sshpass -p "<PASSWORD>" ssh root@192.0.2.10 \
  "lxc-attach -n 310 -- pgrep -la python3"
# Should show fresh miloco.main (non-defunct) + supervisord

# Verify health
sshpass -p "<PASSWORD>" ssh root@192.0.2.10 \
  "lxc-attach -n 310 -- curl -s --connect-timeout 5 http://127.0.0.1:1810/health"
```

## Result
- After killing stuck CLI processes, supervisord auto-restarted miloco.main (new PID 64795)
- Health check passed at 15s
- Fresh perception logs available with `--since 30m --jsonl`
- PVE host load began decreasing

## Key Insight
**When supervisord is already running, killing stuck miloco-cli processes is sufficient for auto-recovery.** This is faster and less disruptive than:
- Full nuclear restart (kill supervisord + miloco.main + CLI + clear socket + restart supervisord)
- Container stop/start (Scenario A)

The stuck miloco-cli processes were from the pre-run script retry pileup — they're children of lxc-attach/pct exec wrappers, not supervised by supervisord, so supervisord couldn't kill them automatically.

## When This Pattern Applies
1. `pgrep` shows `<defunct>` miloco.main (zombie) — supervisord failed to reap it
2. `pgrep` shows supervisord is still running
3. Stuck miloco-cli processes visible alongside

## When This Pattern Does NOT Apply
- If supervisord is NOT running → need nuclear restart or container stop/start
- If miloco.main is not a zombie (just stuck in D state or high CPU) → different scenario
- If killing stuck processes doesn't trigger supervisord auto-restart → escalate to nuclear restart
