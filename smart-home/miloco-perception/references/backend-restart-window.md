# Miloco Backend Restart Window — Diagnosis

## Symptom
- Cron pre-run script: `⚠️ 获取感知日志超时，PVE/CT <ID> 可能不可达` (timeout) OR `⚠️ 无法解析感知日志:` (parse failure — script got output it couldn't parse; same root cause: backend restart window)
- `miloco-cli perceive logs` → `{"error": "cannot connect to Miloco backend at http://127.0.0.1:1810"}`

## ⚠️ Do NOT trust `miloco-cli service status` during a restart window
- It can report `{"running": false, "supervisor_state": "STARTING"}` while the backend is actually mid-recovery and will come up fine.
- The reliable liveness checks are: `ss -tlnp | grep 1810` (port bound) AND fresh mtime on `miloco-backend.log` (perf/identity lines within the last minute). Log timestamps are **UTC** — a line at 01:21 UTC is 09:21 local (UTC+8); do not misread current logs as stale.

## Key insight
Timeout / "cannot connect" is usually a BACKEND RESTART WINDOW, **not** a PVE/CT <ID> network failure.
Backend is `managed: true` → it auto-restarts; during the restart window (roughly 30–90s at low
load, but **up to ~3 min when PVE host load is elevated** — see observed timeline below)
the API at 127.0.0.1:1810 is unreachable and the monitoring pre-run script times out.
Do NOT report "PVE/CT <ID> unreachable" until you have verified `pct status 310`.

**One restart produces MULTIPLE different-looking symptoms across consecutive probes** — a
parse-fail in the pre-run script, a hung (exit 124) `perceive logs`, then a `cannot connect`
response are often all the SAME backend restart event seen from different angles, not three
separate failures. Do not treat each symptom as a new problem; collect one coherent timeline
(`service status` uptime, `ss` port, node_events.log READY/RUNNING_START lines) before
concluding anything is wrong.

## Diagnosis steps (order matters)
1. **PVE reachable + CT <ID> running?**
   `sshpass -p ... ssh root@192.0.2.10 "pct status 310"` → expect `status: running`.
   If running, suspect backend restart, not connectivity.
2. **Backend status + uptime:**
   `pct exec 310 -- bash -c 'export PATH=/usr/local/bin:$PATH; miloco-cli service status'`
   → low `uptime_seconds` (e.g. 10–60s) = just restarted, mid-initialization.
3. **Port not listening yet:**
   `ss -tlnp | grep 1810` → empty during init. Backend log
   (`/root/.openclaw/miloco/log/miloco-backend.log`) shows the device-reconnection phase
   (`miot.lan device online`, `mips_cloud CONNACK success`, `user-level subscribe OK`)
   before 1810 opens.
4. **Wait ~20–60s, retry.** Once `ss` shows `0.0.0.0:1810` listening and uptime grows, API is back.
5. **High PVE host load (load avg 10+) makes `pct exec` FLAKY** — individual calls intermittently hang (exit 124) even though status shows running and simple `pct status` works. This is NOT a hung container by itself; it's host CPU contention. Use a bounded retry loop (e.g. 3–4 attempts, ~20s apart) for any `pct exec` command before concluding the container is hung. `perceive logs` returns in one of three states across retries: `cannot connect` (still initializing) → `No logs found` (up, buffer cleared) → actual events.
6. **Fast 401 triage:** `grep -c "401" /root/.openclaw/miloco/log/miloco-backend.log` — thousands of hits (e.g. 3000+) means the omni API key failure (see `backend-hung-recovery.md`) is the chronic root cause, not the restart itself. Confirm it's ongoing with `grep "401" ... | tail -n 3` — recent timestamp = still failing.

## Post-restart caveat
- Right after a restart, `perceive logs --since 24h` returns EMPTY
  (`"logs": [], "count": 0, "total_inferences": 0`). The stream buffer was cleared —
  pre-restart events are LOST, not "nothing happened".
- In a cron report, distinguish "no events" (engine healthy, house truly quiet) from
  "no data because backend just restarted". Let the engine run a full cycle before
  concluding the house is quiet.
- `miloco-cli monitor` is a GROUP, not a flat command: use `monitor status` /
  `monitor resources`.

## Observed timeline (2026-08-01, UTC)
- backend pid 99906, uptime 10s → 53s → 66s across ~60s of checks
- 1810 listening appeared ~40s after first check; `perceive logs` then returned ok
- `perceive logs --since 24h` empty even after recovery (buffer cleared by restart)
- **Second event (~03:05–03:10 UTC, host load 6.6→10.5)**: pre-run script `无法解析感知日志`
  → first probe `perceive logs --since 24h` returned `code:0, count:0` (backend briefly up)
  → 48h probe hung (exit 124) → retry returned `cannot connect` → `service status` showed
  `uptime_seconds: 25` + `ss` showed 1810 bound → node_events.log showed READY +
  RUNNING_START for all components at 03:08:04–03:08:11 UTC. Recovery took ~3 min total —
  **longer than the 30–90s window seen at lower load**; the elevated PVE load both slowed
  startup and made intermediate probes flaky. All three symptoms were one restart.
