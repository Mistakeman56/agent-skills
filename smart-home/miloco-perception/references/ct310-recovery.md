# CT <ID> Container Recovery Procedures

## Scenario A: Accumulated Stuck Processes from Cron Runs (Most Common)

Cron jobs that invoke `miloco-cli` via `sshpass → ssh → lxc-attach` leave behind stuck processes when they time out. These accumulate over days and cause `pct exec 310` to hang indefinitely — even though the container is "running" and there is NO lock contention.

**Note on terminology**: The skill calls these "zombie" processes, but the most common case is actually stuck processes in **"S" (sleeping) state**, not true zombies in "Z" state. The `ps aux` output will show them as `Ss+` or `S` state. The kill-and-reprobe approach works the same regardless of state.

### Prevention: `timeout N` Wrappers (Cron Context)

The #1 root cause of Scenario A is cron jobs that hang waiting on `miloco-cli` / `pct exec` and get killed by the cron harness, leaving the child processes stuck. **Prevent the accumulation at the source** by bounding every call:

```bash
# On PVE side — bound the whole pct exec (prevents stuck lxc-attach):
sshpass -p "..." ssh root@192.0.2.10 "timeout 20 pct exec 310 -- bash -c '...'"

# Inside the container — bound the CLI itself (prevents stuck miloco-cli python):
pct exec 310 -- bash -c 'export PATH=/usr/local/bin:$PATH; timeout 25 miloco-cli perceive logs --limit 10 --since 48h'
```

`timeout` exits 124 when the bound is hit, so appending `|| echo TIMEOUT` makes the failure visible without leaving orphans. Validated 2026-08-01: three consecutive cron-style probes (`perceive logs` 24h → ok; 48h → hung; retry → `cannot connect`) all belonged to ONE backend restart window; the `timeout` wrappers meant `ps aux | grep miloco-cl[i]` was clean afterward (zero stuck processes).

### Quick Resolution (Most Common Case)

In most cases, killing the stuck processes is sufficient — **no container restart needed**:

```bash
# 1. Kill all stuck processes
sshpass -p "<PASSWORD>" ssh -o StrictHostKeyChecking=no root@192.0.2.10 \
  "kill -9 \$(ps aux | grep -E '(lxc-attach -n 310|miloco-cli|sshpass.*lxc-attach)' | grep -v grep | awk '{print \$2}' | tr '\n' ' ') 2>/dev/null"

# 2. Brief wait for cleanup to settle
sleep 3

# 3. Re-probe pct exec
sshpass -p "<PASSWORD>" ssh -o StrictHostKeyChecking=no root@192.0.2.10 "pct exec 310 -- echo PCT_OK"
# If responsive → done, no restart needed. Proceed to retrieve logs.
# If still hanging → fall through to full restart below.
```

### ⚠️ PITFALL: Bulk Kill Can Kill Your Own SSH Session — Use the Bracket-Trick Form

The `kill -9 $(ps aux | grep -E '...' | grep -v grep ...)` form is fragile: the pattern text is part of your OWN command line, so `ps aux` lists the wrapping ssh/sshpass process too. `grep -v grep` often saves it (the wrapper embeds the word "grep"), but if you add an `sshpass.*lxc-attach` alternative pattern you WILL self-kill — your own cmdline contains both literals ("sshpass" ... "lxc-attach" from the pattern text).

**Self-safe form (validated 2026-08-01 — session survived, kills landed, `PCT_OK` after)**:

```bash
sshpass -p "<PASSWORD>" ssh -o StrictHostKeyChecking=no root@192.0.2.10 \
  'ps aux | grep -E "lxc-attach -n 310|miloco-cl[i]" | grep -v gre[p] | awk "{print \$2}" | xargs -r kill -9; echo KILLED'
```

- `miloco-cl[i]` matches "miloco-cli" in targets, but your own cmdline holds the literal `miloco-cl[i]` which the regex does NOT match.
- `grep -v gre[p]` excludes every wrapper (ssh/sshpass embed "grep" in their cmdline) while its own filter line doesn't match itself.
- **Do NOT add an `sshpass.*lxc-attach` pattern** — self-kill trap. The plain `lxc-attach -n 310` + `miloco-cl[i]` patterns catch everything that matters (the miloco-cli python processes and their lxc-attach parents; idle ssh wrappers die when their child is killed).

### Post-Kill: Light vs Heavy Commands (miloco.main still saturating CPU)

After a successful kill, `pct exec` may STILL hang on heavy commands for 10-30 min while `miloco.main` inference runs at 120-150% CPU. This is NOT residual corruption — light commands prove the container is fine. Do NOT retry the heavy ones (zombie accumulation); use minimal-overhead reads:

| Probe | Expected while starved | Interpretation |
|-------|------------------------|----------------|
| `pct exec 310 -- echo PCT_OK` | instant | container alive |
| `pct exec 310 -- cat /proc/loadavg` | instant, load > 8 | CPU-starved by miloco.main — wait, don't restart |
| `pct exec 310 -- tail -4 /root/.openclaw/miloco/log/node_events.log` | instant (small file) | engine-state check — USE THIS instead of miloco-cli |
| `tail -400 ...miloco-backend.log \| grep realtime_perceive \| tail -2` | may hang (dense log) | keep tails tiny; full-file grep HANGS (see fallback doc) |
| `miloco-cli perceive logs` | hangs | expected — wait for inference to finish |

Validated 2026-08-01: kill at 03:23 → `echo PCT_OK` instant while `tail -3000 | grep` timed out at 40s → `tail -4 node_events.log` instant → supervisor status instant → backend had freshly restarted (uptime 10s) → port 1810 bound + `/health` ok → `perceive logs` fresh-empty (`count:0`) = NORMAL post-restart state, not a stalled scheduler.

### ⚠️ PITFALL: Bulk Kill Also Kills In-Progress `service start` → Backend Freshly Restarted

The bulk-kill regex `(lxc-attach -n 310|miloco-cli|...)` matches **any** miloco-cli process, including a `miloco-cli service start` that the cron script's own retry chain left running. Killing that mid-start aborts/restarts the backend. **Observed 2026-08-01**: after the bulk kill, `supervisorctl status` showed `miloco-backend RUNNING pid 475260, uptime 0:00:05` and `ss -tlnp | grep 1810` returned NOTHING — looked like "backend down", but it was a fresh restart.

**Do NOT panic or run `service start` again** (that would stack another instance). Instead:
1. Check `node_events.log` tail — if it shows recent `STARTING/READY/RUNNING_START` lines, the backend is restarting normally
2. Wait ~25-40s, then verify: `ss -tlnp | grep 1810` → bound, `curl -s http://127.0.0.1:1810/health` → `{"status":"ok"}`
3. Wait until supervisor `uptime` > 120s, then `perceive logs` → expect `count:0` (fresh-empty, see fallback-when-cli-hangs.md)

So after EVERY bulk kill, always cross-check supervisor uptime — a tiny uptime (seconds) means the kill just restarted the backend and you're in post-restart recovery, not a failure state.

**Diagnosis**: SSH to PVE and check for stuck processes:
```bash
sshpass -p "<PASSWORD>" ssh -o StrictHostKeyChecking=no root@192.0.2.10 \
  "ps aux | grep -E '(lxc-attach -n 310|miloco-cli)' | grep -v grep"
```

If you see multiple `lxc-attach -n 310` or `miloco-cli` entries (often from `sshpass` and `ssh` as well), this is the cause.

### ⚠️ PITFALL: A "Stuck" `miloco-cli service start` May Be a Legit Slow Startup — Check Backend Log BEFORE Killing

Validated 2026-08-01 (cron run): pre-run script failed to parse perception log (`无法解析感知日志`) because the backend was mid-restart. `ps aux` showed `lxc-attach` + `miloco-cli service start` entries started ~2 min ago, port 1810 NOT bound — looked exactly like Scenario A stuck processes. **But it was NOT stuck**: the backend log showed startup progressing normally; ORT/ONNX model loading makes cold start take ~2 min, not the ~15-25s the older docs assumed.

**Rule: before bulk-killing a `service start`, check the backend log for progression**:

```bash
sshpass -p "<PASSWORD>" ssh -o StrictHostKeyChecking=no root@192.0.2.10 \
  "pct exec 310 -- bash -c 'tail -15 /root/.openclaw/miloco/log/miloco-backend.log'"
```

- **Healthy progression** (WAIT, do not kill): `Server is ready` → `Application startup complete` → `Uvicorn running on http://0.0.0.0:1810` → `[multicam] n_cam=1 | <camera>` → `RUNNING_START engine` in node_events.log. Wait ~30-60s, then re-check `ss -tlnp | grep 1810`.
- **Genuinely stuck** (kill warranted): log silent for minutes (no new lines) AND process at ~0% CPU with no log growth.
- After it comes up, `perceive logs` returns `count:0` fresh-empty = normal post-restart state (see fallback-when-cli-hangs.md).

**Container clock is UTC, host is UTC+8** (validated 2026-08-01): `node_events.log` / `miloco-backend.log` timestamps read ~8h behind host time. `2026-07-31 21:17` in logs = `2026-08-01 05:17` host time. A `STALLED at 21:11` line is RECENT (05:11 host), not from the previous day — don't misjudge event age when deciding whether to act. The cron `Conversation started` header uses host time; always convert before comparing.

**`supervisorctl` needs the full PATH**: bare `supervisorctl status` → `command not found`. Use:
```bash
pct exec 310 -- bash -c 'export PATH=/usr/local/bin:/root/.local/bin:$PATH; supervisorctl status'
```
If it returns `http://localhost:9001 refused connection` while supervisord IS in `ps`, that is the documented degraded/supervisord-API-down state — cross-check `ss -tlnp | grep 1810` to see if the backend itself (started directly by `miloco-cli service start`) is still functional.

**⚠️ Do NOT use `systemctl` to check miloco services** — they are NOT systemd units. `systemctl status miloco-backend` → `Unit miloco-backend.service could not be found` (validated 2026-08-01). Miloco runs under supervisord / `miloco-cli`, not systemd. Use `miloco-cli service status` (reports `uptime_seconds` — low value = just restarted), `ss -tlnp | grep 1810`, and node_events.log instead. A "could not be found" from systemctl is expected, NOT a sign the service is broken.

### Full Restart (When Kill Alone Is Not Sufficient)

**When to use**: After killing stuck processes, `pct exec` still hangs. This indicates deeper lxc runtime corruption or coexisting CPU overload.

```bash
# 1. Kill all stuck processes in one shot (if not already done)
sshpass -p "<PASSWORD>" ssh -o StrictHostKeyChecking=no root@192.0.2.10 \
  "kill -9 \$(ps aux | grep -E '(lxc-attach -n 310|miloco-cli|sshpass.*lxc-attach)' | grep -v grep | awk '{print \$2}' | tr '\n' ' ') 2>/dev/null"

# 2. Restart container
sshpass -p "<PASSWORD>" ssh -o StrictHostKeyChecking=no root@192.0.2.10 \
  "pct stop 310 && sleep 3 && pct start 310"

# 3. Wait for container boot, then start backend
sleep 15
sshpass -p "<PASSWORD>" ssh -o StrictHostKeyChecking=no root@192.0.2.10 \
  "pct exec 310 -- bash -c 'export PATH=/usr/local/bin:/root/.local/bin:\$PATH && miloco-cli service start 2>&1'"

# 4. Wait for backend init, then verify
sleep 15
sshpass -p "<PASSWORD>" ssh -o StrictHostKeyChecking=no root@192.0.2.10 \
  "pct exec 310 -- bash -c 'export PATH=/usr/local/bin:/root/.local/bin:\$PATH && miloco-cli perceive logs --limit 3 2>&1'"
```

**Pitfall**: The `kill` step alone does NOT always restore `pct exec` responsiveness. Two distinct failure modes can coexist:

1. **Stuck process corruption** (lxc runtime state from accumulated timeouts) → needs full stop/start to clear
2. **CPU overload** from `miloco.main` inference (120%+ CPU for minutes) → PVE load spikes >10, even `echo hello` times out

**After killing stuck processes, always re-probe** before deciding whether to restart the container:
```bash
# Kill stuck processes first (use PIDs from diagnosis above, or bulk kill)
sleep 3

# Re-check PVE load
sshpass -p "<PASSWORD>" ssh -o StrictHostKeyChecking=no root@192.0.2.10 "uptime"
# Load < 5? Try pct exec — if it works, stuck processes were the only issue
# Load > 10? Check what's burning CPU: ps aux --sort=-%cpu | head -15
#   - miloco.main at 100%+ CPU = inference overload → wait for it to finish, don't restart
#   - Other processes = investigate separately

# Quick responsiveness check (use cat /proc/loadavg for load data + responsiveness in one shot)
sshpass -p "<PASSWORD>" ssh root@192.0.2.10 "pct exec 310 -- cat /proc/loadavg"
# If responsive: stuck processes were the only issue, no restart needed
# If still hanging AND load > 10: CPU overload, wait for inference
# If still hanging AND load < 5: corruption persists → do full stop/start
```

**Key insight**: `miloco.main` inference can consume 120%+ CPU for 10-30 minutes, causing PVE load to spike to 12-17. This is NORMAL inference behavior, not a fault. The container will recover on its own once inference completes. Do NOT restart the container during active inference — you'll lose the in-progress computation.

### ⚠️ PITFALL: Stacked miloco-cli Commands Compound CPU Load

Each `miloco-cli perceive logs` invocation runs a Python process that consumes **15-18% CPU** while executing. When multiple cron jobs stack up (e.g., a new cron run starts before the previous one's processes have been cleaned up), these compound with miloco.main inference to push PVE load even higher.

**Symptom**: PVE load >10, but `ps aux --sort=-%cpu` shows BOTH `miloco.main` at 120%+ AND multiple `miloco-cli perceive logs` at 15-18% each.

**Response**: Kill the stacked miloco-cli processes first (they're from timed-out cron runs), then check if miloco.main inference is the remaining load. Do NOT restart the container if miloco.main is actively inferring — wait for it to finish.

**Detection**: Look for multiple `miloco-cli perceive logs` entries in `ps aux | grep miloco-cli`. If you see 3+ of them, they are accumulated cron leftovers — safe to kill.

## Scenario B: Lock Contention (Less Common)

When `pct exec 310 -- <any command>` hangs but there are NO stuck lxc-attach processes (Scenario A), check for stuck PVE operations:

```bash
# 1. Check if a lock holder exists
sshpass -p "<PASSWORD>" ssh -o StrictHostKeyChecking=no root@192.0.2.10 \
  "fuser /run/lock/lxc/pve-config-310.lock 2>&1"

# 2. Identify the stuck process
sshpass -p "<PASSWORD>" ssh -o StrictHostKeyChecking=no root@192.0.2.10 \
  "ps -p <PID> -o pid,ppid,cmd 2>&1"

# 3. Kill it
sshpass -p "<PASSWORD>" ssh -o StrictHostKeyChecking=no root@192.0.2.10 \
  "kill -9 <PID>"
```

**Common stuck processes**: `vzreboot:310`, `vzsnapshot:310`, or any `pct` operation that was interrupted.

**Symptom**: `pct stop 310` or `pct reboot 310` returns "can't lock file ... got timeout".

## Container Restart Sequence

After clearing lock contention:

```bash
# 1. Check container status
pct status 310
# If "running" but unresponsive:
pct stop 310 && sleep 3 && pct start 310
# If "stopped":
pct start 310
```

### ⚠️ PITFALL: Supervisord Does NOT Auto-Start After Container Reboot

After `pct stop/start310`, supervisord does **not** automatically start. The container boots into a bare state — no services, no port 1810 bound. You must manually start the backend:

```bash
# 1. Wait 15-30s for container boot
sleep 20

# 2. Confirm supervisord is NOT running
pct exec 310 -- supervisorctl status  # → "http://localhost:9001 refused connection"

# 3. Start the backend (preferred: miloco-cli handles supervisord internally)
pct exec 310 -- bash -c 'export PATH=/usr/local/bin:$PATH; miloco-cli service start 2>&1'
# Returns: {"code":0,"message":"started","pid":N}

# 4. Wait for initialization (backend needs ~15-25s to bind port 1810)
sleep 20

# 5. Verify port is bound
pct exec 310 -- bash -c 'ss -tlnp | grep 1810'
```

**Why `miloco-cli service start` over manual supervisord**: The CLI handles supervisord startup internally — it will start supervisord if needed, then register and start the miloco-backend service. Trying to start supervisord separately first can leave the backend unregistered.

**Diagnostic shortcut**: If `miloco-cli service start` returns `{"code":0,"message":"started"}` but `ss -tlnp | grep 1810` shows nothing after 20s, the backend is still initializing (normal for cold start with model loading). Wait another 15-20s before assuming failure.

### ⚠️ PITFALL: "Already Running" When Supervisord Is Down

When `miloco.main` is running and has bound port 1810 directly, `miloco-cli service start` may return `{"code":1,"message":"already running (pid=XXXXXX)"}` — but supervisord is NOT actually running (`supervisorctl status` returns "refused connection").

**Why**: `miloco.main` binds port 1810 as its own listener. The CLI sees the port is occupied and reports "already running", but there's no supervisord managing the process. This is a degraded state — the perception engine works, but there's no process supervision or automatic restart on crash.

**Verification**: Always check both after an "already running" response:
```bash
pct exec 310 -- bash -c 'ss -tlnp | grep 1810'           # port bound?
pct exec 310 -- bash -c 'supervisorctl status 2>&1'       # supervisord up?
pct exec 310 -- bash -c 'ps -p <PID> -o pid,stat,cmd'    # process healthy?
```

**If supervisord is down but port 1810 is bound**: The system is functional but unprotected. No action needed for immediate operation, but consider a full stop/start cycle during low-activity windows to restore proper supervision.

## Manual Backend Startup (After Container Restart)

After a container stop/start, `miloco-backend` must be restarted. **Preferred method** — use miloco-cli's service subcommand:

```bash
pct exec 310 -- bash -c 'export PATH=/usr/local/bin:/root/.local/bin:$PATH && miloco-cli service start 2>&1'
# Returns: {"code":0,"message":"started","pid":N}

# Wait for initialization (10-30 seconds depending on model loading)
sleep 15

# Verify logs are accessible
pct exec 310 -- bash -c 'export PATH=/usr/local/bin:/root/.local/bin:$PATH && miloco-cli perceive logs --limit 3 2>&1'
```

**Fallback** (if miloco-cli service start fails — bare process, no supervisord):

```bash
pct exec 310 -- bash -c 'export PATH=/usr/local/bin:$PATH; nohup miloco-backend > /var/log/miloco-backend.log 2>&1 & echo PID=$!'
sleep 15
pct exec 310 -- bash -c 'ss -tlnp | grep 1810'  # Verify port is bound
```

**Pitfall**: Backend logs may go to `/root/.openclaw/miloco/log/miloco-backend_*.log` instead of `/var/log/miloco-backend.log`. Check both locations.

## Container Responsiveness Under Load

When `miloco-backend` is running and processing heavy inference loads, `pct exec` commands may be very slow (10-30s+ per command). This is normal under high CPU/memory usage.

### ⚠️ PITFALL: miloco.main Inference Can Saturate the Entire PVE Host

`miloco.main` (the perception inference process) can consume **120%+ CPU** for extended periods (10-30+ minutes). When this happens:
- PVE host load average spikes to 12-17+
- `pct exec 310 -- echo hello` times out (even simple commands)
- `ps aux --sort=-%cpu | head -15` shows `miloco.main` at top with 120%+ CPU

**This is NOT a fault** — it's the perception engine doing heavy inference (e.g., processing a batch of sensor events). The container will recover on its own once inference completes.

**Do NOT restart the container during active inference** — you'll lose the in-progress computation and it will restart from scratch.

**Also check for other resource hogs**: Minecraft servers, large Java processes, or stuck `apt-helper wait-online` can compound the load. Use `ps aux --sort=-%cpu | head -15` and `ps aux --sort=-%mem | head -15` to identify all heavy consumers.

### ⚠️ PITFALL: PVE Host Load vs. Container Load (Distinct Causes)

There are TWO different load scenarios that look similar but require different responses:

| Symptom | Cause | Response |
|---------|-------|----------|
| `pct exec -- echo hello` works fast, but `ps aux`, `ss`, `miloco-cli` time out | Container CPU-heavy (miloco.main inference) | **Normal** — wait for inference to finish |
| `pct exec -- echo hello` ALSO times out (30s+), `pct status 310` works | PVE host overloaded (load average > 10) | **Abnormal** — investigate PVE host resources |

**First diagnostic — check PVE host load**:
```bash
sshpass -p "<PASSWORD>" ssh -o StrictHostKeyChecking=no root@192.0.2.10 "uptime"
# Load average: X.XX, Y.YY, Z.ZZ
# If all three > 5: host is overloaded, not just the container
```

**Quick responsiveness probe** (use cat /proc/loadavg for load data + responsiveness in one shot):
```bash
sshpass -p "<PASSWORD>" ssh root@192.0.2.10 "pct exec 310 -- cat /proc/loadavg"
# If this takes >5s or times out: PVE host is the bottleneck, NOT the container
```

**When PVE host is overloaded**: Check what's consuming resources on PVE itself:
```bash
sshpass -p "<PASSWORD>" ssh root@192.0.2.10 "top -bn1 | head -15"
# Look for non-miloco processes consuming high CPU/mem on PVE host
```

**Diagnostic for container-level load**: If cat /proc/loadavg works fast but complex commands fail:
```bash
# Confirms container is responsive but CPU-bound
pct exec 310 -- cat /proc/loadavg  # fast = container alive
pct exec 310 -- ps aux | head -5  # slow/timeout = CPU saturation
```

**Workaround for container-level load**: Use the log files directly instead of CLI commands:
```bash
# Read latest log directly from PVE host (avoids pct exec overhead)
pct exec 310 -- tail -20 /root/.openclaw/miloco/log/miloco-backend.log
```

## Full Recovery Checklist

When CT <ID> is unreachable or unresponsive (`pct exec` hangs):

1. ✅ Ping PVE: `ping -c 2 192.0.2.10`
2. ✅ SSH to PVE: `sshpass -p "<PASSWORD>" ssh root@192.0.2.10 "echo OK"`
3. ✅ **Check PVE host load FIRST** (quick probe — determines if it's host or container issue):
   `sshpass -p "<PASSWORD>" ssh root@192.0.2.10 "uptime"`
   - If load avg > 10: PVE host overloaded → investigate `top -bn1 | head -15` on PVE host
   - If load avg < 5: host is fine → continue to step 4
4. ✅ Check container status: `pct status 310` (should say "running")
5. ✅ Quick probe: `pct exec 310 -- cat /proc/loadavg` (if this times out, PVE host is overloaded — go back to step 3)
6. ✅ **Check for stuck lxc-attach processes** (Scenario A — most common cause):
   `ps aux | grep -E '(lxc-attach -n 310|miloco-cli)' | grep -v grep`
7. ✅ If stuck processes found: bulk kill, then **re-probe** (see Scenario A post-kill decision tree):
   - Re-check `uptime` — if load > 10, check `ps aux --sort=-%cpu | head -15` for miloco.main inference
   - If miloco.main at 100%+ CPU → wait for inference to finish (do NOT restart)
   - If load < 5 and pct exec works → stuck processes were the only issue, no restart needed
   - If load < 5 and pct exec still hangs → corruption persists → do full stop/start
8. ✅ If NO stuck processes AND load < 5: check lock holders: `fuser /run/lock/lxc/pve-config-310.lock` (Scenario B)
9. ✅ Start miloco-backend: `pct exec 310 -- miloco-cli service start 2>&1`
10. ✅ Wait 15s for initialization
11. ✅ Verify with `miloco-cli perceive logs --since 1h --limit 3`

**Order matters**: Step 3 (PVE load check) determines whether to investigate host vs. container. Step 6 (stuck process check) should always come before step 8 (lock check), because stuck process accumulation is far more common in cron-driven setups.

**Time estimate**: Quick resolution (kill only): ~30 seconds. Full restart: ~60-90 seconds.
