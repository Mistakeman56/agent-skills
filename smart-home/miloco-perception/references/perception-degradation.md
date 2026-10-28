# Perception Degradation & Auto-Restart Detection

## omni API 401 → Scene Understanding Skipped (partial degradation)

**Signature** in `/root/.openclaw/miloco/log/miloco-backend.log`:

```
httpx - INFO - HTTP Request: POST https://token-plan-cn.xiaomimimo.com/v1/chat/completions "HTTP/1.1 401 Unauthorized"
miloco.perception.engine.omni.omni - ERROR - [omni] omni API 调用失败，错误码=401 | {"error": {"message": "Invalid API Key", ...}}
miloco.perception.engine.pipeline - WARNING - [omni](room=北院 device=北院摄像头(1176694677)) 感知API调用失败，错误码=HTTPStatusError:401(skipped) | _call_omni_messages failed ...
```

**Meaning**: the omni (scene-understanding) LLM API key is invalid/expired. The engine does NOT crash — it degrades:
- `identity` (face recognition) keeps running — perf lines still log `identity=NNNNms`
- `HOLD_START`/`HOLD_END` presence events still fire — extract them with a bounded grep (this is the ONLY presence signal available when `realtime_perceive` lines are missing, e.g. during 401 degradation or right after a restart):
  ```bash
  pct exec 310 -- bash -c 'tail -6000 /root/.openclaw/miloco/log/miloco-backend.log | grep -E "HOLD_START|HOLD_END|presence" | tail -4'
  ```
  These are sufficient to answer "is someone home / in which room" for the cron's light-control decision. **HOLD_START with `hold_duration_sec=360` is a routine presence hold, NOT an arrival event — do not treat it as 回家 requiring lights.**
- Only the per-room omni scene description is skipped (`(skipped)`), so "who/what is happening in room X" events degrade

**Verify/fix**: startup log shows `KVRepo init, keys: [..., 'MIOT_TOKEN_INFO_KEY', ...]` — the credential lives in the KV store. Fix = update the omni API key, then restart backend (`miloco-cli service stop` then `service start`, or container cycle).

## Watchdog Self-Stall → Automatic Backend Restart

**Signature**: log contains `[watchdog] self-stall detected: NNN.Ns since last tick` (e.g. 371.4s), followed minutes later by a clean re-init at a NEW timestamp:

```
<ts> - miloco.database.kv_repo - INFO - KVRepo init, keys: ['DEVICE_UUID_KEY', 'HOME_WHITE_LIST_KEY', 'MIOT_TOKEN_INFO_KEY', 'USER_INFO_KEY']
<ts> - miot.i18n - INFO - init i18n, zh-Hans
<ts> - miot.lan - INFO - new device, ... (device online flood)
```

then `node_events.log` shows STARTING → READY → RUNNING_START for all modules (~15-20s later).

**Watchdog SIGKILL loop (no backend-log lines)**: When the backend restarts every ~2-3 min but the backend log has NO `[watchdog] self-stall` lines, check `/root/.openclaw/miloco/log/supervisord.log` — repeated `WARN exited: miloco-backend (terminated by SIGKILL; not expected)` + `spawned` entries at ~2-3 min intervals = watchdog kill loop. Observed 2026-08-01: correlated 1:1 with omni API 401 errors (key invalid since 18:23 UTC) — theory: omni 401 → inference retry hangs → watchdog self-stall kills process → supervisord respawns → loop. `grep -c "omni API 调用失败" miloco-backend.log` gives error count; `grep -c realtime_perceive` returning 0 means no perception events produced at all. A backend-level kill does NOT break the loop (still SIGKILLed 2-3 min later) — the durable fix is updating the omni API key (401 root cause), then restart.

**Cadence can start SLOW and ACCELERATE — do NOT wait for the 2-3 min cadence to call it a loop (observed 2026-08-01 morning)**: intervals were 35 min → 10 min → 4 min before escalation, and only the 4th PID change made it unambiguous. The reliable signature is: `supervisord` PID stays constant while `miloco.main` PID keeps changing across consecutive `ps -eo pid,stat,etime,cmd | grep miloco.main` checks. `grep -c "omni API 调用失败" miloco-backend.log` (566 on 2026-08-01) is the fast root-cause confirmation once the container is responsive again.

**Verified end-to-end escalation flow (2026-08-01 07:50–08:20 local)** — pre-run timeout `⚠️ 获取感知日志超时，PVE/CT <ID> 可能不可达` → host reachable (`uptime` instant) + `pct status 310` running → 15 stacked zombie PIDs across 3 cron chains (`perceive logs --limit 1`, `service start`, `perceive logs --limit 10`) → killed by explicit PID list → backend restart triggered ~2 min later (expected, per the ⚠️ below) → miloco.main PID churned 3830841→3838036→3852589→3857276 over 40 min while supervisord stayed 3791535 (loop confirmed) → root cause nailed with ONE bounded probe: `grep -c "omni API 调用失败" /root/.openclaw/miloco/log/miloco-backend.log` returned 578 (exit 0) + `tail -4000 ... | grep -E "watchdog.*self-stall"` showed 293s/200s/239s stalls.

Three operational lessons from that flow:
- **Count-only `grep -c` on the FULL log file completes fast** (returned 578, exit 0) even though full-line greps of this log are documented to hang on dense `miot.decoder` output. When the container is responsive, `grep -c` is the cheap root-cause probe — use it before any line-emitting grep.
- **Once the loop is confirmed by PID churn, stop probing and report.** Do NOT attempt `service start`/`service stop` recovery during an omni-401 loop — the backend gets SIGKILLed minutes later regardless. The report should state root cause (omni API key invalid, N failures) and the durable fix (update key + restart), not declare victory on zombie cleanup alone.
- **`miloco-cli service status` mid-restart returns `{"running": false, "managed": true, "supervisor_state": "STARTING"}`** with port 1810 not yet bound and `/health` empty (curl exit 7). This is the pre-bind window, distinct from the `running: true` + small `uptime_seconds` state documented in fallback-when-cli-hangs.md pitfall #5. Both are normal restart-window states; STARTING means initialization hasn't reached the bind point yet. **⚠️ Cleaning the cron zombie pile can itself trigger a restart within ~2 min** (a killed in-flight `miloco-cli service start` aborts/completes and the backend respawns) — after any cleanup, re-check miloco.main's PID: ONE new PID = fresh warmup (normal), repeated new PIDs = the loop is still running underneath.

### One-shot loop confirmation probe (verified 2026-08-01, second recurrence same morning)

When PID churn is suspected (supervisord constant + miloco.main PID changing), confirm the loop in ONE bounded probe. The container is briefly responsive right after a respawn, and count-only greps + small-file tails complete instantly (exit 0) even mid-loop:

```bash
timeout 30 sshpass -p "<PASSWORD>" ssh -o ConnectTimeout=8 root@192.0.2.10 \
  "pct exec 310 -- bash -c 'grep -c \"omni API 调用失败\" /root/.openclaw/miloco/log/miloco-backend.log; echo ---; grep -cE \"WARN exited: miloco-backend\" /root/.openclaw/miloco/log/supervisord.log; echo ---; tail -4 /root/.openclaw/miloco/log/node_events.log'"
```

Reads:
- `omni API 调用失败` count = 401 root-cause tally (566 on the first verified flow; 608 on this recurrence ~2h later)
- `WARN exited: miloco-backend` count (supervisord.log) = cumulative kill/respawn history (observed 3987) — the absolute number is cumulative over the log's lifetime, so use as corroboration only, NOT the sole loop signal
- `node_events.log` tail shows the latest respawn's RUNNING_START timestamp (e.g. 01:56:33 UTC = 09:56 local) — proves churn is happening NOW

**Loop-call threshold refined: 3 PID changes + count corroboration is enough.** The first flow needed the 4th PID to be unambiguous; this recurrence was correctly reported with 3 churned PIDs (09:38 → 09:48 → 09:56, gaps accelerating 10min → 8min) once the omni-401 count and supervisord exit count corroborated. Do NOT burn probes waiting for a 4th PID when the counts already confirm the root cause.

### Fourth recurrence same day (verified 2026-08-01 10:21) — loop STILL unresolved

- supervisord PID **3791535 unchanged** (07:12 start) through the 4th recurrence; miloco.main churned to **4011331** (started 10:20:23, etime ~4min at check). Same PID identity → same loop continuation, per the rule above: PID identity alone is corroboration, no fresh omni-count grep needed.
- `pct exec` probe (count-only grep + node_events tail) returned EMPTY again — container CPU-starved mid-loop, expected. Host-side `ps -eo pid,lstart,stat,etime,cmd` is the only reliable probe.
- PVE host load was 4.57 at check (restart-gap dip) — confirms the "load dip ≠ green light during a crash loop" pitfall; probe still hung.
- Perception logs: agent-mode `--limit 10` returns STALE July-3 entries (cursor-based), `--since 24h` returns empty, DB `perception_log` table last row = 2026-07-18 15:02 UTC, while observability `traces`/`events` tables are fresh (same day). Interpretation: the engine process is alive and doing device/observability work, but the perception inference stage produces ZERO new entries during the loop — so `回家/离家` events cannot occur. Do not read "no logs in 24h" as "nobody home".
- The durable fix (omni API key renewal) had NOT been applied as of 10:21. Recurrences: 07:50-08:20 → 09:38-09:56 → 10:06+ → 10:20+.

### Fifth recurrence same day (verified 2026-08-01 10:35) — NEW pre-run signature `⚠️ 无法解析感知日志:`, loop still unresolved

- **New pre-run failure signature**: the cron pre-run script emitted `⚠️ 无法解析感知日志:` (script fetched data but could not parse it) instead of the documented `⚠️ 获取感知日志超时，PVE/CT <ID> 可能不可达` (timeout). Both signatures are consistent with the SAME omni-401 kill loop — do NOT treat the parse failure as a new problem or burn probes re-checking connectivity. Diagnose from the PVE host exactly as for the timeout case (one-shot probe).
- omni 401 count climbed to **625** (day's progression 566 → 578 → 608 → 625); count-only `grep -c` still completes fast mid-loop.
- supervisord PID **3791535 unchanged** (07:12 start) through the 5th recurrence; miloco.main churned to **4029162** (started 10:34:54, only ~17s old at check; node_events RUNNING_START 10:35:11 local) — the PID-identity rule held again: same supervisord PID + fresh miloco.main = continuation of the same loop, no fresh omni-count grep needed.
- PVE host load 8.14, CT <ID> `status: running` — running status is meaningless during the loop, as documented.
- **CLI behavior during the loop (new)**: `miloco-cli perceive logs --since 2h --limit 100` UNBOUNDED hung past 90s; bounded `timeout 30 miloco-cli perceive logs --since 1h/3h --limit 30` returned EMPTY promptly. Empty `--since` results = zero inference output during the loop (matches stale DB rows), NOT "nobody home". Always wrap the CLI itself in `timeout`, not just `pct exec`.
- Report labeled it "今日第5次复发" (5th recurrence today) — durable fix (omni key renewal) still NOT applied; no light-control action possible (total_inferences=0 → no 回家/离家 events).

### Sixth recurrence same day (verified 2026-08-01 16:20) — supervisord PID CHANGED but loop persists; host-identity pitfall

- **NEW: a supervisord PID change does NOT mean the loop is resolved.** All earlier recurrences shared supervisord **3791535** (07:12 start); at 16:20 supervisord was **44079 (started 12:56:21)** — a supervisord-level restart happened mid-day (likely a manual `service restart` attempt), yet the loop continued underneath: miloco.main churned to **352031 (started 16:17:42, only ~3 min old at first check)** and PVE load climbed **7.37 → 10.01 → 21.51** across the session. The PID-identity rule is ONE-directional: same supervisord PID = continuation confirmed; a NEW supervisord PID only means "re-verify" (check miloco.main churn + perception output + load) — do NOT declare resolution from the PID change alone.
- **Stable miloco.main for minutes ≠ responsive container.** miloco.main 352031 stayed up 6+ min across two checks (16:17:42 → still running at 16:24, etime 06:36) while EVERY `pct exec` probe — even a bare `pct exec 310 -- echo CT-ALIVE` wrapped in `timeout 10` — exited 124, and load hit 21.51. Do NOT wait for the documented 2-3 min churn cadence to call the loop; sustained load >20 + probe-hostile container + zero perception output (total_inferences=0 across 24h) is sufficient even with a stable PID.
- **⚠️ HOST-IDENTITY PITFALL (new, cost 2 wasted probe rounds): the cron job runs on the hermes-agent container (192.0.2.10), NOT on the PVE host.** Local `ps -eo ... | grep miloco` and local `uptime` on the cron runner show ONLY hermes-agent's own processes (hermes gateway, MCP servers, playwright) and its own load — zero miloco lines and a misleading "low" load. The documented "host-side ps" must be executed THROUGH SSH to the PVE host: `sshpass -p "<PASSWORD>" ssh -o ConnectTimeout=8 root@192.0.2.10 "ps -eo pid,lstart,stat,etime,cmd --width=200 | grep -E 'miloco.main|supervisord'"`. Confirm host identity first (`hostname` / `ip -4 addr`); on the cron runner `pct` is not even installed. (`pct list` from the PVE host shows the topology: 100 Ubuntu24.02, 200 mcp-server, 201 homeassistant, 202 hermes-agent, 300 stopped, 310 miloco.)
- `miloco-cli perceive devices` returns fine (3 cameras online: 北院/三楼监控/前院) even mid-loop — devices/observability work continues; camera-online is another false-green, consistent with prior docs. Bounded `perceive logs --since 24h --limit 20` returned EMPTY promptly (exit 0) while unbounded probes hung.
- Outcome: reported as 今日第6次复发 (6th recurrence); durable fix (omni key renewal) still NOT applied; no light-control action possible (total_inferences=0 → no 回家/离家 events).

### Third recurrence same day — supervisord PID identity + host-side ps-only confirmation (verified 2026-08-01 10:15)

- **Same supervisord PID across all of a day's recurrences = CONTINUATION of the same loop, not a new issue.** PID 3791535 (started 07:12) persisted through the 07:50–08:20 flow, the 09:38–09:56 recurrence, AND the 10:06+ recurrence. When the supervisord PID matches one already documented/seen earlier the same day, call the loop with FEWER freshly-observed PID changes — the PID identity IS the corroboration, making the count-only grep optional rather than required.
- **The one-shot confirmation probe can itself hang.** On this recurrence the "verified" probe (`grep -c "omni API 调用失败"` + `tail -4 node_events.log`) returned empty/exit 0 — the container was so CPU-starved that even count-only greps and small-file tails never completed. Do NOT keep retrying it; fall back to host-side ps-only confirmation (below).
- **Host-side ps-only loop call (2 PID changes suffice with corroboration):** run `ps -eo pid,lstart,stat,etime,cmd | grep 'miloco.main'` (and the same filter for supervisord) ON THE PVE HOST — host-level ps always completes (no pct exec involved). Observed here: miloco.main 3991199 (10:06) → 3996983 (10:11) with supervisord constant → loop called without ever reading a container log. Use `lstart` (wall-clock start time), not just `etime`, so PID-change detection stays unambiguous across checks and restart gaps are measurable directly (10min → 8min → 5min, cadence accelerating across the day's recurrences).
- **Clean stuck-process pile ≠ healthy engine.** This recurrence had ZERO stacked lxc-attach/miloco-cli zombies (the cron pre-run script's retries left nothing), yet every pct exec probe hung. PID churn is the decisive signal; zombie presence is neither necessary nor sufficient. The `⚠️ 获取感知日志超时，PVE/CT <ID> 可能不可达` false timeout now has TWO documented causes: (1) the cron script's own hung `service start` retries (fallback-when-cli-hangs.md), (2) the omni-401 kill loop starving the container (this file). Diagnose both from the PVE host with `ps` + `uptime` before assuming anything about connectivity.
- **Report the recurrence count.** When a loop was already reported earlier the same day, the next report should explicitly say "Nth recurrence today of the same issue — the durable fix (omni key renewal) has NOT been applied yet", so the user understands it is unresolved, not a fresh failure. No light-control action is possible during the loop (total_inferences=0 → no 回家/离家 events) — state that in the report.

**Interpretation**: the backend restarted ITSELF after detecting a stall. This is NOT pitfall #12 (stalled scheduler) — the engine is healthy but freshly restarted:
- `miloco-cli perceive logs --since 2h` returns `{"logs": [], "count": 0}` — NORMAL, no inferences have run yet
- Wait ~2 min for full warmup before expecting realtime_perceive events
- CPU spike (miloco.main 120%+ / PVE load >10) right after restart is normal warmup

## Track-Stuck Stall → Self-Recovery (NO restart)

**Signature** in `node_events.log` (NOT the backend log):

```
STALLED processor: track stuck for 68s (threshold 60s)
STALLED engine: track stuck for 68s (threshold 60s)
RECOVERED engine: resumed after 6s stall (track finished)
RECOVERED processor: resumed after 6s stall (track finished)
```

**Meaning**: a perception track (batch inference) exceeded the 60s stall threshold; the engine stalled briefly, then resumed on its own. **NO restart happens.** Distinct from the watchdog self-stall (`[watchdog] self-stall detected` → clean re-init minutes later) — STALLED+RECOVERED pairs mean the engine is healthy and self-healing, no action needed. Observed 2026-08-01 alongside a subsequent backend restart; the stall itself was not the restart trigger.

**Diagnostic value when logs are hard to read (CPU-starved)**: `tail -4 node_events.log` is a small file that reads instantly even when miloco.main saturates CPU. It tells you engine state without touching miloco-cli:
- `STARTING/READY/RUNNING_START` lines → fresh restart, wait for warmup
- `STALLED ... RECOVERED` pairs → transient stall, engine self-healed
- neither + no `realtime_perceive` in backend log → investigate watchdog/restart signatures

## Wait-then-Single-Probe Pattern (pct exec hangs under inference load)

When `pct exec` hangs and host `uptime` shows load > 10, do NOT keep retrying (zombie accumulation). Instead:
1. Kill stacked `miloco-cli` / `bash -c` wrapper / `ssh -o` leftovers on PVE host (safe to kill — they're timed-out cron runs)
2. Poll host `uptime` every ~2 min until load < ~6
3. Only then run ONE pct exec probe

Observed 2026-08-01: load 10.2 → cleaned 3 stacked miloco-cli + wrappers → waited through miloco.main inference (load 9.5→7.6→5.9) → pct exec responsive again.

**⚠️ Load dip ≠ probe green light during a CRASH LOOP (observed 2026-08-01 07:37)**: in an accelerating watchdog loop (21min → 3min cadence), the 1-min load can dip below 6 (observed 4.90) in the dead window right after a SIGKILL — but the respawned miloco.main re-starves the container within seconds, so a probe launched at "load 4.9" still hangs (observed: probe printed its first echo then hung on `tail -6 node_events.log`). During a suspected loop, check PID stability FIRST: if miloco.main's PID keeps changing across checks, expect pct exec to hang regardless of the load reading — do NOT burn probes. The load dip is the restart gap, not a recovered container.

**Warmup refinement (observed 2026-08-01 05:36–05:38)**: the `< ~6` load target applies to STEADY-STATE inference load. During the first ~5–10 min after a backend restart, pct exec can STILL time out at host load ~8 (probes wrapped in `timeout 25 pct exec ...` all returned empty at load 7.95–8.0). Two operational rules learned the hard way:
- NEVER combine `sleep N; <multiple pct exec probes>` into one command — a single hung probe eats the whole timeout and you lose the sleep too (observed: `sleep 90; 4 probes` → 150s timeout, zero info gained). Do the wait in its own terminal call, then run exactly ONE `timeout 25`-wrapped probe per call.
- During warmup, probe cheapest-first: host `uptime` + `ps aux | grep -E 'lxc-attach|miloco-cli'` (host-level, always fast), then ONE bounded log tail. Defer supervisorctl/health checks until load < ~6.

## Pitfalls

- **CT <ID> rootfs is on local-lvm** (`rootfs: local-lvm:vm-310-disk-0` in `/etc/pve/lxc/310.conf`) — you CANNOT read the container's log files from the PVE host filesystem (`/var/lib/vz/images/310/` is empty for local-lvm disks). Log-file fallback always requires `pct exec 310 -- tail ...`.
- **Wrap miloco-cli in `timeout`** inside pct exec to prevent indefinite hangs: `pct exec 310 -- bash -c 'export PATH=/usr/local/bin:$PATH; timeout 25 miloco-cli perceive logs --since 2h --limit 3'`. The CLI itself has no `--timeout` flag.
