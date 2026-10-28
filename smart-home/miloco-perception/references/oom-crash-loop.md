# OOM Crash Loop — NOT a Hung Backend (validated 2026-08-01)

Distinct failure mode from the hung-backend state. The classic recovery (kill -9 + wait for supervisord respawn) does NOT fix this — the process is already being killed by the kernel every few minutes. The fix is a memory bump (`pct set 310 --memory 4096`, user decision).

## Symptom Signature

- Pre-run script reports `⚠️ 获取感知日志超时，PVE/CT <ID> 可能不可达` but PVE is fine (`uptime` responds, `pct status 310` → `running`).
- `miloco-cli perceive logs` returns `{"error": "cannot connect to Miloco backend at http://127.0.0.1:1810"}` OR just times out (exit 124), even though `ss -tln | grep 1810` shows the port LISTENing.
- Host-side `top -bn1 | grep python3` shows a `python3` (uid 100000 = container) at **100%+ CPU, ~2.0GB RSS** — then it VANISHES minutes later.
- `supervisord.log` shows repeated pairs:
  ```
  WARN exited: miloco-backend (terminated by SIGKILL; not expected)
  INFO spawned: 'miloco-backend' with pid <new>
  INFO success: miloco-backend entered RUNNING state ...
  ```
  Then ~4-5 minutes later another SIGKILL. **Cycle period ~4-5 min = memory growth rate.**
- `grep -cE "exited: miloco-backend" /root/.openclaw/miloco/log/supervisord.log` → huge count (4044 in one install); 10+ = crash loop.

## Definitive Confirmation (run on PVE HOST, not in container)

```bash
dmesg -T | grep -iE 'oom|killed process' | tail -8
# Signature:
# oom-kill:constraint=CONSTRAINT_MEMCG,nodemask=(null),cpuset=ns,mems_allowed=0,oom_memcg=/lxc/310,task_memcg=/lxc/310/ns/.lxc,task=python3,pid=<hostpid>,uid=100000
# Memory cgroup out of memory: Killed process <hostpid> (python3) total-vm:5506192kB, anon-rss:2065968kB ...
```

`oom_memcg=/lxc/310` + `anon-rss` ≈ 2GB + `task=python3` = miloco.main exceeds the container's 2048MB cgroup limit → kernel SIGKILL. supervisord respawns it, it grows again, loop repeats.

## Hung Backend vs OOM Loop — How to Tell

| | Hung backend | OOM crash loop |
|---|---|---|
| Process at 2GB RSS | stays alive, 90%+ CPU forever | dies on its own (SIGKILL) every few minutes |
| kill -9 + respawn | **fixes it** | futile — kernel is already killing it; you just add another cycle |
| supervisord.log | single exit or rare | repeated exited/spawned pairs on a ~4-5 min cadence |
| dmesg | no oom entries | `oom-kill ... oom_memcg=/lxc/310` entries |
| Fix | kill -9, wait ~8s for respawn | `pct set 310 --memory 4096` (user decision; changes container config) |

## What NOT To Do

- **Don't keep restarting** — each respawn costs ~2 min cold start (ONNX/ORT model load) and dies 4-5 min later. You burn 10+ min per cycle with no progress.
- **Don't trust `/health` or a fresh RUNNING_START as recovery** — the engine runs fine until memory pressure returns.
- **Don't mistake empty logs right after start for omni 401** — `{"code":0,"count":0,"total_inferences":0}` immediately after startup is NORMAL during model load. Only suspect the omni key if events stay 0 well after the engine has been running (see backend-hung-recovery.md 401 section).

## Probing Under Heavy Load (pct exec times out)

When loadavg is high (9-15) inside CT <ID>, heavy commands time out while light ones answer. Verified workarounds:

**1. Background execution + file read (MOST RELIABLE).** The outer ssh may time out (exit 124) but the inner command still completes and writes its file:

```bash
# launch (outer may exit 124 — that's OK):
sshpass -p "$PW" ssh root@192.0.2.10 \
  "pct exec 310 -- bash -c 'export PATH=/usr/local/bin:\$PATH; (timeout 40 miloco-cli perceive logs --since 2h --limit 60 > /tmp/percept_out.txt 2>&1; echo DONE >> /tmp/percept_out.txt) & echo BG_LAUNCHED'"

# later, read the result file (light command, usually answers):
sshpass -p "$PW" ssh root@192.0.2.10 "pct exec 310 -- cat /tmp/percept_out.txt"
```

**2. nsenter escape hatch** — occasionally works when plain `pct exec` hangs (not reliable either, but worth one try):
```bash
pct exec 310 -- nsenter -t 1 -m -u -i -n -- bash -c 'cat /proc/loadavg; ss -tln | grep 1810; tail -3 /root/.openclaw/miloco/log/node_events.log'
```

**3. Host-side view** — `top -bn1 | grep -E "python3|supervis"` shows container processes under uid 100000. Host PIDs ≠ container PIDs (namespace offset) — never kill a host PID for container work; kill via `pct exec`.

## Escaping / Self-Kill Pitfalls

- **awk through nested ssh→pct exec→bash** mangles `$` even with `\$` (got `awk: 1: unexpected character '\'`). Write a small script to /tmp in the container first, then `bash /tmp/chk.sh`, then `cat` its output file.
- **pgrep -f "bash -c" + kill loop can kill your own executing shell** (observed exit 137 — the `for p in $(pgrep ...)` matched the shell running the loop itself). Exclude self: `pgrep -f <pat> | grep -v $$` or use a more specific pattern.
- **LVM-backed LXC rootfs is NOT readable from the host** — `/var/lib/lxc/310/rootfs/` exists but is empty for `rootfs: local-lvm:vm-310-disk-0`. You cannot `tail` container logs via that path; you MUST go through `pct exec`.
