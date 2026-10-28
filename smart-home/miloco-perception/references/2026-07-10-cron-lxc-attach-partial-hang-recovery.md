# 2026-07-10 — Scenario A Container Hang + lxc-attach Partial Hang Recovery

## Timeline
- Cron pre-run script timeout (感知日志超时)
- PVE reachable: OK
- CT <ID> status: `running`
- `pct exec 310 -- uptime`: 15s timeout → pct exec broken
- `lxc-attach -n 310 -- echo HELLO`: OK (fast)
- `lxc-attach -n 310 -- pgrep -la python3`: 15s timeout
- `lxc-attach -n 310 -- bash -c 'ss -tlnp | grep 1810'`: 15s timeout
- lxc-attach partial hang (echo works, subprocess commands hang)
- Container stop/start + supervisord restart: success
- Health check #1 (~15s): exit code 7 (failed)
- Health check #2 (~30s): {"status":"ok"} ✓
- perceive logs --since 30m --limit 20 --jsonl: 8 fresh entries, total_inferences > 0

## Key Observation: lxc-attach Partial Hang
Unlike the 2026-07-08 session (where lxc-attach also hung for echo), this session showed the classic lxc-attach partial hang: echo HELLO succeeds but pgrep, ss, ps aux all hang. The skill correctly identifies this as a container stop/start situation (PID-targeted kills impossible without process info).

Diagnostic pattern: After pct exec hangs, always probe lxc-attach with echo FIRST, then pgrep/ss. If echo works but pgrep hangs → partial hang → escalate to container stop/start (same as true hang, since you cannot get PIDs).

## Perception Logs Analysis
Timestamps: 2026-07-09T22:02-22:29 UTC
- 三楼书房: person sleeping in bed (red underwear → striped blanket, 翻身)
- 北院: two people near vehicles at 22:20 (red top walking toward white SUV, another by dark car)
- 前院: empty
- No clear home/away transition events → no device control needed

## Recovery Path
Standard Scenario A path — lxc-attach partial hang → container stop/start → supervisord → health at 30s.
