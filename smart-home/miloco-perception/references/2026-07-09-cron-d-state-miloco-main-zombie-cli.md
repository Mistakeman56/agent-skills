# 2026-07-09 Cron: D-State miloco.main + Zombie CLI

## Symptom
Pre-run script timed out ("获取感知日志超时"). `pct exec` hanging on all commands. `lxc-attach` echo works, `ps aux` works.

## Diagnostic Signature (via `lxc-attach -- ps aux`)
```
root   324   Ss   supervisord -c .../supervisord.conf
root   38919 S    bash -c miloco-cli service start 2>&1
root   38922 S    /usr/bin/python3 /usr/local/bin/miloco-cli service start
root   38933 D    /usr/bin/python3 -m miloco.main
```

Key observations:
- **miloco.main in D state** (Uninterruptible Sleep) — not dead, not in R state, stuck on I/O
- **zombie `miloco-cli service start`** — S state, from a previous failed start attempt
- **supervisord alive** (PID 324) but port 1810 NOT listening
- `ss -tlnp | grep 1810` returns empty (port unbound)
- `curl http://127.0.0.1:1810/health` returns exit code 7 (connection refused)

## Recovery
PID-targeted kill via `lxc-attach`:
```bash
lxc-attach -n 310 -- kill -9 324 38919 38922 38933
lxc-attach -n 310 -- bash -c 'rm -f /root/.openclaw/miloco/supervisor.sock && /usr/local/bin/supervisord -c /root/.openclaw/miloco/supervisord.conf'
```
Wait 15s → health OK → perception logs returned fresh data (total_inferences > 0).

## Notes
- D-state miloco.main kill -9 succeeded despite D state (I/O was likely stale/broken, not actively blocking signals)
- This is a B/B+ hybrid: port unbound (B characteristic) + zombie CLI present (B+ characteristic)
- The existing skill's PID-targeted nuclear restart path handles this correctly
- Fresh inferences appeared immediately after recovery (14:25-14:38 timestamps), no warm-then-die observed

## Differentiation from other scenarios
- **vs B0 (backend dead)**: ps aux shows miloco.main present (in D state), not absent
- **vs B (port unbound, no zombies)**: zombie CLI start process is present
- **vs D (perceive logs pileup)**: D-state is on miloco.main itself, not on spawned CLI processes
- **vs E/E+ (stale pipeline)**: port was never bound — backend never started accepting connections
