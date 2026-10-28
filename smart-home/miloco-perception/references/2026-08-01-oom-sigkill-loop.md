# 2026-08-01 — OOM SIGKILL Loop Masquerading as Auto-Recovery

## Situation
Cron pre-run returned `⚠️ 无法解析感知日志:` (parse failure — a known pre-run failure string). Diagnosis showed this WAS the auto-recovery pattern (backend had just restarted) — BUT the restart itself was a symptom of an OOM SIGKILL loop, not a routine healthy bounce. Service recovered on its own, yet the situation was worth reporting.

## Diagnostic path taken (chronological)
1. PVE reachable, load avg 6.0 (elevated, manageable). CT <ID> `running`.
2. Host `ps aux --sort=-%cpu | head -12`: miloco.main at 6.4% CPU, STAT `Sl`, start 01:22 — just restarted (uptime <2min). NOT the >100% CPU inference false-alarm shortcut; this was restart warmup.
3. `curl -s -m 8 http://localhost:1810/health` → exit 7 (connection refused) — backend still starting. **Do not escalate on a refused health check during warmup**; wait 15-20s and retry.
4. `pct exec 310 -- /usr/local/bin/miloco-cli service status` → `FileNotFoundError: [Errno 2] No such file or directory: 'supervisorctl'` — see PATH pitfall below.
5. `pct exec 310 -- /usr/local/bin/supervisorctl -c /root/.openclaw/miloco/supervisord.conf status` → `miloco-backend RUNNING, uptime 0:01:08`.
6. `perceive logs --since 2h` AND `--since 24h` → **both empty (count 0)**. After a restart, event history is cleared — empty logs ≠ no events; correlate with backend uptime before concluding "nothing happened".
7. Health check → `{"status":"ok"}` (recovered on its own).

## Root cause: OOM SIGKILL loop
- supervisord log: **11+ `terminated by SIGKILL` exits in ~1.3h** (16:06–17:22 UTC), restart-to-restart interval ~3-13 min. `grep -c SIGKILL` total in log: 3649 (accumulated over time).
- dmesg (PVE host): `oom-kill:constraint=CONSTRAINT_MEMCG ... oom_memcg=/lxc/310 ... Killed process 3050772 (python3)` at 01:20:36.
- CT <ID>: `MemTotal 2097152 kB` (2GB), `MemAvailable 173004 kB` (~173MB) — critical territory (skill threshold: <50MB = critical; 173MB is close).

## Commands that confirmed it (run from PVE host)
```bash
sshpass -p "<PASSWORD>" ssh root@192.0.2.10 "dmesg -T | grep -i 'oom\|killed process' | tail -5"
sshpass -p "<PASSWORD>" ssh root@192.0.2.10 "pct exec 310 -- bash -c 'cat /proc/meminfo | head -3'"
sshpass -p "<PASSWORD>" ssh root@192.0.2.10 "pct exec 310 -- bash -c 'grep -c SIGKILL /root/.openclaw/miloco/log/supervisord.log'"
```

## Takeaway rules
1. **Auto-recovery ≠ all-clear.** If the backend has restarted (uptime <60s) when you arrive, check WHY before declaring the documented false alarm: SIGKILL frequency in supervisord log + dmesg OOM evidence + MemAvailable. An OOM loop is worth reporting even though the service recovered on its own.
2. **`miloco-cli service status` needs PATH; `perceive logs` does not.** `service status` shells out to `supervisorctl` via subprocess with no PATH → full-path invocation crashes with FileNotFoundError. Use `pct exec 310 -- /usr/local/bin/supervisorctl -c /root/.openclaw/miloco/supervisord.conf status` directly, or the `bash -c` wrapper with PATH export. `perceive logs` via full path works fine.
3. **Empty `perceive logs` after a restart = history cleared by the restart**, not necessarily "no events". Check backend uptime first.
4. **Report OOM loop to user with concrete remediation** (bump CT <ID> memory via `pct set 310 -memory 4096`, or investigate leak in `/root/.openclaw/miloco/log/`). Do NOT change CT <ID> config autonomously without user approval.

## Outcome
Reported to user: no home/leave events that night (no light control needed), but flagged the OOM loop with dmesg/supervisord evidence + remediation options. User decision required on memory bump vs leak investigation.

## Recurrence — 05:05 same day (worsening)
Same `⚠️ 无法解析感知日志:` pre-run string again, ~3.5h after the first flag. This time the diagnosis was MORE deceptive: miloco.main showed the **>100% CPU + `Sl` + accumulating CPU-time pattern** (the documented false-alarm shortcut), yet it was NOT healthy inference — it was restart churn from the OOM loop.

- SIGKILL count climbed **3649 → 3676**; MemAvailable dropped **~173MB → 14MB** (now below the 50MB critical threshold).
- dmesg: second OOM kill at 05:03:18 (`Killed process 3595194 (python3)`, 2GB RSS, `oom_memcg=/lxc/310`).
- miloco.main PID churned between checks: 3589886 → 3595194 → 3602759 (each a fresh restart).
- `perceive logs` CLI hung repeatedly under load (R/D state processes piling up on host — kill host-level `lxc-attach`/`miloco-cli perceive` wrappers with `kill -9 <hostPID>` to reduce load).
- Health endpoint: exit 7 (connection refused) then timeouts while churning; eventually backend auto-recovered to STARTING → RUNNING and `perceive logs` returned empty (history cleared).

**Lesson added to `references/diagnostics.md`**: the false-alarm shortcut MUST be validated against the health endpoint before skipping steps 3-7 — the Sl/>100% CPU pattern also matches an OOM restart loop. Health failure (exit 7/timeout) or PID churn = check dmesg + MemAvailable + SIGKILL count.

**Status at end of session**: still awaiting user decision (memory bump `pct set 310 -memory 4096` vs leak investigation). OOM loop unresolved and worsening; risk of missed home-arrival events continues.

## Recurrence — 11:52 same day (third flag, ~6.5h after the 05:05 recurrence)

Pre-run string: `⚠️ 获取感知日志超时，PVE/CT <ID> 可能不可达` (fetch-timeout variant). Host `ping 192.0.2.10` (0% loss) + `pct status 310` → `running` — **PVE/CT <ID> were never actually unreachable**; the pre-run timeout was caused by the backend being down.

- `perceive --help` worked but `perceive logs` → `{"error": "cannot connect to Miloco backend at http://127.0.0.1:1810"}`; `supervisorctl status` showed `RUNNING, uptime 0:00:06` → backend had just auto-restarted (the documented auto-recovery pattern).
- dmesg: third OOM kill at 11:52:56 — `Killed process 4138822 (python3)` anon-rss 2043136kB, `oom_memcg=/lxc/310`.
- supervisord log: 03:49 start → 03:54:55 SIGKILL → 03:55 respawn; kill interval ~5 min and tightening.
- SIGKILL count 3676 → 3744 (+68 in ~6.5h). Host load 8.24.
- **MemAvailable rebounded to ~1074MB right after the restart — a high MemAvailable immediately after restart does NOT mean the loop is resolved**; the process grows back toward 2GB and gets killed again.
- Health endpoint eventually `{"status":"ok"}`; `perceive logs` empty (history cleared by restart). No home/leave events → no light control. Third flag reported to user with same remediation options (`pct set 310 -memory 4096` vs leak investigation); user decision still pending.

## Recurrence — 14:25–14:30 same day (fourth flag, ~2.5h after the 11:52 recurrence)

Pre-run string: `⚠️ 获取感知日志超时，PVE/CT <ID> 可能不可达` (same fetch-timeout variant). Same shape: PVE/CT <ID> reachable (ping 0% loss, `pct status 310` → running), backend down at port 1810, auto-recovery in progress (fresh `miloco-cli service start` + miloco.main uptime <30s, supervisord RUNNING), health briefly `{"status":"ok"}` with empty `perceive logs` (`total_inferences: 0` = history cleared, warming up) — then backend died again within minutes.

**Loop worsening — kill interval now ~5 min**:
- dmesg (PVE host): TWO OOM kills 5 min apart — 14:25:55 `Killed process 178329 (python3)` anon-rss 2068660kB; 14:30:41 `Killed process 186139 (python3)` anon-rss 2065684kB; both `oom_memcg=/lxc/310`.
- SIGKILL count **3769** (3744 at 11:52; +25 in ~2.5h).
- MemAvailable **23MB** (below the 50MB critical threshold; measured while backend down). CT <ID> load ~8.4, PVE host load ~8 (thrashing). `pct exec` began hanging again — don't pile on more stuck CLI processes.
- Health endpoint responded `{"status":"ok"}` mid-cycle then connection refused; final state: backend down, `pct status` still `running`.

**Pitfalls re-confirmed this session**:
1. dmesg inside CT <ID> (`pct exec 310 -- dmesg ...`) returns EMPTY — always read OOM evidence from the PVE host: `ssh root@192.0.2.10 "dmesg -T | grep -i 'oom\|killed process' | tail -5"`.
2. Correct supervisord log path for SIGKILL counting: `/root/.openclaw/miloco/log/supervisord.log` (the path without `/log/` returns N/A).

**Status**: fourth flag reported to user (same remediation options: `pct set 310 -memory 4096` vs leak investigation in `/root/.openclaw/miloco/log/`). User decision still pending; loop unresolved and accelerating — risk of missed home/leave events continues.
