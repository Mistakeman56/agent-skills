# Fallback When `miloco-cli` Hangs

> 🔗 Related: omni API 401 degradation (scene understanding skipped), watchdog self-stall auto-restart signature, local-lvm log access → see `references/perception-degradation.md`

## Problem

After a `miloco-backend` restart or when `miloco.main` is CPU-heavy (>50%), `miloco-cli perceive logs` and other CLI commands may **hang indefinitely** (timeout at 15–60s) even though `supervisorctl status` shows the service as RUNNING.

## Cron Job Quick-Diagnostic Sequence

When `miloco-cli perceive logs` hangs in a cron job context, follow this **exact** order. Each step is a decision point — do NOT skip ahead or retry earlier steps:

```bash
# STEP 1: Plain SSH to PVE host (no pct exec) — determines host vs container
sshpass -p "<PASSWORD>" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=8 root@192.0.2.10 "uptime"
# Load avg > 10 → PVE host overloaded (all pct exec slow)
# Load avg < 5 → host is fine, problem is container-level
# ⚠️ This MUST be the first diagnostic step after a miloco-cli hang. Do NOT try pct exec variants first.

# STEP 2: If host load > 10, check what's consuming resources
sshpass -p "<PASSWORD>" ssh -o ConnectTimeout=8 root@192.0.2.10 "top -bn1 | head -15"
# Look for: miloco.main at 90%+ CPU → container is the primary load source
# If miloco.main is NOT top consumer → other PVE workloads are the issue
# At this point, STOP. Do not retry pct exec — report the finding.

# STEP 3: If host load is moderate but miloco-cli still hangs → container-level issue
# Only try pct exec after confirming host load < 10:
sshpass -p "<PASSWORD>" ssh -o ConnectTimeout=8 root@192.0.2.10 "pct exec 310 -- cat /proc/loadavg"
# Fast → container alive, miloco-cli just needs warmup time
# Slow/timeout → container itself is stuck (proceed to log-file fallback below)

### ⚠️ Probe Hygiene: wrap every `pct exec` in `timeout N`, keep host checks in separate calls

`ConnectTimeout=8` on ssh only guards the SSH handshake — it does NOT protect the `pct exec` inside. An unwrapped hung `pct exec` blocks the ENTIRE ssh call until the caller's own timeout fires (observed 2026-08-01 11:43: a combined `pct exec ... service status; ss` + host `ps` call burned the full 45s terminal timeout and returned nothing; the hung probe also left an R-state `/usr/bin/python3 /usr/local/bin/miloco-cli service status` leftover inside CT <ID> that had to be `kill -9`'d by PID afterwards). Rules:

1. **Always wrap the pct exec portion**: `timeout 20 pct exec 310 -- bash -c '...'` (20–25s is enough). The probe then self-terminates with exit 124 instead of hanging the whole call — and leaves a much smaller leftover footprint to clean.
2. **Never batch a pct exec with host-only checks in one ssh command.** Run host diagnostics (`uptime`, `pct status 310`, `ps -eo pid,stat,etime,cmd | grep -E 'lxc-attach -n 310|miloco-cli'`) in their OWN ssh calls FIRST — they are immune to container hangs and give the host picture while the container is wedged. Only after host checks are done, fire at most one timeout-wrapped pct exec probe.
3. **Reading probe exit codes** (with `timeout` wrapping): `124` = probe hung and was killed — immediately re-check `ps` on the host and `kill -9` any leftover it left. `0` + empty output = the container RESPONDED within the window and the log simply had no matching lines (e.g. `grep realtime_perceive` over a bounded tail found nothing) — that is a responsiveness signal, NOT proof the house was quiet and NOT proof of a hang. A container can flip between these two states within ~30s while miloco.main is >100% CPU (observed 2026-08-01 11:44–11:45: `tail|grep` read → exit 0 empty, next raw-tail read → exit 124).
4. **Load cross-check while the engine is busy**: host load ~9–10 with ~90% CPU idle and `python3 -m miloco.main` (uid 100000, 2GB RES) at 100%+ CPU = the ENGINE ITSELF is the load source; the host is fine and the container is simply CPU-starved by the engine. Verify the big python3 is miloco.main via `cat /proc/<pid>/cmdline | tr '\0' ' '` BEFORE killing anything — never kill it, only the sshpass/ssh/lxc-attach/`bash -c miloco-cli`/`/usr/bin/python3 .../miloco-cli` retry-chain PIDs.
```

### Key Signature: "echo hello" OK but miloco-cli hangs

When `pct exec 310 -- echo hello` succeeds instantly but `pct exec 310 -- miloco-cli ...` hangs, this is the **container-level CPU overload pattern**: the container is alive (lightweight commands work) but `miloco.main` is consuming 90%+ CPU, starving miloco-cli. Do NOT interpret `echo hello` success as "container is fine" — it only means the container isn't completely dead. This pattern appeared on 2026-07-16 with load avg 11.50 and miloco.main at 90.9% CPU.

### Direct Python Invocation (when the miloco-cli wrapper returns EMPTY)

Observed 2026-08-01: during a backend crash-loop (watchdog SIGKILLs every 3-5 min), `pct exec 310 -- /usr/local/bin/miloco-cli --help` and any `bash -c '... miloco-cli ...'` / `sh -lc '...'` variant returned **empty output with exit 0** — not a hang, just nothing. Meanwhile `pct exec 310 -- echo TEST_OK` and `pct exec 310 -- ls /usr/local/bin/` worked fine. The reliable way to reach the CLI in this state is to invoke the Python entry point directly, bypassing the shebang wrapper:

```bash
sshpass -p "<PASSWORD>" ssh -o ConnectTimeout=8 root@192.0.2.10 \
  "pct exec 310 -- python3 -c 'from miloco_cli.main import main; import sys; sys.argv=[\"miloco-cli\",\"perceive\",\"logs\",\"--since\",\"3h\",\"--jsonl\"]; main()'"
```

Notes:
- `sys.argv` must be set explicitly — the `miloco-cli` script is a thin shebang wrapper around `miloco_cli.main.main()` (see `cat /usr/local/bin/miloco-cli`).
- This worked even while `perceive devices` / `perceive logs` via the wrapper returned `{"error": "cannot connect to Miloco backend at http://127.0.0.1:1810"}` — the wrapper-level emptiness is separate from backend reachability. Backend down → CLI answers with the JSON error; wrapper broken/empty → use this python3 form.
- `--since` returned `No logs found` (not an error) for 3h/12h windows during the crash loop — consistent with a backend that restarted and produced no inferences, NOT evidence of a quiet period. Cross-check with `supervisord.log` SIGKILL cadence before concluding anything (see `references/watchdog-selfstall-kill-loop.md`).

### ⭐ Best Fallback: Host-Side Log Read via `pct mount` (zero container contention)

When `pct exec` hangs (container CPU-starved by miloco.main or watchdog loop), read the log files DIRECTLY from the PVE host by mounting CT <ID>'s rootfs — no container CPU needed, no zombie accumulation:

```bash
# 1. Mount CT <ID> rootfs on the host (host command, immune to container hangs)
sshpass -p "<PASSWORD>" ssh -o ConnectTimeout=8 root@192.0.2.10 \
  "pct mount 310"   # → mounted CT <ID> in '/var/lib/lxc/310/rootfs'

# 2. Read logs from the host path (fast, no contention):
#    backend live log (miot.decoder spam + perception events):
tail -40 /var/lib/lxc/310/rootfs/root/.openclaw/miloco/log/miloco-backend.log
#    dated backend logs (perception events live here when logging rotates):
ls -t /var/lib/lxc/310/rootfs/root/.openclaw/miloco/log/miloco-backend_*.log | head -3
#    supervisord SIGKILL cadence (crash-loop check):
tail -15 /var/lib/lxc/310/rootfs/root/.openclaw/miloco/log/supervisord.log
#    engine state:
tail -6 /var/lib/lxc/310/rootfs/root/.openclaw/miloco/log/node_events.log

# 3. Unmount when done:
sshpass -p "<PASSWORD>" ssh -o ConnectTimeout=8 root@192.0.2.10 "pct unmount 310"
```

Validated 2026-08-01 12:30 local: while `pct exec 310 -- which miloco-cli` hung (exit 124, engine at 90-121% CPU), this method returned node_events, supervisord SIGKILL cadence, 401 counts, and full log tails in seconds. Whole-file `grep` on the 5.8MB live log is fine host-side (no container CPU contention) — the hang risk was container-side only.

### Fallback: Read Log File Directly

When CLI commands hang, read the backend log file directly via `pct exec` with `tail` or `grep`:

```bash
# Last 30 lines
sshpass -p "<PASSWORD>" ssh -o ConnectTimeout=8 root@192.0.2.10 \
  "pct exec 310 -- tail -30 /root/.openclaw/miloco/log/miloco-backend.log"

# Or search for recent perception events — ⚠️ ALWAYS bound the grep with `tail -N` first.
# Full-file grep on the raw log HANGS (observed 2026-08-01, exit 124 after 30s): the log
# is dense with `miot.decoder` "drop non-key frame" lines, so scanning it whole is too slow.
sshpass -p "<PASSWORD>" ssh -o ConnectTimeout=8 root@192.0.2.10 \
  "pct exec 310 -- bash -c 'tail -2000 /root/.openclaw/miloco/log/miloco-backend.log | grep realtime_perceive | tail -5'"
```

If `tail` also hangs → the container is completely unresponsive. Do NOT retry. Report host load stats and recommend `pct stop 310 && sleep 5 && pct start 310`.

### Log Line Format for Perception Events

```
YYYY-MM-DD HH:MM:SS - miloco.perception.client - INFO - ✅ realtime_perceive: {JSON}
```

The JSON payload contains:
- `caption` — array of scene descriptions with `description`, `room_name`, `device_name`, `time_window`
- `matched_rules` — rules triggered by this perception
- `speeches` — detected speech
- `env_sounds` — environmental sounds
- `device_rule_map` — device-to-rule associations
- `timing` — performance metrics

### Example Parsing

```bash
# Extract the JSON from the last perception event (bounded tail first — see above)
sshpass -p "<PASSWORD>" ssh -o ConnectTimeout=8 root@192.0.2.10 \
  "pct exec 310 -- bash -c 'tail -2000 /root/.openclaw/miloco/log/miloco-backend.log | grep realtime_perceive | tail -1 | sed \"s/.*realtime_perceive: //\"'"
```

## Pitfalls

0. **Do NOT retry `pct exec` if it hangs on first attempt — you're making it worse.** Each `sshpass → ssh → pct exec` attempt that times out leaves behind zombie `lxc-attach` or `miloco-cli` processes. Retrying the same pattern 3-5 times compounds the problem. If `pct exec 310 -- echo hello` (or any command) hangs for >10s, **stop retrying** and go straight to the zombie check: `ps aux | grep -E '(lxc-attach -n 310|miloco-cli)' | grep -v grep` on the PVE host. **The monitoring cron script itself is a major contributor to zombie accumulation** — each scheduled run that hits a timeout leaves behind D-state `miloco-cli perceive logs` and `bash -c miloco-cli service start` processes inside CT <ID>. On 2026-07-16, `ps aux` inside CT <ID> showed multiple `miloco-cli` processes in D state plus a zombie python3, all from the cron script's own retries across scheduled runs.
1. **supervisorctl command not found**: Use full path `/usr/local/bin/supervisorctl -c /root/.openclaw/miloco/supervisord.conf`
2. **HTTP API refused**: `http://localhost:9001 refused connection` — the HTTP API is flaky, but CLI status check still works
3. **Heavy CPU load (container)**: When `miloco.main` uses >50% CPU (check with `ps aux`), ALL `pct exec` commands slow down or timeout. Use `-o ConnectTimeout=8` SSH flag to avoid SSH-level hangs. **Signature**: `echo hello` succeeds instantly but `miloco-cli` hangs → container is alive but CPU-starved (miloco.main at 90%+). This appeared on 2026-07-16 with load avg 11.50 and miloco.main using 90.9% CPU + 2GB RAM.
4. **PVE host overloaded (distinct from container load)**: When PVE host load average > 10, even `pct exec 310 -- cat /proc/loadavg` times out. This is NOT a container issue — it's host-level resource exhaustion. Check `uptime` on PVE host first. If host is overloaded, investigate `top -bn1 | head -15` on PVE to find what's consuming resources. **Concrete example (2026-07-16)**: A standalone Java process (not miloco) consumed 6GB RAM + 9.1% CPU on PVE, pushing load to 12.72. The container was fine — the host was starved by an external workload. When `top` shows Java as a top consumer alongside miloco, the fix is on the PVE host, not inside CT <ID>.
5. **Backend restart recovery**: After a restart, the backend needs ~1-2 minutes to fully initialize. The `miloco-cli service status` command will show `running: true` but `uptime_seconds` will be small. Wait for uptime >120s before expecting CLI commands to work reliably.
6. **Partial recovery after restart**: After a backend restart, the first `perceive logs` query may succeed (after ~10s warmup), but subsequent queries may still timeout. The backend may need additional time to fully warm up its internal state. If the first query returns old/stale logs and subsequent queries timeout, wait another 30-60 seconds before retrying.
7. **Partial module availability (2025-07-15)**: The backend may be partially degraded where `perceive logs` works but `device control`, `service status`, `device list`, `device spec` all timeout. This suggests the perception module's local cache (for logs) is functional while the device control module (which likely needs backend API) is unreachable. When this happens:
   - `perceive logs` succeeds and returns recent data
   - `device control` hangs indefinitely
   - `service status`, `device list` also timeout
   - The backend process IS running (SSH works, container is alive)
   - Workaround: Read logs from file directly (`tail -30 /root/.openclaw/miloco/log/miloco-backend.log`) or check `supervisorctl status`
8. **Health endpoint OK but CLI still errors**: When the backend just restarted, `curl http://127.0.0.1:1810/health` may return `{"status":"ok"}` while `miloco-cli perceive logs` still returns `{"error": "cannot connect to Miloco backend at http://127.0.0.1:1810"}`. The health endpoint responds from the web server layer, but the CLI's internal HTTP client may fail during the backend's warmup window. This is NOT a false positive — the backend is genuinely not fully ready. Diagnosis pattern: (1) `ss -tlnp | grep 1810` → port is listening, (2) `curl /health` → returns ok, (3) `miloco-cli perceive logs` → "cannot connect". When all three occur together, the backend is in early warmup. Retry after 5-10s; it usually resolves within one retry.
9. **No `--timeout` flag on perceive logs**: The `miloco-cli perceive logs` command only supports `--since`, `--limit`, `--jsonl`, and `--pretty`. There is no `--timeout` or `--connect-timeout` option. If the CLI hangs, use the fallback log file read pattern instead.
9a. **`--since` format is relative time only, NOT ISO**: `--since` accepts relative durations like `1h`, `30m`, `2h30m`, `7d`. It does NOT accept ISO timestamps like `2026-07-16T00:00:00` — that returns error `Invalid 'since' format`. Always use relative time: `--since 1h` for last hour, `--since 7d` for last week.
9b. **Empty output + exit 0 from a timeout-wrapped probe ≠ "no logs"**: piping through `| head -N` masks the real exit code, so `timeout 60 sshpass ssh ... "pct exec 310 -- bash -c '... miloco-cli perceive logs ...'" 2>&1 | head -80` returning EMPTY with exit 0 means the probe hung and was killed (or output was swallowed) — NOT that the CLI answered "no perception events". Misreading this as a quiet period is dangerous: you'd report "no events" while the engine is actually mid-restart. Cross-check with host-level evidence (load, `ps aux | grep lxc-attach`) and bounded log-file reads (`tail -2000 ... | grep realtime_perceive | tail -3`). Corollary (observed 2026-08-01 05:31): during container CPU starvation even `which miloco-cli` / `miloco-cli perceive --help` can return NOTHING — the whole pct exec hangs, not just the CLI data path. Both probes came back empty with exit 0 while the container was busy starting the backend.
12. **Stale perception logs (hours to weeks old)**: When `perceive logs` returns entries that are stale — whether hours or weeks — this is NOT a warmup issue. The perception inference pipeline may be stopped, misconfigured, or the cron trigger that runs perception is not firing. Stale logs after a fresh restart (pitfall #6) are normal for ~2 minutes; stale logs persisting beyond that means the inference scheduler is not running. **Key diagnostic**: read the backend log file directly. If it shows successful initialization (miot client connected, cameras initialized, rules loaded) at time T, but no `realtime_perceive` events appear after T+5min, the backend HTTP server is up but the perception inference trigger failed to start. This was observed on 2026-07-16: backend restarted at 14:59 with clean init logs, but the last perception event was at 14:54 — 8 hours stale with no new events. Check if `miloco.main` process is actually running (`ps aux | grep miloco.main`) and whether `realtime_perceive` events appear in the backend log file (`tail -2000 /root/.openclaw/miloco/log/miloco-backend.log | grep realtime_perceive | tail -3`). If the backend init looks clean but perception events are missing, the container likely needs a full stop/start cycle.
10. **Service stop/start restart (cleaner than force-kill)**: When the backend is running but unresponsive, try `miloco-cli service stop` then `miloco-cli service start` — cleaner than `killall -9` because supervisord manages the lifecycle. Stop returns `{"code":0,"message":"stopped","pid":N}`, start returns `{"code":0,"message":"started","pid":N}`. Wait 8-15s after start for port 1810 to bind. ⚠️ Pitfall: `service stop` can itself hang (30s+) when the backend is in a bad state — if it does, fall back to `kill -9` on the miloco-cli/miloco.main PIDs.
11. **Service instability after restart (crash loop)**: A freshly restarted service may bind port 1810, pass `/health`, then become unresponsive within seconds. Symptoms: (1) port bound + health ok immediately after start, (2) 5-10s later, `miloco-cli perceive query` hangs and port stops responding. This indicates the backend is crashing during initialization — likely resource exhaustion (check `ps aux | grep miloco` for memory/CPU) or corrupted internal state. If this happens repeatedly, escalate to full container restart: `pct stop 310 && sleep 3 && pct start 310`.
13. **`miloco-cli service start` hangs when backend is fully down**: When the backend process is completely dead (port 1810 NOT bound, `ss -tlnp | grep 1810` returns nothing), `miloco-cli service start` can hang indefinitely — it tries to start supervisord which may already be in a bad state. **Diagnosis**: `curl http://127.0.0.1:1810/health` → connection refused (not timeout), `ss -tlnp | grep 1810` → empty. **Workaround**: Run `service start` in background via `nohup pct exec 310 -- ... &` on PVE, then check result after 20s. If still hanging, the container needs a full stop/start cycle. Do NOT keep retrying `service start` — each attempt leaves behind stuck `lxc-attach` processes that compound the problem (see pitfall #0).

## Timezone: Container UTC vs Host Local (UTC+8)

The CT <ID> container clock is **UTC**; the PVE host uses local time (UTC+8). Backend log timestamps are UTC. A log tail that appears "8 hours stale" vs host time may actually be current — do NOT jump to pitfall #12 (stalled scheduler) before confirming. Always cross-check with `pct exec 310 -- date`.

Observed 2026-08-01: backend log last line `17:56:52` (UTC) matched container `date` = `17:57:01 UTC` while PVE host showed `01:56` local — same moment, log was LIVE. The "8h gap" was pure timezone difference.

## Fresh Restart vs Stalled Scheduler (empty logs ≠ stale logs)

Right after a backend restart, `miloco-cli perceive logs --since 2h --limit 5` may return `{"code":0,"logs":[],"count":0,"total_inferences":0}`. This is NORMAL — no inferences have run yet since the restart. Distinguish it from pitfall #12 (stalled scheduler):

- **Stale** = log contains OLD timestamps (hours old) with no new activity after init → scheduler problem
- **Fresh-empty** = `node_events.log` tail shows STARTING/READY/RUNNING_START lines timestamped NOW, and `perceive logs` returns empty → healthy fresh restart, just no events yet

Confirm a restart completed cleanly: `tail /root/.openclaw/miloco/log/node_events.log` should show `READY engine/processor/collector/camera` and `RUNNING_START engine` — all modules up.

`grep 'realtime_perceive'` returning **0 matches** is consistent with a healthy fresh restart that hasn't produced an inference yet — it is NOT itself a failure signal (perception events are only logged when an inference actually runs).

## Identify Mystery Processes from PVE Host

When `top -bn1` on PVE shows a D-state / high-CPU process owned by uid 100000 (container user), identify it without entering the container:

```bash
cat /proc/<pid>/cmdline | tr '\0' ' '
```

A freshly-restarted `miloco.main` shows as D-state with high %CPU during warmup and can transiently push host load >10 — monitor it, don't panic (seen 2026-08-01: PID started 01:56, 127% CPU in D state, load avg 10.73; resolved to normal warmup of a just-restarted backend).

## Post-Restart Query Pattern

When the backend just restarted (uptime < 120s):
1. First query often fails with "cannot connect to Miloco backend" — wait 10s and retry
2. First successful query may return stale/cursor-based old logs — use `--since` flag instead of default
3. Subsequent queries may still timeout — wait 30-60s for full warmup
4. Only after uptime > 120s should you expect reliable, timely results — ⚠️ **uptime is NOT the deciding factor, CPU settling is**. Observed 2026-08-01: miloco.main at 146% CPU with 5:41 uptime still made EVERY pct exec probe hang (3 consecutive attempts, each ~30-60s). While miloco.main is still >100% CPU, treat the backend as warming up regardless of uptime — do NOT re-probe; see "Warmup Probe Discipline" below.

## Full Container Restart Recovery (verified 2026-08-01)

When the backend is down AND a `miloco-cli service start` is stuck (pitfall #13), the clean recovery sequence:

1. **Container restart clears everything at once**: `pct stop 310 && sleep 3 && pct start 310`. Kills ALL stuck lxc-attach / miloco-cli processes in one shot (retrying service start individually just compounds zombies per pitfall #0).
2. **⚠️ Backend does NOT auto-start after container boot**: supervisord is not running after `pct start` (`supervisorctl status` → `unix:///root/.openclaw/miloco/supervisor.sock refused connection`), and `/health` on 1810 fails. You MUST start it manually — do not mistake this for a failed restart.
3. **Manual start via nohup** (the only non-hanging way when backend is fully down, per pitfall #13):
   ```bash
   sshpass -p "<PASSWORD>" ssh -o ConnectTimeout=8 root@192.0.2.10 \
     "pct exec 310 -- bash -c 'export PATH=/usr/local/bin:$PATH; nohup miloco-cli service start > /tmp/miloco-start.log 2>&1 &'"
   ```
4. **Verification timeline** (observed 2026-08-01): ~30s after start → `/health` returns `{"status":"ok"}`; `node_events.log` shows READY modules then `RUNNING_START engine` ~6s later; `cat /tmp/miloco-start.log` shows `{"code":0,"message":"started","pid":N}`. `perceive logs` returning empty right after is a healthy fresh restart (see Fresh Restart vs Stalled Scheduler above).
5. **Load signature of stuck processes**: host load > 10 (observed 18.06) with CPU ~99.5% idle = stuck lxc-attach/miloco-cli processes, NOT genuine CPU overload. After the container restart the load collapses (observed 18 → 3.13 within ~2 min). Always cross-check `top -bn1 | head` CPU idle% alongside `uptime` load before concluding the host is resource-starved.

### Cron pre-run script's own service-start can be the culprit

The monitoring cron's pre-run script may itself run `miloco-cli service start` as a retry step. When it hangs, `ps aux` on PVE shows `lxc-attach -n 310 -- bash -c 'miloco-cli service start 2>&1'`, plus `bash -c miloco-cli service start` and `/usr/bin/python3 /usr/local/bin/miloco-cli service start` inside CT <ID> — all S-state, inflating host load. A timeout message like "PVE/CT <ID> 可能不可达" is often FALSE: plain SSH `uptime` succeeds instantly; the real cause is the hung service-start from the script's own retries. Diagnose with `ps aux | grep -E 'lxc-attach -n 310|miloco-cli service start'` before assuming the host/container is down.

**After killing the pile, re-check miloco.main's PID** — killing an in-flight `service start` can trigger a backend restart within ~2 min. A new miloco.main PID = fresh-restart warmup (load spike, probes hang, empty logs — all normal, not a new failure). But a PID that keeps changing across consecutive checks while `supervisord`'s PID stays constant = genuine crash loop underneath — escalate per `references/perception-degradation.md` (accelerating cadence + omni 401 count), don't declare victory on the cleanup alone.

**Self-resolution observed 2026-08-01 (05:30→05:38)**: the cron script's stacked procs — 3× `perceive logs` variants + a `service start` (S-state, actively chewing CPU at 10.5%) — all cleared on their own within ~7 min once the service start completed and the backend came up (`supervisorctl` showed `miloco-backend RUNNING pid 53572, uptime 0:00:16` at 05:35). So BEFORE killing leftovers, re-run `ps aux | grep -E 'lxc-attach -n 310|miloco-cli'` — the stuck set may already be gone. Killing is optional cleanup, not a required step, and a fresh `ps` first avoids killing a service-start that is mid-flight (aborting the very recovery it is performing).

**⚠️ But self-resolution is NOT guaranteed (observed 2026-08-01 06:27 batch)**: the same stacked pattern (3× perceive logs + 1× service start) was still stuck at 06:35 — 8 min later — with a `miloco-cli perceive logs` python3 in R-state spinning at 15.7% CPU and accumulating 1:06+ CPU time, and `pct exec` log reads still hanging. When the stuck set contains an R-state spinner (not just S-state waiters) or has survived >7–8 min, do NOT wait longer — kill the batch by PID.

**R-state spinner criterion validated at young age (2026-08-01 07:53 local)**: killed a pile at max etime 3:28 based purely on the R-state spinners — three burners (`perceive logs --limit 1` 18.3%, `service start` 16.0%, `perceive logs --limit 10` 14.5%) plus one D-state. pct exec log reads were already hanging. The call was correct: container stayed wedged until cleanup. Do NOT wait for the 7–8 min threshold when R-state burners are present — the spinner criterion is a standalone trigger regardless of batch age. Safe kill set (do NOT touch `python3 -m miloco.main` or supervisord): all `sshpass`/`ssh`/`lxc-attach` wrappers + `bash -c miloco-cli ...` + `/usr/bin/python3 /usr/local/bin/miloco-cli ...` from the cron's retry chains. `pkill -9 -f 'lxc-attac[h] -n 310'` etc. can kill your own ssh connection (observed exit -9) — kill by explicit PID list instead: `ps -eo pid,cmd | grep -E 'lxc-attach -n 310|miloco-cli' | grep -v grep`, filter out miloco.main/supervisord PIDs, `kill -9` the rest.

**⚠️ Always list the FULL stuck set — `head -N` hides older batches**: at 06:35 the visible 06:27 batch (via `ps ... | head -10`) masked an older batch from 05:59/06:03 (`miloco-cli service start` D-state, `perceive logs` R-state). The cron pre-run script stacks processes across MULTIPLE runs, so list `ps -eo pid,user,stat,etime,cmd | grep -E 'lxc-attach -n 310|miloco-cli' | grep -v grep` WITHOUT head truncation before deciding the kill set.

## Warmup Probe Discipline (observed 2026-08-01, kill-triggered restart)

After a kill-triggered restart, the agent's OWN diagnostic probes become part of the zombie pile — the cron script is not the only contributor:

- **Cap pct exec attempts while miloco.main is >100% CPU.** Even `supervisorctl status` or a bounded `tail` log read hangs during warmup. In one session, 3 consecutive probes each hung (~30-60s) and each left a stuck `lxc-attach`/`supervisorctl`/`bash -c` process that had to be `kill -9`'d by PID on the PVE host before it joined the pile.
- **Clean your own probe before re-probing.** After a probe times out, immediately kill its tree: `ps -eo pid,stat,etime,cmd | grep -E 'lxc-attach -n 310|supervisorctl' | grep -v miloco.main` → `kill -9` the PIDs. A defunct zombie (`[supervisorctl] <defunct>`) is fine — it gets reaped.
- **One bounded log read per ~2-3 min max** during warmup. The first successful read typically comes only after miloco.main CPU settles below ~100%.
- **`supervisorctl status` showing `STARTING` while miloco.main runs at high CPU is a warmup signal**, not a crash — do not escalate.
- **Final verification before reporting:** confirm the host is clean — `ps -eo pid,stat,etime,cmd | grep -E 'lxc-attach -n 310|miloco-cli|supervisorctl' | grep -v miloco.main` returns empty (zombies OK). Only then report "container clean".
- **If no perception data is retrievable, report the infra state honestly** (backend mid-warmup, next cycle should read normally) — do NOT report "no events" as if the engine had answered.

## Kill Decision Refinement (observed 2026-08-01)

The stuck set self-differentiates: the S-state `perceive logs` wrapper chains self-resolved within ~2 min, while the `miloco-cli service start` chain (S-state sshpass/ssh/lxc-attach wrappers + D-state then R-state `/usr/bin/python3 .../miloco-cli service start`) did NOT self-resolve and required the kill. Decision rule: when the pile contains a `miloco-cli service start` (or any `miloco-cli` python) in D/R state, kill it — those persist. S-state-only `perceive logs` chains may clear on their own; re-run `ps` once before killing them.

**⚠️ Fresh arrivals after cleanup**: the cron pre-run script can launch a NEW `miloco-cli service start` within seconds of you killing the previous batch (observed 2026-08-01 12:12 local: right after a 14-PID batch was `kill -9`'d — most had already self-resolved, exit "No such process" — a brand-new `service start` python appeared at etime 00:11 and had to be killed too). After any kill, ALWAYS re-list `ps -eo pid,user,stat,etime,cmd | grep -E 'lxc-attach -n 310|miloco-cli' | grep -v grep` and kill fresh arrivals before declaring the container clean. Note also: `kill -9` on an already-exited PID is harmless ("No such process") — kill-by-explicit-PID-list stays safe even while the pile is self-resolving.
