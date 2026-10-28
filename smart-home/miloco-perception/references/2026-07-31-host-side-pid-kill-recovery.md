# Host-side PID Kill — Recovery When Both pct exec AND lxc-attach Hang

**Date**: 2026-07-31 cron session

## Scenario
- Pre-run script: `⚠️ 获取感知日志超时`
- PVE host reachable (ping 0% loss), but load average 11-13 (high)
- CT <ID> `pct status`: running; `cat /proc/loadavg` works (12.07) — container alive
- `pct exec` partial hang: `cat`/`test -f` work, but `ls`, `pgrep`, `supervisorctl`, `curl`, `miloco-cli` all return nothing/hang
- `lxc-attach -n 310 -- bash -c ...` also times out
- Host-side `ps aux --sort=-%cpu` revealed the picture: miloco.main backend spinning at 111% CPU with 2.0GB RSS (hot loop / memory-leak pattern), plus 3 stuck `miloco-cli` processes in D/R state (`perceive logs --limit 1`, `service start`, `perceive logs --limit 10`) piled up from the pre-run script and a hung service start

## Root cause pattern
Same as Scenario C (D-state startup loop) but manifesting as **progressive degradation** — the spinning backend + piled-up stuck miloco-cli processes drove load to 13+, making every subprocess-spawning pct exec/lxc-attach command hang.

## Fix — kill from the PVE host (most reliable in partial-hang state)

LXC container processes are visible on the PVE host under UID `100000`. The host was fully responsive even while the container was degraded.

```bash
# 1. Identify container processes from the host
sshpass -p "<PASSWORD>" ssh root@192.0.2.10 \
  "ps aux --sort=-%cpu | grep -E 'miloco' | grep -v grep"

# 2. Kill specific PIDs (backend + stuck cli processes), never blanket killall
sshpass -p "<PASSWORD>" ssh root@192.0.2.10 \
  "kill -9 2769550 2783215 2783582 2784118; sleep 3; ps aux --sort=-%cpu | grep -E 'miloco|python3' | grep -v grep | head -8"

# 3. supervisord survives (it's a python3 process but not targeted) and
#    auto-respawns miloco.main within seconds
```

## ⚠️ Pitfalls
1. **Do NOT `killall -9 python3` from the host** — CT <ID> hosts many unrelated python3 services (supervisord, Home Assistant `python3 -m homeassistant`, ha-mcp, Playwright, MCP servers). Always kill specific PIDs.
2. **Avoid `pkill -9 -f miloco-cli`** — the `-f` flag matches your own ssh command line (contains "miloco-cli" if you use the wrapper), killing your session (exit 137).
3. **`miloco-cli service status` fails with `FileNotFoundError: 'supervisorctl'` via bare `pct exec`** — supervisorctl is in `/usr/local/bin`, not in the minimal pct exec PATH. This is a CLI PATH quirk, NOT a service failure. Verify with `curl -s http://localhost:1810/health` → `{"status":"ok"}` or `/usr/local/bin/supervisorctl -c /root/.openclaw/miloco/supervisord.conf status`.

## Recovery timeline (2026-07-31)
```
23:37  Pre-run timeout flagged; host ping OK, load 11.59
23:41  Host ps: backend 111% CPU / 2.0GB RSS + 3 stuck miloco-cli (D/R)
23:43  Host-side kill -9 of backend + stuck processes
23:43  supervisord auto-respawns miloco.main (fresh PID)
23:44  curl health → {"status":"ok"}; host load dropping (13.25 → 8.93)
23:44  perceive logs → code 0, empty (no events during degraded window — expected)
```

## Lessons
- When pct exec AND lxc-attach both hang but the PVE host responds, **the host is the diagnostic and recovery path** — don't waste time inside the container.
- A fresh respawn + healthy `curl /health` is sufficient verification; the `service status` PATH quirk is noise.
- Post-recovery, `perceive logs` returns empty for the degraded window — that's expected, not a new failure.
