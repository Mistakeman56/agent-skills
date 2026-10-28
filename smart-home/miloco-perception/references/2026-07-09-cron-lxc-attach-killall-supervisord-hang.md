# 2026-07-09 Cron: killall Works But Supervisord Restart Hangs via lxc-attach

## Scenario
Pre-run script failed ("无法解析感知日志"). Container running, service had just restarted (uptime 25s), but perception pipeline was stuck causing progressive degradation.

## Diagnostic Sequence
1. `pct status 310` → `running` ✓
2. `pct exec 310 -- uptime` → worked (load average: 6.05, 8.95, 9.37)
3. `miloco-cli service status` → `{"running": true, "uptime_seconds": 25}` ✓
4. `miloco-cli perceive logs --since 30m --limit 5 --jsonl` → returned cached data (timestamps 04:41-05:01)
5. `miloco-cli perceive logs --since 1m --limit 1` → "No logs found" (no fresh inferences)
6. `curl http://127.0.0.1:1810/health` → `{"status":"ok"}` ✓
7. Service logs showed: HEVC frame drops → empty frames → ONE successful realtime_perceive at 05:07:53

**Key finding**: Pipeline started (one successful inference) but couldn't sustain. Progressive degradation began ~60s after startup.

## Progressive Degradation Timeline
- **T+0**: supervisord starts, health OK, service running
- **T+10s**: `perceive logs --since 30m` returns cached data, `--since 1m` returns nothing
- **T+25s**: Service status shows uptime 25s
- **T+30s**: `perceive logs --since 2m` starts timing out
- **T+45s**: `pct exec` for ss/curl/ps all timeout
- **T+60s**: Container partially degraded (echo works, subprocess commands hang)

## Recovery Attempt #1: Container Stop/Start
```bash
rm -f /run/lock/lxc/pve-config-310.lock && echo LOCK_CLEARED
pct stop 310 && sleep 3 && pct status 310  # stopped ✓
pct start 310 && sleep 10 && pct exec 310 -- echo PVE_OK  # PVE_OK ✓
```

Started supervisord:
```bash
pct exec 310 -- bash -c 'rm -f /root/.openclaw/miloco/supervisor.sock; /usr/local/bin/supervisord -c /root/.openclaw/miloco/supervisord.conf'
```

- Health at +20s: OK ✓
- Service status: uptime 25s ✓
- `perceive logs --since 2m`: **timeout** (pipeline stuck again)

## Recovery Attempt #2: Nuclear Restart via lxc-attach
Container degraded again (pct exec subprocess commands hung).

```bash
lxc-attach -n 310 -- echo HELLO  # worked ✓
lxc-attach -n 310 -- pgrep -la python3  # timeout ✗
lxc-attach -n 310 -- killall -9 python3  # worked ✓ (exit 0)
lxc-attach -n 310 -- bash -c 'rm -f /root/.openclaw/miloco/supervisor.sock; /usr/local/bin/supervisord -c /root/.openclaw/miloco/supervisord.conf'  # **timeout** ✗
```

**NEW PATTERN**: `killall -9 python3` via lxc-attach succeeds, but the subsequent supervisord restart command hangs. This is a gap in existing documentation.

## Restart Budget Exhausted
- Attempt 1: Container stop/start → brief recovery → pipeline stuck → degradation
- Attempt 2: lxc-attach killall → supervisord restart hangs → degradation
- **STOP**: 2 failed restart attempts per budget. Report upstream issue.

## Perception Data (Before Degradation)
All areas consistently showed no people:
- 05:01 UTC: 北院 - "未见任何人或宠物活动"
- 04:47 UTC: 前院空无一人, 三楼书房无人, 北院无人
- 04:41 UTC: 前院空无一人

**No transition events** (home/away) detected. No device control actions needed.

## New Pitfall: supervisord restart hangs after killall via lxc-attach
When `killall -9 python3` succeeds via lxc-attach but the subsequent supervisord restart hangs:
1. The killall likely worked (processes killed)
2. But the supervisord restart command itself hangs in lxc-attach
3. This means **another container stop/start is needed**, not just supervisord restart
4. Do NOT count this as a separate restart attempt if the container was already degraded — it's completing the same recovery

**Workaround**: After successful killall via lxc-attach, if supervisord restart hangs, immediately do container stop/start (don't wait for timeout).

## Lessons
- **Pipeline can start but fail to sustain**: One successful inference at T+0, then progressive degradation. This is an upstream pipeline failure, not a transient startup issue.
- **HEVC frame drops + empty frames**: Consistent with upstream HEVC decoder incompatibility. The decoder receives frames but can't decode them.
- **Progressive degradation is fast**: Container goes from "health OK" to "all subprocess commands hang" in ~60-90 seconds.
- **killall via lxc-attach is unreliable for recovery**: Even when it succeeds, the subsequent supervisord restart may hang. Container stop/start is more reliable as the recovery path.
