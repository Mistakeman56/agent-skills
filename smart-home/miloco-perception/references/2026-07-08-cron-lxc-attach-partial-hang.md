# 2026-07-08 Cron: lxc-attach Partial Hang → Container Stop/Start

> **Note**: This reference covers the case where `ps aux` ALSO hangs (can't find PIDs → container stop/start is the only option). For the case where `ps aux` works but `ss`/`curl` hang (can find PIDs → PID-targeted nuclear restart preferred), see `references/2026-07-08-cron-mis-escalation-to-container-stop.md`.

## Scenario
Pre-run script timed out ("获取感知日志超时"). PVE reachable, CT <ID> running, but pct exec hanging for all commands.

## Diagnostic Sequence
1. `pct status 310` → `running` (fast, <2s)
2. `pct exec 310 -- bash -c 'ss -tlnp | grep 1810'` → timeout (20s)
3. `pct exec 310 -- bash -c 'curl -s --connect-timeout 5 http://127.0.0.1:1810/health'` → timeout (20s)
4. `lxc-attach -n 310 -- echo HELLO` → **worked** (returned "HELLO")
5. `lxc-attach -n 310 -- bash -c 'curl -s --connect-timeout 5 http://127.0.0.1:1810/health'` → timeout (15s)
6. `lxc-attach -n 310 -- bash -c 'ss -tlnp | grep 1810'` → timeout (15s)
7. `lxc-attach -n 310 -- pgrep -la python3` → timeout (15s)
8. `lxc-attach -n 310 -- ss -tlnp` → timeout (15s)

**Key finding**: lxc-attach passes trivial commands (`echo`) but hangs on anything that spawns a subprocess or does I/O. This is the same "partial hang" pattern documented for pct exec, but now observed for lxc-attach too.

**Decision**: Can't find PIDs (pgrep hangs) → PID-targeted kills impossible → container stop/start is the only option, even though lxc-attach partially works.

## Why PID-targeted kills don't work here
The existing decision tree says "lxc-attach basic commands work → Container alive but miloco deadlocked → kill stuck processes by PID". But this assumes `ps aux` or `pgrep` works to find PIDs. In this session:
- `echo HELLO` → works ✓
- `pgrep -la python3` → hangs ✗
- `ps aux` → hangs ✗
- `ss -tlnp` → hangs ✗

Without process listing, PID-targeted kills are impossible. Container stop/start is the correct path.

## Recovery
```bash
pct stop 310 && sleep 3 && pct status 310  # → stopped ✓
pct start 310 && sleep 10 && pct exec 310 -- echo PVE_OK  # → PVE_OK ✓
```

Then start miloco service:
```bash
pct exec 310 -- bash -c 'rm -f /root/.openclaw/miloco/supervisor.sock; /usr/local/bin/supervisord -c /root/.openclaw/miloco/supervisord.conf'
```

Health check timing:
- ~15s after supervisord: exit code 7 (failed)
- ~30s after supervisord: `{"status":"ok"}` ✓

## Post-recovery perception logs
- `perceive logs --since 30m --limit 10 --pretty`: 7 entries, `total_inferences: 1`
- Latest entry: 三楼书房, person at computer with headphones
- 前院/北院: no people
- Snapshot interpretation (total_inferences: 1) → no device control action

## Lessons
- **lxc-attach exhibits the same partial hang pattern as pct exec**: trivial commands work, subprocess-spawning commands hang. Test with `ps aux` before trusting lxc-attach.
- **If you can't list processes, you can't do PID-targeted kills** — regardless of whether echo works. Go straight to container stop/start.
- **Port binding after container restart takes ~30s**, not 8-10s. Check health at 20s AND 30s intervals.
- **Snapshot vs transition**: total_inferences: 1 = post-restart snapshot, not a transition event. Don't trigger device control.
