---
name: miloco-perception
description: Monitor and troubleshoot the Miloco perception engine on CT <ID>/PVE — correct CLI commands, service health checks, and restart patterns.
tags: [smart-home, miloco, pve, ct310, monitoring, perception]
triggers:
  - miloco
  - perception engine
  - miloco-cli
  - CT <ID> service
  - perception logs
  - omni 401
  - crash loop
  - 网页登不进去
---

# Miloco Perception Engine — Operations & Troubleshooting

## CT <ID> Reachability Quick-Check

「网页登不进去 / 后端打不开」先分清**服务没起**还是**服务卡死**，三条命令定性（PVE 宿主机 `192.0.2.10`，密码 `<PASSWORD>`）：

```sh
sshpass -p '<PASSWORD>' ssh root@192.0.2.10 "uptime"                                    # 宿主机活着吗
sshpass -p '<PASSWORD>' ssh root@192.0.2.10 "timeout 10 pct exec 310 -- echo CT310_OK"  # 容器活着吗
sshpass -p '<PASSWORD>' ssh root@192.0.2.10 "timeout 10 pct exec 310 -- ss -lnt"        # 服务活着吗
```

- 宿主机不通 → 先修宿主机，别碰 CT <ID>。
- `CT310_OK` 秒回、但 `ss -lnt` 只剩 `25/22` → **容器重启过，supervisord 没起来**。miloco 只挂 supervisord、**没注册 systemd unit**，LXC 一重启就全无；配套签名：`ps aux` 只有 systemd/sshd/postfix、`miloco-backend.log` 的 mtime 停在几天前、网页 `http://<CT <ID>-IP>:1810/` 打不开。**这是没启动不是卡死，重启容器无效**：

```sh
sshpass -p '<PASSWORD>' ssh root@192.0.2.10 \
  "pct exec 310 -- /usr/local/bin/supervisord -c /root/.openclaw/miloco/supervisord.conf"
# 等 10~15s（startsecs=5 + 后端初始化），再确认 1810 在听
sshpass -p '<PASSWORD>' ssh root@192.0.2.10 \
  "timeout 10 pct exec 310 -- sh -c 'ss -lnt | grep 1810'"
```

- `1810` 在听但 `miloco-cli` 挂住 → 服务活着但卡死，走 `references/hung-container-recovery.md`。
- `pct exec` 本身超时 → 先看 `uptime` 的 load，再考虑 `pct reboot 310`；单次超时不能定死「容器挂了」。

**Pitfalls**

- `supervisorctl` 不在 `pct exec` 默认 PATH：一律 `/usr/local/bin/supervisorctl -c /root/.openclaw/miloco/supervisord.conf status`（报 `command not found` 别去装包）。
- 启动后日志狂刷 `unauthorized(401) … code:96008` 是**米家云 token 过期**：它让摄像头刷新失败但**不挡网页**；修复要用户自己重登米家，别把它当成「服务没起」的证据，也别揽成能替用户解决的事。
- 每次容器重启都得手工跑一遍上面的启动命令 —— 要根治得给 CT <ID> 加自启（systemd unit 或 PVE 启动钩子），动它之前先ask the user。

## ⚠️ Correct CLI Subcommands

The `miloco-cli` CLI has evolved — older subcommand names no longer work:

| ❌ Wrong | ✅ Correct | Purpose |
|----------|-----------|---------|
| `miloco-cli perception log` | `miloco-cli perceive logs` | Query perception event history |
| `miloco-cli perception status` | `miloco-cli perceive --help` | Discover available perceive subcommands |

📖 refs: `ct310-recovery.md` · `backend-hung-recovery.md` (omni 401) · `backend-restart-window.md` · `fallback-when-cli-hangs.md` · `perception-degradation.md` (401 loop) · `watchdog-selfstall-kill-loop.md` (SIGKILL loop) · `oom-crash-loop.md` (OOM = memory bump)
📖 **Device control syntax & device IDs**: see `references/device-control.md`
📖 **Hung container recovery** (stop+start, PATH fallback, backend warmup): see `references/hung-container-recovery.md`

When `miloco-cli` commands hang or timeout, the issue is usually the container, not the PVE host:

1. **PVE host reachable but CT <ID> stuck** — load average on PVE host may be very high (e.g. 11+). `pct exec 310 -- echo OK` may succeed once then subsequent calls hang.
2. **Diagnostic sequence** (do in this order):
   - `ping 192.0.2.10` — confirms PVE host network
   - `ssh ... root@192.0.2.10 "uptime"` — confirms PVE host load
   - `ssh ... root@192.0.2.10 "pct exec 310 -- echo CT310_OK"` — confirms CT <ID> is responsive (use timeout 10)
   - If CT <ID> echo succeeds but miloco-cli hangs → container is alive but miloco service is likely stuck (or PVE load is very high, see Pitfall below)
3. **If CT <ID> is unresponsive**: recommend user manually check / restart via PVE web UI or `pct reboot 310`
4. **Never assume "CT <ID> is down" from a single timeout** — try the echo test with timeout wrapper first

## Environment
- **Host**: PVE at `192.0.2.10` (ssh password: `<PASSWORD>`)
- **Container**: CT <ID> (LXC on PVE)
- **Backend port**: `1810` (HTTP, localhost on CT <ID>)
- **Service manager**: supervisord (`/root/.openclaw/miloco/supervisord.conf`)

## Access Pattern

**Preferred (most reliable)** — use full path directly, no `bash -c` wrapper:
```bash
sshpass -p "<PASSWORD>" ssh -o StrictHostKeyChecking=no root@192.0.2.10 \
  "pct exec 310 -- /usr/local/bin/miloco-cli perceive logs --since 1h --limit 20 --pretty"
```

**Fallback** — `bash -c` with PATH export (can intermittently hang):
```bash
sshpass -p "<PASSWORD>" ssh -o StrictHostKeyChecking=no root@192.0.2.10 \
  "pct exec 310 -- bash -c 'export PATH=/usr/local/bin:$PATH; miloco-cli perceive logs --since 1h --limit 20 --pretty'"
```

## Recovery Procedures

### OOM / Unresponsive Container

When `pct exec` commands to CT <ID> hang but `pct status 310` still shows "running", the container is likely OOM. Lightweight `/proc` commands still work under OOM:

```bash
# Load average (should be <5 for healthy; >10 = overloaded)
pct exec 310 -- cat /proc/loadavg

# Memory (free <50MB = critical)
pct exec 310 -- cat /proc/meminfo | head -3

# Basic connectivity test
pct exec 310 -- echo ok
```

**Recovery sequence:**
1. Remove stale lock file if `pct stop` hangs:
   ```bash
   ssh root@192.0.2.10 "rm -f /run/lock/lxc/pve-config-310.lock && pct stop 310"
   ```
2. Wait 5 seconds, then start:
   ```bash
   sleep 5 && ssh root@192.0.2.10 "pct start 310"
   ```

### supervisord Not Auto-Starting

After CT <ID> reboot, supervisord may not start. Start manually and verify:

```bash
# Start supervisord (daemonizes)
pct exec 310 -- supervisord -c /root/.openclaw/miloco/supervisord.conf

# Verify (MUST use -c flag — bare supervisorctl fails with "refused connection")
pct exec 310 -- supervisorctl -c /root/.openclaw/miloco/supervisord.conf status
```

⚠️ **Pitfall**: `supervisorctl` without `-c /root/.openclaw/miloco/supervisord.conf` fails because it cannot find the unix socket. Always pass the explicit config path.

### Health Check via HTTP

```bash
pct exec 310 -- curl -s -m 8 http://localhost:1810/health
# Expected: {"status":"ok"}
```

### SIGKILL Pattern (Memory Leak Indicator)

The supervisord log (`/root/.openclaw/miloco/log/supervisord.log`) may show repeated:
```
WARN exited: miloco-backend (terminated by SIGKILL; not expected)
```
This indicates the backend is being OOM-killed by the kernel. If this recurs frequently, consider increasing the CT <ID> memory allocation or investigating the backend for memory leaks.

**Confirm & quantify OOM** (on PVE): `dmesg -T | grep -i 'oom\|killed process' | tail -5` (expect `oom_memcg=/lxc/310`), `cat /proc/meminfo | head -3` (MemAvailable <50MB critical), `grep -c SIGKILL <supervisord.log>` (frequency). Empty `perceive logs` after restart = history cleared, not "no events". Reference: `references/2026-08-01-oom-sigkill-loop.md`.

⚠️ **PITFALL — `bash -c` wrapper can hang; prefer full-path for `perceive logs`**: `pct exec 310 -- bash -c 'export PATH=...; miloco-cli ...'` may hang 30s+ even when the container is responsive — switch to full-path `/usr/local/bin/miloco-cli` immediately. **EXCEPTION — `service status`** shells out to `supervisorctl` with no PATH → full-path crashes `FileNotFoundError: 'supervisorctl'`; query supervisor directly: `pct exec 310 -- /usr/local/bin/supervisorctl -c /root/.openclaw/miloco/supervisord.conf status`. Reference: 2026-07-11 + 2026-08-01 (`references/2026-08-01-oom-sigkill-loop.md`).

⚠️ **PITFALL — Pre-run 30s timeout too short for `bash -c` wrapper**: wrapper latency pushes execution to 60-120s, so a pre-run `⚠️ 获取感知日志超时` usually means slow wrapper, not a broken service. Attempt manual SSH recovery with 120s timeout before assuming failure. Reference: `references/2026-07-12-cron-pre-run-false-alarm-recovery.md`.

⚠️ **PITFALL — Pre-run timeout may indicate auto-recovery in progress**: when the pre-run script times out, the service may have been mid-restart; by the time you SSH in it may already be back (`service status` shows `running: true`, `uptime_seconds` < 30s). **Do not escalate** — wait 15-20s and retry `perceive logs`. Only intervene if status fails or uptime stays low for >60s. ⚠️ But auto-recovery can mask an OOM SIGKILL loop — check SIGKILL frequency + dmesg before declaring false alarm (see SIGKILL section). Reference: `references/2026-07-12-cron-auto-recovery-no-intervention.md`.

### Fallback: `lxc-attach` when `pct exec` hangs

If `pct exec 310 -- <cmd>` hangs but `pct status 310` returns `running`, the container is alive — it's the `pct exec` wrapper that's broken. Use `lxc-attach` instead:

⚠️ **PITFALL — Partial pct exec hang**: `pct exec 310 -- <cmd>` can be *partially* functional — it passes through trivial commands (`echo hello`) while hanging on anything that spawns a subprocess or does I/O (`uptime`, `ls`, `ps aux`). **Do not test with `echo hello`** — it will give a false positive. Test with a real command like `uptime` or `ss -tlnp` before trusting pct exec. If echo works but uptime hangs, switch to lxc-attach immediately. Reference: `references/2026-07-08-cron-partial-pct-exec-recovery.md`.

⚠️ **PITFALL — `which` fails but binary exists in partial hang**: When pct exec is in partial hang, `which miloco-cli` may return NOT_FOUND or fail with lxc-attach exec errors — NOT because the binary is missing, but because `which` is a shell built-in that may not work in minimal pct exec environments. **Use `test -f /usr/local/bin/miloco-cli` instead** — it succeeds even when `which`, `ls`, and other commands hang. If `test -f` returns EXISTS but `which` fails, the container is in partial hang, not missing the binary. Reference: `references/2026-07-11-cron-test-f-vs-which.md`.

```bash
sshpass -p "<PASSWORD>" ssh -o StrictHostKeyChecking=no root@192.0.2.10 \
  "lxc-attach -n 310 -- bash -c 'export PATH=/usr/local/bin:$PATH; <command>'"
```

⚠️ **PITFALL**: `lxc-attach` bypasses Proxmox's resource tracking, so use it for diagnostics but prefer `pct exec` for lifecycle operations (stop/start). Also: `lxc-attach` may not have the same PATH — always export explicitly.

⚠️ **PITFALL — Partial lxc-attach hang**: Just like `pct exec`, `lxc-attach` can be *partially* functional — `echo HELLO` works but `pgrep`, `ss`, `ps aux`, `curl` all hang. **Do not assume lxc-attach works just because echo succeeds.** Test with `ps aux` or `pgrep -la python3` before trusting lxc-attach for diagnostics. If echo works but `ps aux` hangs, try `pgrep -la python3` and `pgrep -la miloco` — **`pgrep` often works when `ps aux` hangs** in partial hang scenarios. If pgrep reveals PIDs, do PID-targeted nuclear restart (kill all, clear socket, restart supervisord) instead of the more disruptive container stop/start. If pgrep also hangs, then PID-targeted kills are impossible — go straight to container stop/start. Reference: `references/2026-07-08-cron-lxc-attach-partial-hang.md`, `references/2026-07-09-cron-pgrep-over-ps-aux.md`.

⚠️ **PITFALL — Lock file blocks `pct stop`**: After `pct exec` hangs, `/run/lock/lxc/pve-config-310.lock` may be left stale, causing `pct stop 310` to fail with `"can't lock file ... got timeout"`. **Always clear proactively before attempting `pct stop`** (zero-cost, prevents the error entirely):
```bash
sshpass -p "<PASSWORD>" ssh root@192.0.2.10 "rm -f /run/lock/lxc/pve-config-310.lock && echo LOCK_CLEARED"
```

## Correct CLI Commands

| Action | Command |
|--------|---------|
| List perception-capable devices | `miloco-cli perceive devices` |
| Get perception logs | `miloco-cli perceive logs --limit N` |
| Get logs (time window) | `miloco-cli perceive logs --since 1h --limit 20` |
| Get logs (pretty) | `miloco-cli perceive logs --since 30m --pretty` |
| Get logs (JSONL) | `miloco-cli perceive logs --jsonl` |
| Active multimodal query | `miloco-cli perceive query` |
| Clear perception cache | `miloco-cli perceive clear` |
| Check CLI help | `miloco-cli perceive --help` |
| Start service | `miloco-cli service start` |
| Stop service | `miloco-cli service stop` |
| Restart service | `miloco-cli service restart` |
| Control device | `miloco-cli device control <DID> <prop> <value>` |
| Service logs | `miloco-cli service logs --lines N` |

> **Note**: The skill is near its size limit. Detailed diagnostics and pitfalls are in `references/diagnostics.md`.

⚠️ **PITFALL**: The subcommand is `perceive` (verb), NOT `perception` (noun).
Using `perception` yields: `Error: No such command 'perception'. (Did you mean one of: 'perceive', 'person'?)`

## Cron Job Recovery — Pre-Run Script Timeout

When the cron pre-run script fails, the perception logs cannot be fetched automatically. The agent must diagnose and recover manually. **However**, failure does NOT always mean the service is broken — high container load can make miloco-cli slow enough to trigger timeouts while the backend is healthy. Always check the quick-reference path below before assuming failure. Reference: `references/2026-07-09-cron-high-load-false-alarm.md`.

Known pre-run failure strings:
- `⚠️ 获取感知日志超时` — see `references/2026-08-01-oom-sigkill-loop.md`
- `"获取感知日志超时"` — timeout fetching logs (most common)
- `"⚠️ 无法解析感知日志:"` — received data but couldn't parse it. **Can be a false alarm**: when host diagnostics show miloco.main healthy (Sl state, moderate CPU), the service is fine — the parse failure is from pre-run zombie pileup, not a backend issue. Kill host-level zombies + retrieve logs directly. See `references/2026-07-12-cron-parse-failure-false-alarm.md`. Contrast with genuine B/B+ failure: `references/2026-07-10-cron-b-plus-hybrid-recovery.md`.

Quick-reference path:

⚠️ **PITFALL — Do NOT skip steps in the quick-reference path**: common error is checking PVE reachability (step1) then jumping straight to `perceive logs` (step7), skipping steps2-6. This wastes 30-120s on a slow CLI query that will fail, when steps2-6 (port/health/ps checks) take 5-10s each. **Always follow the sequence in order.** Reference: 2026-07-12 cron session.

1. **PVE reachable?** `sshpass ... ssh root@192.0.2.10 "echo PVE_OK"` — if PVE is down, nothing to do from here.

2. **PVE host load?** — if load average > 15, PVE host is overloaded. ALL `pct exec` commands will hang regardless of container health. This is NOT a container problem — the PVE host itself needs investigation. **Do not waste time on container-level diagnostics** — first check host `ps aux --sort=-%cpu | head -15` and kill stuck processes from the host shell (see host-level diagnostic block below). If load drops below 10 after cleanup, proceed with container diagnostics. If load stays >10 after cleanup, the issue is genuine (e.g., miloco.main at >120% CPU doing inference, Minecraft server) — report the specific offender to user. Reference: `references/2026-07-10-cron-pve-host-overload.md`.

   If load is 10-15, it's elevated but may be manageable. **Before attempting any container commands, always clean up host-level zombie processes first** (see host-level diagnostic block below). In this session, killing 15 host-level zombies dropped load from 9.59 → 4.95, making container commands viable. Proceed with caution after cleanup — if load stays >10 after cleanup, the issue is genuine (e.g., miloco.main at >120% CPU doing inference, Minecraft server).

⚠️ **False Alarm Shortcut — miloco.main doing inference**: After running host `ps aux --sort=-%cpu | head -15` in step 2, check if miloco.main matches this pattern: (1) CPU >100%, (2) STAT is `Sl` (NOT Dl, Ds, D, or R), (3) CPU TIME accumulated in minutes (not seconds). If ALL three match → **this is a false alarm**. miloco.main is actively inferring; the pre-run timeout was CPU contention + zombie pileup. **Skip steps 3-7 entirely.** Instead: (a) kill pre-run zombies from host shell (see below), (b) report "Service healthy, miloco.main inferring at X% CPU", (c) stop. This saves ~2-3 minutes of diagnostic timeouts. Reference: `references/2026-07-12-cron-false-alarm-high-cpu-shortcut.md`.

**Concrete host-level diagnostic** (run on PVE, not inside container — container commands will hang):
```bash
sshpass -p "<PASSWORD>" ssh root@192.0.2.10 "ps aux --sort=-%cpu | head -15"
```
This shows all processes across all CTs/VMs ranked by CPU. Common culprits:
- `miloco.main` at >100% CPU — perception pipeline running hot (may be stuck in inference loop, or genuinely processing)
- `miloco-cli service start / perceive logs` processes in R/D state — **pre-run retry pileup** (the cron pre-run script + agent diagnostics both spawned stuck CLI wrappers; see Scenario D pitfall)
- Java/Minecraft servers — long-running, high memory (6GB+), moderate CPU
- Other CTs — list with `pct list` + `pct status` for each

When the top consumer is inside CT <ID>, the fix is container stop/start. When it's a different CT/VM, report the specific offender.

⚠️ **PITFALL — Host-level PIDs don't work with `pct exec kill`**: The `ps aux --sort=-%cpu` command on the PVE host shows container processes with **host-level PIDs** (e.g., PID 2691778 for miloco.main). These PIDs are from the host's PID namespace and do NOT match the container's internal PID namespace. Attempting `pct exec 310 -- kill -9 <host_PID>` will fail with "No such process". **Always get container-internal PIDs** by running `pct exec 310 -- ps aux | grep miloco` instead. The host-level ps is useful for identifying *which* process is consuming CPU, but the actual PID for kill operations must come from inside the container. Reference: 2026-07-11 cron session — host ps showed PID 2701471 for a stuck miloco-cli, but `pct exec 310 -- kill -9 2701471` failed; container-level ps showed the same process as PID 101598.

⚠️ **PITFALL — Container processes CAN be killed from PVE host shell**: While `pct exec 310 -- kill -9 <host_PID>` fails (PID namespace mismatch), `kill -9 <host_PID>` FROM THE PVE HOST SSH SHELL works. Container processes visible in host `ps aux` (UID 100000) exist in the host's PID namespace, so the host shell's `kill` command operates on them directly. **Use this as a fast cleanup path** when pct exec hangs but you can see stuck processes from the host. Example: `ssh root@192.0.2.10 "kill -9 <host_PIDs>"`. Reference: `references/2026-07-12-cron-stuck-init-agent-pileup.md`.

⚠️ **PITFALL — Host-level pre-run zombies ARE killable on the host**: The pre-run script spawns `miloco-cli service start` processes on the PVE host (not inside the container). These are SSH wrappers + CLI processes that run in the host's PID namespace. Unlike container processes (which need container-internal PIDs for kills), host-level pre-run zombies can be killed directly on the host shell: `kill -9 <PID>`. Check with `ps aux --sort=-%cpu | head -15` on the host — look for `miloco-cli service start` or `bash -c miloco-cli service start` processes with low CPU time (indicating stuck state). Killing these reduces PVE host load immediately. Reference: `references/2026-07-11-cron-host-pid-namespace-mismatch.md` — 4 stuck host-level `miloco-cli service start` zombies consuming ~23% CPU; `kill -9` on host reduced load from 16.70 to 9.8.

⚠️ **PITFALL — Host-level kill may enable auto-recovery without restart**: After killing pre-run zombie processes from the host shell, the service may auto-recover WITHOUT nuclear restart or container stop/start. In the 2026-07-12 incident, killing stuck miloco-cli processes + supervisord from the host allowed miloco.main to restart independently (new PID, no supervisord). Health passed and `total_inferences: 1` confirmed fresh inference. **This is the lightest recovery path** — try host-level zombie cleanup first, then verify health before escalating to nuclear restart. Some PIDs may already be dead ("No such process" is not an error — other killed processes may have been sufficient). Reference: `references/2026-07-12-cron-pre-run-pileup-host-kill-recovery.md`. **Variant — supervisord alive**: When supervisord is NOT killed (only CLI zombies are targeted), it handles miloco.main restart automatically. This is the more common and easier case — kill CLI zombies, supervisord restarts miloco.main, health passes. Reference: `references/2026-07-12-cron-supervisord-alive-zombie-cleanup.md`.

⚠️ **PITFALL — Duplicate supervisord processes spawn duplicate miloco.main**: After host-level cleanup of stuck CLI processes, supervisord may auto-restart miloco.main. If TWO supervisord processes exist (from concurrent recovery attempts), each spawns its own miloco.main — resulting in duplicate miloco.main processes competing for port 1810 and doubling CPU load. **Diagnostic**: after killing CLI zombies, re-check `ps aux --sort=-%cpu` — look for multiple supervisord entries (same start time, similar command) and multiple miloco.main entries. **Fix**: kill the duplicate supervisord (the one with less CPU time) and its miloco.main child from the host shell. The original supervisord + miloco.main will continue operating. Reference: `references/2026-07-12-cron-duplicate-supervisord-cleanup.md` — host load 16.67 from 2× supervisord + 2× miloco.main + CLI pileup; killing duplicate pair dropped load to 12.22.

⚠️ **PITFALL — Host-level ssh/lxc-attach wrappers also pile up**: The pre-run script also spawns ssh + lxc-attach wrapper processes on the PVE host. These appear in `ps aux --sort=-%cpu` as `lxc-attach -n 310 --keep-env -- /usr/local/bin/miloco-cli ...` and `ssh ... lxc-attach -n 310 -- bash -c 'miloco-cli ...'`. They accumulate during retry pileup and block container commands. **Kill ALL host-level wrapper PIDs** (not just miloco-cli processes) before attempting container stop/start. This is especially important when pct exec and lxc-attach both hang — the stale wrappers are part of the blocking chain. Reference: `references/2026-07-11-cron-host-wrapper-cleanup.md`.

3. **CT <ID> running?** `pct status 310` — fast (<2s). If "stopped", container crashed.
- If lxc-attach works but pct exec doesn't, it's a pct exec wrapper issue, not a container hang — proceed to step 5. If both hang → **check lxc-attach ps aux** before escalating:
- `lxc-attach -n 310 -- ps aux` works → **container alive, miloco deadlocked** → go to Scenario A "PID-targeted nuclear restart" path (NOT container stop/start). You can see PIDs, so kill them directly.
- `lxc-attach -n 310 -- ps aux` hangs → true container hang → container stop/start (Scenario A). ⚠️ Do NOT try `nsenter` from PVE host as a workaround — it cannot kill LXC container processes (PIDs don't map). Go straight to `pct stop/start`.
5. **Port 1810 listening?** `ss -tlnp | grep 1810` — if no output, backend dead → check `ps aux | grep miloco` for stuck processes (Scenario B). If port IS listening, proceed to step 6.
6. **Health OK?** `curl http://127.0.0.1:1810/health` — if OK, service is alive; try `perceive logs --since 30m` (NOT `--limit N`, which may return stale cached data with `total_inferences: 0`). ⚠️ If health returns exit code 7 (connection refused) despite port listening → **Scenario B+ (zombie-bound socket)** — old miloco.main holds the port but is dead. Go to PID-targeted nuclear restart.
7. **Fresh inferences?** Check `total_inferences` in the response. If `0` and timestamps are days old → Scenario E (stale pipeline).

⚠️ **PITFALL — `perceive logs --limit N` or wide `--since` returns stale data on fresh start**: After a container restart, `--limit N` returns cached entries from the previous session with old timestamps. Similarly, `--since 1h` (or any wide window) includes stale cached entries whose timestamps fall within the window. **Use a short `--since` window** (`--since 10m` or `--since 30m`) to see only fresh post-restart inferences. `total_inferences: 0` confirms no fresh inference has occurred yet. `total_inferences: 1+` with recent timestamps confirms fresh data. In this session, `--since 1h` returned 10 stale entries with `total_inferences: 0`, while `--since 10m` (queried seconds later) returned 1 fresh entry with `total_inferences: 1`.

## Health Check

### Fastest triage: port binding check
```bash
pct exec 310 -- bash -c 'ss -tlnp | grep 1810'
# Fallback if pct exec hangs:
lxc-attach -n 310 -- bash -c 'ss -tlnp | grep 1810'
```
If no output → port 1810 not listening → backend dead or stuck. Check `ps aux | grep miloco` — if no miloco processes at all → Scenario B0 (backend completely dead, needs fresh start). If processes exist but port unbound → Scenario B (stale socket). This check takes ~5s vs 20-30s for `perceive logs`/`perceive devices` timeouts.

### Health endpoint states

```bash
curl -s http://127.0.0.1:1810/health
```

| Response | Meaning | Action |
|----------|---------|--------|
| `{"status":"ok"}` | Service healthy | Proceed normally |
| `{"status":"unhealthy"}` | Service degraded but operational (e.g., HEVC decoder dropping frames) | Check `perceive logs --since 30m` and `perceive devices` — if logs return fresh data and cameras are online, the pipeline is functional despite the degraded status. **Do NOT escalate to restart.** The "unhealthy" status reflects decoder issues, not backend failure. |
| Connection refused / timeout | Backend not responding | Proceed to port binding check and Scenario diagnostics |

⚠️ **PITFALL — `{"status":"unhealthy"}` is NOT a restart trigger**: The health endpoint returns `"unhealthy"` when the service detects internal degradation (most commonly HEVC decoder frame drops). However, the perception pipeline may still be fully functional — cameras online, fresh inferences being generated, `total_inferences > 0`. Always verify with `perceive logs` and `perceive devices` before deciding on action. In the 2026-07-12 late-night cron run, health returned `"unhealthy"` but `perceive logs --since 30m` returned 7 fresh inferences with current timestamps and all 3 cameras online. The HEVC frame drops were cosmetic degradation, not pipeline failure. Reference: `references/2026-07-12-cron-health-unhealthy-pipeline-ok.md`.

### Service status probe (works during backend initialization)
```bash
miloco-cli service status   # talks to supervisord IPC, not backend HTTP
```
Returns `running`, `pid`, `uptime_seconds` even when the backend HTTP server (port 1810) isn't accepting connections yet. **Use this to distinguish "backend initializing" from "backend dead"**: if `service status` shows `running` with low `uptime_seconds` (< 30s), the backend just restarted and needs time — wait 15-20s and retry. If `service status` itself fails, supervisord is down (Scenario B0).

⚠️ **PITFALL**: `miloco-cli service status` uses supervisord's UNIX socket, NOT the backend's HTTP API on port 1810. It can succeed while `perceive logs` and `perceive devices` both fail. Do not assume the backend is fully operational just because `service status` returns OK — always verify with an actual `perceive` subcommand.

⚠️ **PITFALL — `service status` false negative after container restart**: After a container stop/start recovery, `miloco-cli service status` may timeout (10s+) even though the backend is actually alive and `perceive logs` works. The supervisord UNIX socket may be slow to re-establish after the fresh supervisord start. **Do not interpret `service status` timeout as "supervisord is down"** — verify with `perceive logs --since 30m` or `curl http://127.0.0.1:1810/health` instead. If `perceive logs` returns fresh data, the service is healthy regardless of `service status` behavior. This is the inverse of the above pitfall — both false-positive and false-negative `service status` results occur post-restart. Reference: 2026-07-09 container recovery — `service status` hung but `perceive logs --since 30m --jsonl` returned 6 fresh entries with `total_inferences: 1`.

⚠️ **PITFALL — `service status` fails with `FileNotFoundError: supervisorctl`**: `miloco-cli service status` internally calls `supervisorctl` as a subprocess. If `/usr/local/bin` is not on the container's default PATH (which it often isn't in `pct exec` environments), `supervisorctl` won't be found and the command crashes with `FileNotFoundError: [Errno 2] No such file or directory: 'supervisorctl'`. **Do not treat this as supervisord being down** — it's a PATH issue. Fall back to `curl -s --connect-timeout 5 http://127.0.0.1:1810/health` for health checking. Reference: 2026-07-12 cron session — `service status` failed with this error while health endpoint returned `{"status":"ok"}`.

### Quick connectivity check (fast, works even when logs hang)
```bash
miloco-cli perceive devices   # returns device list in <5s if backend is alive
```

⚠️ **PITFALL — Transient CLI connection failure**: `miloco-cli perceive logs` may fail with `{"error": "cannot connect to Miloco backend at http://127.0.0.1:1810"}` even when port 1810 is listening and `curl -s http://127.0.0.1:1810/` returns HTML. This is a transient issue — the CLI's HTTP client may hit a brief unresponsive window. **Diagnose first**: check `miloco-cli service status` — if `uptime_seconds` is very low (< 30s), the backend just restarted and is still initializing. **Fix**: wait 10s, then retry. If it fails twice consecutively, then investigate further (check process state, port binding).

### Full diagnostic (requires pct exec)
```bash
# 1. Check if port 1810 is listening
ss -tlnp | grep 1810

# 2. HTTP health endpoint
curl -s http://127.0.0.1:1810/health
# Expected: {"status":"ok"}

# 3. Check for stuck miloco-cli processes (key diagnostic!)
ps aux | grep miloco | grep -v grep
```

⚠️ **PITFALL — Fake-healthy collapse**: After a fresh startup, `perceive logs` may return stale cached data (timestamps days/weeks old). **Check `total_inferences` in the response** — if it's `0`, the pipeline has NOT started inferring yet. The stale data is from cache, not live inference. If the next `perceive logs` call fails or the port drops, the pipeline has collapsed — do NOT wait for it to "warm up." Reference: `references/2026-07-06-cron-fake-healthy-collapse.md`.

## Restart Budget — HARD STOP

**Maximum restart attempts before declaring upstream failure: 2.**

After **2 failed restart attempts** (soft restart + nuclear restart or container restart), **STOP RESTARTING**. The service is healthy — the perception pipeline input/output is broken. Further restarts waste time and risk cascading container hangs.

Decision tree:
1. First failure → try soft restart (Scenario B/D step 1)
2. Soft restart fails → try nuclear restart or container stop/start (Scenario A/D step 2)
3. **Nuclear restart fails → STOP. Gather diagnostics, then report upstream issue to user. Do NOT retry.**

**⚠️ Pre-reporting diagnostic — ALWAYS gather before declaring upstream failure**: When the restart budget is exhausted, DO NOT just say "upstream failure" and stop. Gather diagnostic info BEFORE reporting to give the user actionable starting points:
```bash
# 1. Service logs — shows HEVC drops, model API errors, camera failures
miloco-cli service logs --limit 50
# 2. Camera status — are cameras reachable?
miloco-cli perceive devices
# 3. Port binding — is backend alive?
curl -s http://127.0.0.1:1810/health
```
If `pct exec` hangs, use `lxc-attach` fallback. If both hang, report without diagnostics (container is degraded). Common root causes found in service logs:
- `drop non-key frame, MIoTCameraCodec.VIDEO_HEVC` → HEVC decoder failure (persistent, not fixable by restart)
- Model API errors (timeout, 429, 500) → API rate limiting or outage
- Camera connection failures → network or camera issues
Without service logs, the user has no starting point for manual investigation.

The pipeline may appear to start (health OK, models load, cameras online) but still fail to produce fresh inferences. This is an upstream problem — not fixable by restarting the miloco service.

⚠️ **PITFALL — Restart budget counting**: The 2-restart budget counts **pipeline restart attempts** only. A container stop/start done purely to restore basic container functionality after degradation (when the pipeline is already declared broken) does NOT count against the budget. Example: after 2 failed pipeline restarts + container degradation, a final `pct stop/start` to get the container back to a usable state is acceptable. Do not confuse "restoring the container" with "restarting the pipeline." **However**, if a container stop/start is done to fix degradation and the pipeline subsequently collapses (warm-then-die), the NEXT container stop/start counts as a pipeline restart attempt — because you're now restarting to fix the pipeline, not just the container. Track collapses after each recovery, not just the recovery itself. Reference: `references/2026-07-09-cron-repeated-warm-then-die.md`.

⚠️ **PITFALL — Scenario A→E cascade**: Fixing a container hang (Scenario A) via stop/start may expose a latent Scenario E (stale pipeline). The container recovery succeeds but the perception pipeline is separately broken. Do not assume fixing A also fixes the pipeline — always verify `total_inferences` after recovery. Reference: `references/2026-07-06-afternoon-cron-a-e-cascade.md`.

## Restart Pattern

### Startup Sequence — Healthy vs Stuck

When the miloco service starts (after container restart or supervisord start), the backend goes through a predictable initialization sequence. Knowing what "normal" looks like helps diagnose stuck startups quickly.

**Healthy startup sequence** (observed in logs):
```
00:05:12 - supervisord starts
00:05:12 - miloco.main starts
00:05:12 - ORT session loaded (human_body_reid_v2.onnx)
00:05:12 - backfill_reid_embeddings done
00:05:12 - Application startup complete
00:05:12 - Uvicorn running on http://0.0.0.0:1810
00:05:19 - [multicam] n_cam=1 | 1179415436-前院 (first camera connects)
00:05:21 - ORT session loaded (det_4C.onnx)
00:05:21 - tracking_service created for device=1179415436
00:05:21 - IdentityEngine started for device=1179415436
00:05:21 - video frame decoded successfully → inference begins
```

**Stuck startup pattern** (indicates upstream pipeline failure):
```
... same as above until camera connects ...
00:05:21 - drop non-key frame, MIoTCameraCodec.VIDEO_HEVC (×5-10)
00:05:22 - video frame is empty (×2-3)
00:05:25 - tracking_service created
00:05:25 - IdentityEngine started
(pipeline never produces fresh inference → perceive logs hangs after ~60s)
```

**Key diagnostic**: If `perceive logs --limit 1` hangs **more than 30 seconds** after a fresh service start (supervisord started, health OK, models loaded), the perception pipeline is fundamentally broken. This is NOT a slow-start issue — it's an upstream failure. Do not restart again; report to user.

**What to check when pipeline is stuck**:
1. `perceive devices` — are cameras online? (Yes = cameras reachable, issue is inference)
2. `service logs` — any model API errors? (timeout, 429, 500, connection refused)
3. `perceive query` — does active query work? (If yes, the pipeline partially works)

### Scenario A: `pct exec` hangs but `pct status` shows running (container-level hang)
When even basic `pct exec` commands (`uptime`, `ps aux`) hang for 10-15+ seconds, the container itself is in a bad state. `pct status` still returns `running` but nothing works inside. **Nuclear restart won't work** because you can't run any command inside the container (killall, supervisord, etc. all unreachable).

**⚠️ IMPORTANT — Container probe before escalating**: Not all `pct exec` hangs mean the container is dead. Use the **3-level probe** to distinguish container hang from miloco deadlock:

**⚠️ CRITICAL — When pct exec hangs for ALL commands, fall back to lxc-attach for the probe.** `pct exec` can hang even when the container is alive (the wrapper itself is broken). Try lxc-attach directly:
```bash
# lxc-attach fallback for the probe
lxc-attach -n 310 -- echo HELLO
lxc-attach -n 310 -- pgrep -la python3
lxc-attach -n 310 -- curl -s --connect-timeout 5 http://127.0.0.1:1810/health
```

Standard probe (when pct exec is responsive):
```bash
# Level 1: Basic exec test
pct exec 310 -- echo HELLO
# Level 2: Process inspection (almost always works if container is alive)
pct exec 310 -- ps aux
# Level 3: Port / miloco-specific check
pct exec 310 -- ss -tlnp | grep 1810
```

Quick binary check (works even when ps/ls/which hang):
```bash
# Check if miloco-cli exists without spawning subprocesses
pct exec 310 -- test -f /usr/local/bin/miloco-cli && echo EXISTS || echo NOT_FOUND
```
This uses `test -f` (shell builtin) instead of `which` (requires subprocess). Use this to distinguish "binary missing" from "container in partial hang" — if `test -f` says EXISTS but `miloco-cli` hangs, it's a partial hang, not a missing binary. See `references/2026-07-11-cron-test-f-vs-which.md`.
- **All 3 hang AND lxc-attach can't even run `echo HELLO`** → **True container-level hang** → container stop/start required (Scenario A fix below). This is distinct from miloco deadlock — the container itself is unresponsive. Reference: `references/2026-07-08-cron-both-hang-container-stop.md`. **If you also try `pgrep` via lxc-attach and it hangs**, this further confirms true container hang (not partial hang). In partial hangs, pgrep works when ps aux hangs; when pgrep also hangs, PID-targeted kills are impossible and container stop/start is the only option. Reference: `references/2026-07-09-cron-true-container-hang-pgrep-confirms.md`
- **All 3 hang, lxc-attach `echo` works BUT `ps aux`/`pgrep` also hang** → **lxc-attach partial hang** (same pattern as pct exec partial hang — trivial commands pass, subprocess-spawning commands hang). Can't find PIDs → can't do PID-targeted kills → **container stop/start required** (same as true container hang). Do NOT attempt PID-targeted kills — you can't get process info. Reference: `references/2026-07-08-cron-lxc-attach-partial-hang.md`
- **All 3 hang, lxc-attach `echo` AND `ps aux` work (but `ss`/`curl` hang)** → **Container alive but miloco deadlocked** → kill stuck processes by PID, clear socket, restart supervisord. **Do NOT do container stop/start** — it's unnecessary and disruptive. ⚠️ **COMMON MIS-ESCALATION**: When `uptime` hangs but `ps aux` works, it's tempting to escalate to container stop/start because the "partial hang" pattern feels severe. But the ability to run `ps aux` means you can get PIDs — use PID-targeted nuclear restart instead. This saves ~60s of container restart time and avoids disrupting other container services. Reference: `references/2026-07-08-cron-d-state-recovery.md`
- **pgrep works, `echo` and `ps aux` don't** → **Lighter recovery possible**: Use pgrep to inspect process state. If pgrep shows `supervisord` running + miloco.main as `<defunct>` (zombie) + stuck `miloco-cli` processes → **kill only the stuck miloco-cli processes** — supervisord will auto-restart miloco.main. No nuclear restart or container stop/start needed. This is faster than the standard nuclear restart path. Verify with `pgrep -la python3` (should show fresh non-defunct miloco.main) and `curl health`. Reference: `references/2026-07-10-cron-zombie-miloco-supervisord-auto-recovery.md`
- **Level 1+2 work, Level 3 hangs** → Container is alive, miloco processes are deadlocked → kill stuck processes by PID, clear socket, restart supervisord.
- **Level 1 hangs but lxc-attach works** → `pct exec` wrapper broken → use lxc-attach for all subsequent commands

⚠️ **PITFALL — `nsenter` from PVE host cannot kill LXC container processes (2026-07-10)**: When both `pct exec` and `lxc-attach` hang, you might try `nsenter -t <container_init_pid> -p -- kill -9 <PIDs>` to kill processes from the PVE host. **This does NOT work** — the PIDs visible via host `ps aux` don't map correctly into the container's PID namespace via nsenter. All kill attempts return "No such process" despite the processes being clearly visible. Do NOT waste time on this approach. Go directly to container stop/start. Reference: `references/2026-07-10-cron-nsenter-fails-for-lxc-kills.md`.

**Fix** (true Scenario A): Container stop/start from PVE host:
```bash
# 0. Preemptive lock file clear (prevents pct stop timeout)
sshpass -p "<PASSWORD>" ssh root@192.0.2.10 "rm -f /run/lock/lxc/pve-config-310.lock"
# 1. Stop and restart container
pct stop 310 && sleep 3 && pct status 310  # verify stopped
pct start 310 && sleep 10 && pct exec 310 -- echo PVE_OK  # verify exec works
```
⚠️ After container restart, the miloco service **may auto-start** if the restart was clean (pct exec was only partially hanging, not fully dead). Supervisord and miloco-backend can both auto-start without manual intervention. **Check before starting**: try `supervisord -c /root/.openclaw/miloco/supervisord.conf` — if you get "Another program is already listening on a port", supervisord is already running. Use `supervisorctl -c /root/.openclaw/miloco/supervisord.conf status` to check if the backend is RUNNING with low uptime (still initializing). Wait 15-20s, then retry `perceive logs`. If the restart was **degraded** (pct exec was hanging badly, both pct exec and lxc-attach partially broken), supervisord is less likely to auto-start — proceed with manual start. Reference: `references/2026-07-10-cron-supervisord-auto-start-init.md`.

After a **degraded** container restart, `miloco-cli service start` is more likely to truly fail — use supervisord directly. After a **clean** restart, `service start` MAY work but often hangs for 40+ seconds (the CLI times out at 20s while the service starts in the background). If it hangs, check `miloco-cli service logs` — if you see initialization progress (ORT models loaded, cameras connecting, subscriptions synced), the service is starting and will complete in 30-40s. Reference: `references/2026-07-09-cron-service-start-slow-after-clean-restart.md`.
```bash
pct exec 310 -- bash -c 'rm -f /root/.openclaw/miloco/supervisor.sock; /usr/local/bin/supervisord -c /root/.openclaw/miloco/supervisord.conf'
```
Wait 15 seconds after supervisord start for the backend to bind port 1810, then verify with `curl -s http://127.0.0.1:1810/health`. ⚠️ After a container restart, port binding consistently takes ~25-30s — if the first health check at 15s fails, retry at 30s before escalating. Do not assume failure at 15s. (2026-07-08 and 2026-07-10 data: health unreachable at 15s, succeeded at 30s.)

### Scenario B−: Backend stuck during initialization

supervisord is running, miloco.main process exists but is stuck in initialization — never bound port 1810. Key diagnostic: `ps aux` shows miloco.main with extremely low accumulated CPU time relative to its wall-clock uptime. Service logs may show startup messages (`Database initialization completed`, `Manager initialization started`, even `Server is ready`) but port 1810 is never bound. `curl http://127.0.0.1:1810/health` returns exit code 7. `ss -tlnp` shows port 1810 is NOT in the listening ports.

**State patterns observed**:
- **Dl state** (Uninterruptible Sleep) with ~1-2s CPU time — classic B− (2026-07-12 incident)
- **Sl state** (sleeping, multi-threaded) with ~35s CPU time over 8+ hours — also B− (2026-07-13 cron). The Sl state means the process is threaded but stuck, not doing I/O. The key signal is low CPU time relative to wall-clock uptime.

**Distinguishing from other scenarios**:
- vs Scenario B (port unbound): B has alive-but-stuck processes; B− has a process stuck during init with near-zero CPU time
- vs Scenario B+ (zombie-bound socket): B+ has port LISTENING but health unreachable; B− has port never bound
- vs Scenario E (stale pipeline): E has health OK and port bound; B− has no port binding at all
- vs Scenario D (CLI pileup): D has health OK but CLI hangs; B− has health failing from the start

**Fix**: Nuclear restart (same as B+ — kill supervisord + miloco.main, clear socket, restart supervisord). The stuck init process won't respond to soft restart. Port binding takes ~25-30s after supervisord start — check health at 10s, 20s, 30s intervals.

⚠️ **PITFALL — Stuck init looks like healthy process**: A miloco.main with low CPU time after hours looks like it's "running" in `ps aux`. Check CPU time column — a process running for hours with <60s CPU time is stuck, not healthy. The state can be Dl (I/O-bound stuck) OR Sl (threaded but stuck) — both indicate B−.

### Scenario B0: Backend completely dead (no miloco processes at all)
No `ps aux | grep miloco` shows any miloco process — not supervisord, not miloco.main, nothing. Port 1810 is not listening. The backend was either never started or crashed without supervisord restart.

**Quick fix** (when you just need the backend up):
```bash
# Via lxc-attach (since pct exec may be hanging)
lxc-attach -n 310 -- bash -c 'nohup /usr/local/bin/miloco-backend > /var/log/miloco-backend.log 2>&1 &'
# Wait 5-10s for port binding, then verify
lxc-attach -n 310 -- bash -c 'ss -tlnp | grep 1810'
```

**Proper fix** (restart supervisord for managed lifecycle):
```bash
lxc-attach -n 310 -- bash -c 'rm -f /root/.openclaw/miloco/supervisor.sock; /usr/local/bin/supervisord -c /root/.openclaw/miloco/supervisord.conf'
```
⚠️ The `nohup` approach works but the backend runs unmanaged — if it crashes, nothing restarts it. Use supervisord for persistent operation. Wait 5-10s after either approach for port 1810 to bind.

### Scenario B: Port 1810 not listening (process alive but server socket unbound)

**⚠️ Lightest fix — zombie cleanup + wait (no restart)**: Before attempting `service restart`, check if the port blockage is caused by a stuck `miloco-cli` zombie. If `ps aux | grep miloco` shows a stuck CLI process alongside a fresh miloco.main (low CPU time), **kill only the zombie** and wait 15s. The fresh miloco.main may bind port 1810 on its own without a full restart. This is faster than soft restart and avoids disrupting the running service. Reference: `references/2026-07-12-cron-container-internal-zombie-cleanup.md`.
```bash
# Preferred: single atomic restart command
miloco-cli service restart
# Alternative: separate stop + start
miloco-cli service stop
sleep 2
miloco-cli service start
```
`miloco-cli service restart` is a single atomic command that stops and starts the service. It's cleaner than stop+start for Scenario B recovery and handles the transition internally. Use this as the first-line fix when port 1810 is unbound but processes are alive.

⚠️ **PITFALL — Zombie CLI blocks soft restart (B/B+ hybrid, 2026-07-09)**: Before attempting `miloco-cli service restart`, ALWAYS check `ps aux | grep miloco` first. If you see a stuck `miloco-cli service start` zombie alongside supervisord and miloco.main, `miloco-cli service restart` may hang — the zombie interferes with the restart path. This is a B/B+ hybrid: port is unbound (B characteristic) but zombie CLI is present (B+ diagnostic pattern). **Skip `miloco-cli service restart`** and go directly to **nuclear restart with PID-targeted kills** (same as B+ fix). The presence of a zombie CLI process indicates a previous failed start attempt that blocks the atomic restart. Without this check, you waste 30s on a hanging `service restart` before discovering the zombie anyway. Reference: 2026-07-09 cron — port unbound + zombie `miloco-cli service start` (PIDs 12892/12898), nuclear restart via `lxc-attach` succeeded cleanly.

⚠️ **PITFALL — "already running (pid=XXXX)" after cleanup means supervisord already recovered**: When `miloco-cli service start` returns `{"code": 1, "message": "already running (pid=XXXX)"}` after killing stuck processes, supervisord has already spawned a new miloco.main. The PID in the message is the NEW process. **Do NOT kill this PID or restart again** — check `ss -tlnp | grep 1810` immediately; the port is likely binding or already bound. This is a positive diagnostic signal, not an error. Reference: `references/2026-07-12-cron-cli-zombie-supervisord-auto-recovery.md`.

⚠️ **PITFALL — Zombie CLI low CPU time confirms stuck state**: When checking zombie CLI processes in `ps aux`, pay attention to the **CPU time column**. A zombie `miloco-cli service start` that has been running for hours but accumulated < 1 minute of CPU time is clearly stuck (waiting on a dead process or lock), not actively working. This is a quick diagnostic to confirm the B/B+ diagnosis without waiting for command timeouts. For example: `bash -c miloco-cli service start` running since 11:18 with 0:13 CPU time at 19:19 = 8 hours stuck, clearly not progressing.

⚠️ **PITFALL — D-state miloco.main (2026-07-09)**: When checking `ps aux | grep miloco`, pay attention to the **STAT column** of miloco.main. If it shows **D** (Uninterruptible Sleep), the process is stuck on I/O — it won't respond to normal signals but `kill -9` still works (the I/O is typically stale/broken, not actively blocking signals). Combined with a zombie `miloco-cli service start`, this is another B/B+ hybrid variant: port unbound + zombie present + miloco.main stuck in D state. Recovery is the same PID-targeted nuclear restart. Don't waste time trying `service restart` — go straight to `kill -9 <PIDs>` via `lxc-attach`, clear socket, restart supervisord. Reference: `references/2026-07-09-cron-d-state-miloco-main-zombie-cli.md`.

⚠️ **PITFALL — `supervisorctl restart failed: ""` means supervisord control interface broken (2026-07-09)**: When `miloco-cli service restart` returns `{"error": "supervisorctl restart failed: ""}` (empty error string), supervisord's control interface is broken even though the supervisord process itself is alive. **Do NOT retry `service restart`** — it will keep failing. Go directly to PID-targeted nuclear restart: find supervisord + miloco.main PIDs via `pgrep -la python3`, kill both, clear socket, restart supervisord. Also check for hidden `miloco-cli service start` zombies after killing — they may be revealed. Reference: `references/2026-07-09-cron-service-restart-fail-lxc-attach-recovery.md`.

⚠️ **PITFALL — `miloco-cli service restart` fails with FileNotFoundError (2026-07-13)**: `miloco-cli service restart` internally calls `supervisorctl` without a full path, causing `FileNotFoundError: No such file or directory: 'supervisorctl'`. The default `pct exec` PATH does not include `/usr/local/bin` where supervisorctl lives. **Always bypass `miloco-cli service restart` and call supervisorctl directly with full path**: `/usr/local/bin/supervisorctl -c /root/.openclaw/miloco/supervisord.conf restart miloco-backend`. Additionally, the supervisord process name is **`miloco-backend`**, not `miloco` — running `supervisorctl ... restart miloco` returns "no such process". Reference: 2026-07-13 cron — miloco-cli service restart failure.

⚠️ **PITFALL — Port 1810 not listening but `ps aux` shows miloco processes (2026-07-13)**: `ps aux | grep miloco` can show supervisord + miloco-cli + miloco.main processes all running, yet port 1810 is not bound (backend HTTP server dead while parent process alive). Always verify with `ss -tlnp | grep 1810`. If not listening, restart `miloco-backend` via supervisorctl full path. This is distinct from Scenario B+ where port IS listening but health fails — here the port simply isn't bound.

### Scenario B+: Port 1810 listening but health unreachable (zombie-bound socket, 2026-07-08 incident)
Port shows as LISTENING in `ss -tlnp` (bound to a python3 PID), but `curl http://127.0.0.1:1810/health` returns exit code 7 (Failed to connect) and `miloco-cli perceive devices` returns `"cannot connect to Miloco backend"`. The old miloco.main process holds the socket but is in a dead/unresponsive state — it's bound but not accepting connections.

**Key diagnostic**: `ps aux | grep miloco` typically shows a stuck `miloco-cli service start` process alongside supervisord and miloco.main. The stuck `service start` is a zombie from a previous failed attempt.

**Distinguishing from other scenarios**:
- vs Scenario B: port IS listening (B has no listener)
- vs Scenario D: health fails (D has health OK)
- vs Scenario E+: port doesn't drop — stays bound but unresponsive (E+ port eventually drops)

**Fix**: Nuclear restart with PID-targeted kills (skip soft restart — the socket is held by a dead process, `service stop` won't work):
```bash
# 1. Get PIDs
ps aux | grep miloco | grep -v grep
# 2. Kill all by PID (killall unreliable in pct exec — use PID-targeted)
kill -9 <supervisord_PID> <stuck_cli_PID> <miloco_main_PID>
# 3. Verify killed — ⚠️ RE-CHECK after kill! Hidden zombies may appear
ps aux | grep miloco | grep -v grep
# 4. Kill any newly revealed processes
kill -9 <newly_found_PIDs>
# 5. Verify all gone
ps aux | grep miloco | grep -v grep
# 6. Clear socket + restart
rm -f /root/.openclaw/miloco/supervisor.sock
/usr/local/bin/supervisord -c /root/.openclaw/miloco/supervisord.conf
```

⚠️ **PITFALL — Hidden zombie processes**: After killing supervisord + miloco.main, additional stuck `miloco-cli service start` zombie processes may become visible that weren't in the initial `pgrep` output. The initial process list may only show the main python3 process, but killing it reveals hidden CLI zombies (typically in S state, running for minutes). **Always re-check** `ps aux | grep miloco` after each kill round and kill any newly revealed processes before restarting supervisord. If you skip this step, the zombie processes may interfere with the fresh supervisord start.

⚠️ **PITFALL — Supervisord restart hangs after killall via lxc-attach** (2026-07-09): When doing nuclear restart via lxc-attach (because pct exec hangs), `killall -9 python3` may succeed but the subsequent supervisord restart command hangs. This is a gap in the existing recovery path — the skill says "kill processes → clear socket → restart supervisord" but the restart step itself can hang in lxc-attach partial hang scenarios. **Workaround**: If killall succeeds but supervisord restart hangs, immediately escalate to container stop/start (don't wait for timeout). This completes the same recovery attempt — don't count it as a separate restart. Reference: `references/2026-07-09-cron-lxc-attach-killall-supervisord-hang.md`.

Wait 10s, then verify health. Recovery is typically clean — fresh processes bind port correctly.

⚠️ **PITFALL — B+ recovery can mask pipeline failure**: After a clean B+ nuclear restart, health may pass (`{"status":"ok"}`) but the perception pipeline may still be broken. Verify with `perceive logs --since 30m` — if it hangs, the pipeline failed despite the server being alive. See `references/2026-07-08-cron-post-restart-pipeline-failure.md` for this variant.

⚠️ **PITFALL — B+ → A cascade when supervisord survives**: If you kill only the stuck miloco.main + zombie CLI processes but leave supervisord alive, supervisord auto-restarts miloco.main. The new process may briefly bind port 1810 (health passes) but the pipeline fails within ~60s, causing progressive degradation → pct exec hangs → container-level hang (Scenario A). **Always kill supervisord too** during B+ recovery to avoid this cascade. If cascade is already happening (pct exec timing out after partial recovery), go directly to container stop/start — do NOT retry CLI commands. See `references/2026-07-08-cron-b-plus-to-a-cascade.md`.

### Scenario C: Health OK, `perceive logs` returns data, but `perceive query` hangs
The backend is alive (health OK), logs can be read (return cached entries), `perceive devices` may or may not work, but `miloco-cli perceive query` hangs indefinitely. The perception pipeline is nominally running but inference tasks don't complete.

**Fix**: Same escalation as Scenario D — try service restart first, escalate to nuclear restart if CLI commands hang.

### Scenario D: Port listening, health OK, but `perceive logs` hangs (2026-07-06 incident)
Multiple `miloco-cli perceive logs` processes pile up in **R** (Running) or **D** (Uninterruptible Sleep) state, each consuming CPU/memory. The backend is technically alive but the perception pipeline is stuck. **Key diagnostic**: `ps aux | grep miloco` will show many `miloco-cli perceive logs --limit N` entries with 10-30+ minutes of CPU time.

**⚠️ Multi-type pileup variant (2026-07-08)**: Both `miloco-cli perceive logs` AND `miloco-cli perception status` processes can pile up simultaneously, causing extreme container load (9-12). After `pkill -9 miloco-cli`, logs become temporarily available but the container may degrade again within seconds. If container load stays >5 after cleanup, consider container stop/start as the primary recovery path rather than trying to recover via CLI commands. Reference: `references/2026-07-08-cron-multi-stuck-cli-cleanup.md`.

**⚠️ Common initial state**: When you first check, you may see `miloco-cli service start` already running in R state alongside supervisord + miloco.main. The service is partially alive but health check may fail. **Wait 10-15s and re-check health** — the service start may still be completing. If health recovers but logs are still stale, this is Scenario E, not D.

**Fix (escalating)**:

1. **Try soft restart first** (may work if process pileup is mild):
   ```bash
   miloco-cli service stop && sleep 2 && miloco-cli service start
   ```

2. **If `service start` itself hangs** (2026-07-16 pattern — many stuck processes block the CLI): `miloco-cli service stop` succeeds but `service start` times out because the stale `miloco-cli` subprocesses interfere. **Escalate to nuclear restart**:
   ```bash
   killall -9 supervisord 2>/dev/null   # MUST kill supervisord first — it owns the listening port
   killall -9 python3 2>/dev/null        # kills miloco.main and any stuck cli processes
   sleep 3                               # wait for port release
   rm -f /root/.openclaw/miloco/supervisor.sock
   /usr/local/bin/supervisord -c /root/.openclaw/miloco/supervisord.conf
   ```
   ⚠️ **PITFALL**: `killall -9 python3` does NOT kill supervisord (it's a separate process). If you skip `killall -9 supervisord`, the next `supervisord` start will fail with "Another program is already listening on a port". Always kill supervisord first, wait 3s for the port release, then clear the socket and restart.
   ⚠️ `supervisord` may not be on PATH inside `pct exec` — use full path `/usr/local/bin/supervisord`. After start, wait 8-10s for the backend to bind port 1810.
Verify with `ps aux | grep miloco` afterward — should show only supervisord + fresh miloco.main process (2 processes total).

⚠️ **PITFALL — Orphaned miloco.main appears after supervisord kill** (2026-07-09): When doing PID-targeted nuclear restart, killing supervisord may not prevent an already-forked miloco.main child from materializing. After `kill -9 <supervisord_PID>`, always re-run `pgrep -la python3` — a new non-defunct miloco.main may appear (it was spawned before the kill signal landed). Kill it too before clearing socket and restarting. Without this step, the orphaned process may interfere with the fresh supervisord start. Reference: `references/2026-07-09-cron-zombie-supervisord-orphan-recovery.md`.

⚠️ **PITFALL — `killall -9` unreliable in `pct exec` for ALL process types** (2026-07-06, confirmed 2026-07-07): After running `killall -9` inside `pct exec`, target processes may NOT be killed. This affects supervisord, python3 (miloco.main), and miloco-cli processes alike. The `pct exec` wrapper's signal delivery is unreliable — `killall` appears to succeed (exit 0) but processes survive. **Symptoms**: after nuclear restart, `ps aux | grep miloco` shows old processes with earlier start times coexisting with new ones. Port 1810 binds to the OLD process, new processes can't bind. **Escalation path when killall fails**:
```bash
# 1. Get PIDs of all miloco processes
ps aux | grep miloco | grep -v grep
# 2. Kill by specific PID (more reliable than killall in pct exec)
kill -9 <PID1> <PID2> <PID3> ...
# 3. Verify killed
ps aux | grep miloco | grep -v grep
# 4. Then restart supervisord
```
If even PID-targeted kills fail (pct exec itself hangs), escalate to container stop/start (Scenario A). **Always verify** post-restart: `ps aux | grep miloco | grep -v grep` — should show exactly 2 processes (1 supervisord + 1 miloco.main).

   ⚠️ **PITFALL**: The `pct exec` wrapper can time out (20s default) even though `killall` succeeded inside the container. The killall runs but the SSH/pct wrapper hangs waiting for the shell to exit. If nuclear restart via `pct exec` times out, **escalate to container stop/start** (Scenario A) — the killall likely worked, but you can't confirm. Container restart is a more reliable "nuclear" option when `pct exec` is unreliable.

⚠️ **PITFALL**: When CT <ID>'s miloco service is hung, even `pct exec 310 -- bash -c '...'` commands can hang indefinitely. Always check `pct status 310` first (fast) before attempting heavier commands. If `pct status 310` returns `running` but pct exec hangs, the container is alive but something inside is blocking.

⚠️ **PITFALL — Progressive degradation after restart**: After a successful container restart + health OK, running `perceive logs` or `perceive devices` when the pipeline is broken will cause the container to progressively degrade — commands that worked initially (curl health, ps aux) start timing out too. If health passes but both `perceive logs` AND `perceive devices` hang, **stop immediately**. Do NOT retry with different timeouts — it just makes the container worse. The 2-restart budget exists to prevent this. Reference: `references/2026-07-06-morning-cron-restart-budget.md`. **2026-07-08 variant** (`references/2026-07-08-cron-post-restart-pipeline-failure.md`): health passes and stays OK, but all CLI commands timeout — even `ps aux` becomes unreachable within 60s. Distinguished from E+ by port not dropping: health stays OK but inference never starts.

⚠️ **PITFALL — `device control` fails while `perceive logs` succeeds (2026-07-10)**: The `miloco-cli device control` command can fail with `cannot connect to Miloco backend at http://127.0.0.1:1810` even when `miloco-cli perceive logs` returns data successfully moments earlier. This indicates the backend's perception endpoint is alive but the device control endpoint is not (or requires a different internal path that hasn't initialized). **Do not assume the backend is fully operational just because perception works.** When device control fails with this error but perceive logs works, the perception pipeline is functional for monitoring but device automation is offline — report this state to the user rather than attempting restarts. Reference: `references/2026-07-10-cron-device-control-partial-backend.md`.

⚠️ **PITFALL — `ss -tlnp | grep 1810` false negative via pct exec (2026-07-10)**: Running `ss -tlnp | grep 1810` inside `pct exec` can return **empty output even when port 1810 IS listening**. The pipe through pct exec may corrupt or reformat the output such that grep fails to match. **Symptom**: `ss -tlnp | grep 1810` returns exit code 1 (no match), but the subsequent `ss -tlnp` (without grep) shows port 1810 bound to a python3 PID, and `curl http://127.0.0.1:1810/health` returns `{"status":"ok"}`. **This can cause a false Scenario B diagnosis** (port unbound) when the port is actually healthy. **Fix**: When `grep 1810` returns empty, do NOT immediately assume Scenario B. Run `ss -tlnp` without grep first, OR use `curl -s --connect-timeout 5 http://127.0.0.1:1810/health` as the port-health check instead — curl is more reliable through pct exec than piped grep. Reference: `references/2026-07-10-cron-ss-grep-false-negative.md`.

⚠️ **PITFALL — Pre-run retry pileup compounds Scenario D**: When the pre-run script times out, it may have already spawned several stuck miloco-cli processes. The agent's own diagnostic attempts (pct exec → lxc-attach → miloco-cli perceive logs × N) then pile up MORE stuck processes on top. **Result**: nuclear restart (kill + supervisord restart) clears supervisord and miloco.main but the NEW stuck miloco-cli processes survive (they're children of lxc-attach/pct exec wrappers, not supervised by supervisord). Health may pass but CLI commands still hang. **Fix**: If nuclear restart doesn't restore CLI functionality, escalate immediately to container stop/start — this kills ALL processes including the piled-up CLI wrappers. Do not waste time retrying CLI commands after nuclear restart when the pileup is from pre-run retries. Reference: `references/2026-07-10-cron-cli-pileup-container-restart.md`.

⚠️ **PITFALL — Legitimate high CPU from miloco.main causes ALL probe methods to timeout**: When miloco.main is at >120% CPU doing legitimate inference (not stuck), even trivial commands via `pct exec` and `lxc-attach` can timeout — including `echo HELLO`, `echo CONTAINER_OK`, and `curl health`. The container is alive but slow under CPU contention from the inference process. **Key diagnostic**: check host `ps aux --sort=-%cpu` — if miloco.main shows high CPU time (accumulated minutes, not seconds) and the STAT column is `Sl` (not `Dl` or `Ds`), the process is healthy and actively inferring. **Do NOT escalate to container stop/start** — the service is working, just busy. Wait for inference to complete, or accept that perception data may be temporarily unavailable. If `ss -tlnp | grep 1810` succeeds (kernel call, fast) but `curl health` fails, the port is bound but the backend is too busy to respond — this is NOT Scenario B+. Reference: `references/2026-07-12-cron-high-cpu-probe-timeout.md`.

⚠️ **PITFALL — `miloco-cli perceive logs` can succeed when `curl health` fails under high CPU**: When miloco.main is at >140% CPU, `curl --connect-timeout 10 http://127.0.0.1:1810/health` may return exit code 7 (connection refused) because the backend is too busy to accept new TCP connections promptly. However, `miloco-cli perceive logs` may still succeed — it uses a different HTTP client with longer internal timeouts or connection retry logic. **Use `miloco-cli perceive logs --since 30m --limit 3` as the primary health indicator under high CPU**, not `curl health`. Also: `ss -tlnp` via pct exec can timeout even when the port IS bound. Service logs (`miloco-cli service logs`) can confirm startup when all live probes fail. **Decision rule**: if miloco.main is at >120% CPU in Sl/Rl state and `miloco-cli perceive logs` returns data → service is healthy regardless of curl/ss results. Stop probing and report status. Reference: `references/2026-07-12-cron-cli-success-curl-fail-high-cpu.md`.

⚠️ **PITFALL — Agent self-inflicted diagnostic pileup (2026-07-12)**: After a successful nuclear restart, the agent's own diagnostic probes (`miloco-cli perceive logs`, `curl health`, `ps aux` via `pct exec`) can pile up as stuck processes — distinct from pre-run pileup because these are spawned by the agent, not the pre-run script. **Key sign**: after confirming health OK + fresh inferences (total_inferences > 0), subsequent `pct exec` queries time out and host `ps aux` shows new stuck miloco-cli/curl processes in R/D state. **Escalation pattern**: agent tries pct exec (times out) → escalates to lxc-attach (times out) → each escalation creates NEW stuck processes on top of existing ones. **Fix**: Kill stuck processes from PVE host shell (`kill -9 <host_PIDs>`) — container processes visible in host ps are killable from the host. **Prevention**: After confirming service health via ANY of these signals, **STOP PROBING**: (1) Health OK + at least 1 fresh inference (`total_inferences > 0`), OR (2) Health OK + host `ps aux` shows miloco.main at high CPU (>100%) in **Sl** state — the high CPU IS the inference happening, even if `total_inferences` is still 0 during warm-up. Do not attempt additional `perceive logs` or `curl` queries to verify stability — each query risks pileup when miloco.main is at high CPU. **The correct action after confirming service health is to report status and stop.** Reference: `references/2026-07-12-cron-stuck-init-agent-pileup.md`, `references/2026-07-12-cron-high-cpu-probe-timeout.md`, `references/2026-07-12-cron-host-zombie-cleanup-high-cpu.md`. `perceive logs` or `curl` queries to "verify stability" — each query risks pileup when miloco.main is at high CPU. **The correct action after confirming service health is to report status and stop.** Reference: `references/2026-07-12-cron-stuck-init-agent-pileup.md`, `references/2026-07-12-cron-high-cpu-probe-timeout.md`.

⚠️ **PITFALL — Progressive degradation under extreme load (13+)**: When container load exceeds ~13, commands that initially work (`uptime`, `ss`, `curl`, `miloco-cli perceive logs`) start timing out after repeated queries. This is NOT a container hang — it's the container becoming progressively slower under extreme load. Eventually even `echo HELLO` via `pct exec` times out. **Key distinction from Scenario A**: in Scenario A, pct exec hangs from the start; here, commands work initially but degrade. **Action**: If you already have the essential perception data, **STOP PROBING immediately**. Each additional query adds to the load and worsens degradation. Do not attempt to verify service status or gather more diagnostics — you already know the service is alive. Reference: `references/2026-07-10-cron-high-load-progressive-degradation.md`.

⚠️ **PITFALL — Warm-then-die post-restart** (2026-07-09): After container stop/start + supervisord, the first `perceive logs` query may succeed with **fresh, real data** (total_inferences > 0, same-day timestamps, actual scene descriptions) — but subsequent queries collapse within ~60s. This differs from the "dead from the start" variant (2026-07-08) where ALL commands timeout immediately. **Key sign**: first query returns genuine inference output (not stale cache), but `perceive devices` or the next `perceive logs` call times out, followed by health check timeout. **Do not assume recovery is complete** just because the first query returns fresh data. Verify pipeline stability with a second query 30-60s later before reporting success. If the pipeline collapses after brief success, this counts as a failed restart attempt — try nuclear restart as second attempt per restart budget. Reference: `references/2026-07-09-cron-warm-then-die-post-restart.md`.

⚠️ **PITFALL — `supervisord` is not on the default PATH** inside `pct exec`. Use `/usr/local/bin/supervisord` or rely on the full Python path `/usr/bin/python3 /usr/local/bin/supervisord -c /root/.openclaw/miloco/supervisord.conf`.

⚠️ **PITFALL — "Another program is already listening" is a positive diagnostic**: When you try to start supervisord and get `Error: Another program is already listening on a port that one of our HTTP servers is configured to use`, this means supervisord is **already running** — don't treat it as a failure. Follow up with `supervisorctl -c /root/.openclaw/miloco/supervisord.conf status` to check the backend's state. If it shows `RUNNING` with low `uptime_seconds` (< 30s), the backend is still initializing — wait 15-20s and retry `perceive logs`. This often happens after a clean container stop/start where supervisord auto-started. Reference: `references/2026-07-10-cron-supervisord-auto-start-init.md`.

Wait 3-5 seconds after start before querying — the backend binds port 1810 asynchronously and needs time to initialize.

### Scenario E: Perception logs are days/weeks stale
Service healthy (health OK, `perceive logs` returns fast, `perceive devices` shows cameras online) but the newest log entry is days old = the inference pipeline produces nothing. This is an **upstream** problem, not a service problem.

**Diagnosis**: `miloco-cli perceive logs --limit 1` → check the `t` field **and** `total_inferences`; `total_inferences: 0` after startup means the logs are cached, not fresh. `perceive query` and `service logs` hanging are corroborating signals, not a separate fault.

**HEVC frame-drop judge** (repeated `drop non-key frame, MIoTCameraCodec.VIDEO_HEVC` in `miloco-cli service logs`):
- A handful at startup, cleared within ~15-30s once a keyframe arrives → **transient, self-healing, no action**.
- Dozens+/second sustained while `total_inferences` stays 0 → the camera's HEVC stream cannot be decoded; **restarts never fix this** (it persists across runs). Fix upstream instead: camera keyframe interval/profile, firmware changes, or network keyframe delivery.

**Restart budget**: one Scenario B attempt, then one Scenario D nuclear restart; if logs are still stale ~5 min after that, **stop and report as upstream** (camera feed access / model API / task config). Do NOT keep restarting a healthy service — repeated restarts degrade the container, and running perception queries against a broken pipeline makes it worse.

### Scenario E+: Fake-Healthy Collapse (2026-07-06 incident)
A variant of Scenario E where the backend briefly appears healthy after startup, then collapses:

1. Port 1810 binds → health responds → `perceive logs` returns stale cached data (`total_inferences: 0`)
2. Within 30-60s: port drops, CLI connection fails, `curl health` times out
3. Container degrades — even basic commands time out

**Diagnostic signature**: `perceive logs` returns stale data with `total_inferences: 0` → next call fails → port drops.

**⚠️ Partial-recovery variant (2026-07-06 afternoon cron)**: After nuclear restart, `total_inferences` may briefly increment (e.g., 0→2) before the pipeline stalls and degrades. This means the pipeline *tried* to start but couldn't sustain. The brief increment is a strong E+ signal — don't interpret it as "warm-up in progress." If health check starts timing out within 30s of seeing a small `total_inferences` bump, the pipeline is collapsing. Reference: `references/2026-07-06-afternoon-cron-a-e-cascade.md`.

**Key distinction from Scenario E**: In Scenario E, the service is stable but stale. In E+, the service collapses — it's not just stale, it can't sustain itself. The backend process is alive (PID running) but the server socket dies.

**Response**: Same restart budget (2 attempts max). If the pattern repeats after nuclear restart, declare upstream failure immediately. Do NOT wait for "warm-up" — the stale data is cached, not live.

Reference: `references/2026-07-06-cron-fake-healthy-collapse.md`

### Scenario F: Service restart doesn't stick after container restart
After a container stop/start (Scenario A), `miloco-cli service start` reports success but the service dies shortly after. **Key diagnostic**: `ps aux | grep miloco` shows only supervisord, no `miloco.main`.

**Fix**: Clear the stale socket, then start supervisord directly (NOT via `miloco-cli service start`, which may hang):
```bash
rm -f /root/.openclaw/miloco/supervisor.sock
/usr/local/bin/supervisord -c /root/.openclaw/miloco/supervisord.conf
```
Wait 8-10s, then verify with `curl -s http://127.0.0.1:1810/health`.

## Post-Recovery Log Interpretation

After a successful recovery (any scenario), perception logs will resume but require careful interpretation before taking action.

### Snapshot vs transition events

**Snapshot** (total_inferences ≤ 5 after restart): The first few inferences are point-in-time views. If all cameras show no people, this is a **state observation** ("当前无人在家"), NOT a transition event ("离家"). Do NOT trigger automatic actions (e.g., lights off) based on snapshots alone.

**Transition** (total_inferences > 5 with state change): Requires seeing people **appear** (回家) or **disappear** (离家) across consecutive inferences. Only trigger device control actions when a clear transition is observed across multiple inference entries.

**Baseline gap**: After restart, there's no prior state to compare against. The first inference is just a snapshot. Wait for 5-10 more inferences before interpreting transitions.

### Decision framework for cron jobs

| total_inferences | Interpretation | Action |
|---|---|---|
| 0-2 | Post-restart snapshot only | Report current state, no device control |
| 3-10 | Warming up | State observations becoming reliable, still no transitions |
| >10 | Pipeline established | Can interpret transitions (people appearing/disappearing) |

### Startup timing note

After supervisord restart, port 1810 may take **up to 30 seconds** to bind (not just 8-10s as listed in individual scenarios). Check health at 10s, 20s, and 30s intervals before escalating. Reference: `references/2026-07-08-cron-b-plus-recovery-snapshot.md` and `references/2026-07-08-cron-clean-scenario-a-recovery.md`.

### First-query success ≠ pipeline stability

⚠️ **PITFALL — First-query success ≠ pipeline stability**: Even if the first `perceive logs` query after restart returns **fresh, real data** (total_inferences > 0, same-day timestamps, actual scene descriptions), do NOT assume the pipeline is stable. The warm-then-die pattern (2026-07-09) shows the pipeline can produce genuine inferences for one query, then collapse on the next. **Verify with a second query 30-60s later** before reporting recovery as successful. If the second query fails, treat the restart as failed and proceed per restart budget. Reference: `references/2026-07-09-cron-warm-then-die-post-restart.md`.

⚠️ **PITFALL — Collapse can be faster than 30-60s**: The 2026-07-11 incident showed warm-then-die collapse in **~15 seconds** (first query succeeds, second query 15s later times out). Previous references documented 30-60s collapse windows. When verifying pipeline stability, space queries at least 30s apart — a 15s gap may not be enough to detect imminent collapse. Reference: `references/2026-07-11-cron-rapid-warm-then-die.md`.

⚠️ **PITFALL — Persistent high miloco.main CPU (>129%) across restarts = upstream failure**: When miloco.main consistently runs at >129% CPU across multiple container restart attempts (e.g., 134% before restart 1, 129% after restart 1, 129% after restart 2), AND the pipeline collapses after brief success each time, this is a strong indicator of upstream pipeline failure. Do NOT keep restarting — the inference process is likely stuck in a computation loop. Contrast with healthy high CPU: in the 2026-07-10 incident, miloco.main at 123% CPU was doing legitimate inference (pipeline sustained for 14+ minutes). The diagnostic difference: sustained pipeline = healthy; brief success then collapse = upstream failure. Reference: `references/2026-07-11-cron-rapid-warm-then-die.md`.

## CT <ID> IP Discovery
CT <ID> uses DHCP on vmbr0. Its IP can change. To find it:
```bash
# From PVE host — get the container's IP (pct exec may hang, so use pct config to get MAC, then check DHCP leases)
pct config 310 | grep net  # get hwaddr
cat /var/lib/misc/dnsmasq.leases | grep <hwaddr>  # get IP
# Or brute-force: ping sweep 192.0.2.10-150, check which responds + has SSH
```
As of 2026-07-06, CT <ID>'s IP is `192.0.2.10`. **Note**: Direct SSH to CT <ID> may not work (SSH daemon may be down or port unreachable) even when `pct exec` works — always prefer `pct exec` for commands inside the container.

## Incident References
- `references/2026-07-06-cron-stuck-service-start-recovery.md` — stuck `miloco-cli service start` + `supervisorctl status`, port 1810 unbound, single nuclear restart fixed it
- `references/2026-07-06-0800-cron-pipeline-hang.md` — upstream pipeline failure (3 restarts didn't fix, stopped per budget)
- `references/2026-07-06-evening-cron-hevc-upstream-failure.md` — HEVC decoder failure (service logs show `drop non-key frame, MIoTCameraCodec.VIDEO_HEVC`), stale logs despite clean restart
- `references/2026-07-06-cron-fake-healthy-collapse.md` — "fake-healthy collapse": backend briefly binds port, returns stale cached data (`total_inferences: 0`), then port drops and container degrades to timeout. Distinct from stable-stale Scenario E.
- `references/2026-07-06-afternoon-cron-a-e-cascade.md` — Scenario A→E+ cascade: container hang recovery exposes latent pipeline failure; `total_inferences` briefly increments (0→2) before collapse; container recovery after budget exhaustion.
- `references/2026-07-07-cron-killall-failure-e-plus.md` — killall -9 fails for ALL process types (not just supervisord); PID-targeted kill as escalation; E+ pipeline collapse repeated; restart budget exhausted.
- `references/2026-07-07-cron-pre-run-timeout-recovery.md` — pre-run script timeout; pct exec partially working; `perceive logs --limit` stale data vs `--since` fresh data; container stop/start + supervisord restart recovery.
- `references/2026-07-07-cron-transient-hevc-recovery.md` — HEVC frame drops on startup that self-resolved within ~8s; pre-run script failure didn't mean service was broken; stale cached data still contained useful observations.
- `references/2026-07-08-cron-zombie-bound-port.md` — Scenario B+: port 1810 listening but health unreachable (zombie-bound socket from dead miloco.main); stuck `miloco-cli service start` zombie; PID-targeted nuclear restart fixed it cleanly.
- `references/2026-07-08-cron-backend-restart-recovery.md` — backend restart during pre-run; `uptime_seconds: 18` signal; `--jsonl` + `--since` combination works; brief wait-and-retry recovery.
- `references/2026-07-08-cron-post-restart-pipeline-failure.md` — B+ recovery succeeded (health OK) but perception pipeline broken: all CLI commands timeout, progressive degradation within 60s. Distinguishes from E+ (port drops) — here health stays OK but inference never starts.
- `references/2026-07-08-cron-backend-dead-lxc-attach.md` — Backend completely dead (no processes), pct exec hung, lxc-attach fallback, standalone nohup restart, lock file issue, stale 14-day-old data.
- `references/2026-07-08-cron-d-state-recovery.md` — D-state process + service start zombie: container probe technique (echo/ps/ss), PID-targeted kill, no container restart needed.
- `references/2026-07-08-cron-b-plus-to-a-cascade.md` — B+ → A cascade: partial PID kill (supervisord alive) → auto-restart → brief health → progressive degradation → container stop/start recovery. Always kill supervisord during B+ recovery.
- `references/2026-07-08-cron-lxc-attach-probe-hidden-zombies.md` — pct exec completely hangs → lxc-attach probe fallback → hidden zombie CLI processes revealed after killing main process → thorough kill → clean recovery.
- `references/2026-07-08-cron-both-hang-container-stop.md` — both pct exec AND lxc-attach hang → true container-level hang → container stop/start recovery (no PID-targeted kills possible when you can't get in).
- `references/2026-07-08-cron-partial-pct-exec-recovery.md` — partial pct exec hang (echo works, uptime hangs), supervisord HTTP down but socket works, `miloco-cli service restart` atomic recovery.
- `references/2026-07-08-cron-multi-stuck-cli-cleanup.md` — multiple miloco-cli process types (perceive logs + perception status) stuck in R state, extreme load 9-12, container degrades after cleanup.
- `references/2026-07-08-cron-b-plus-recovery-snapshot.md` — B+ recovery followed by snapshot interpretation: total_inferences: 1 confirms point-in-time view, not transition event; 20-second startup delay vs documented 8-10s.
- `references/2026-07-08-cron-clean-scenario-a-recovery.md` — clean Scenario A (both pct exec + lxc-attach hang → container stop/start → supervisord → health at 30s). Timing calibration: actual port binding took ~30s, exceeding documented 20s upper bound.
- `references/2026-07-08-cron-lxc-attach-partial-hang.md` — lxc-attach partial hang: echo works but pgrep/ss/ps aux hang → can't find PIDs → PID-targeted kills impossible → container stop/start. Demonstrates that lxc-attach exhibits the same partial hang pattern as pct exec.
- `references/2026-07-08-cron-mis-escalation-to-container-stop.md` — lxc-attach ps aux works but agent still escalated to container stop/start instead of PID-targeted nuclear restart. Documents the mis-escalation pattern and correct action.
- `references/2026-07-09-cron-clean-backend-restart-recovery.md` — clean backend restart recovery: pre-run timeout → `service status` showed low uptime_seconds (backend initializing) → 15s wait → retry succeeded. Demonstrates `service status` as supervisord IPC diagnostic during backend initialization.
- `references/2026-07-09-cron-pgrep-over-ps-aux.md` — pgrep works when ps aux hangs in partial lxc-attach hang; enabled PID-targeted nuclear restart without container stop/start.
- `references/2026-07-09-cron-true-container-hang-pgrep-confirms.md` — pgrep via lxc-attach also hangs in true container-level hang; confirms diagnosis and rules out PID-targeted kills; clean container stop/start recovery with 30s health check timing.
- `references/2026-07-09-cron-zombie-supervisord-orphan-recovery.md` — defunct miloco.main zombie + stuck CLI; PID-targeted kill of supervisord spawned orphaned miloco.main; required re-kill before socket clear + supervisord restart.
- `references/2026-07-09-cron-lxc-attach-killall-supervisord-hang.md` — killall -9 python3 via lxc-attach succeeded but supervisord restart hung; progressive degradation timeline (health OK → one inference → container degraded in ~60s); demonstrates killall + supervisord restart gap in lxc-attach partial hang scenarios.
- `references/2026-07-09-cron-warm-then-die-post-restart.md` — container stop/start recovery → health OK at 30s → first perceive logs returns FRESH data (5 entries, total_inferences > 0, real scene descriptions) → subsequent queries timeout → health check timeout → collapse. Distinct from "dead from start" (2026-07-08) and stale-cache E+ (2026-07-06). First successful query does NOT confirm pipeline stability.
- `references/2026-07-09-cron-repeated-warm-then-die.md` — warm-then-die repeated across 2 container stop/start cycles before stabilizing. Key finding: service status returning `running: true` with low `uptime_seconds` can be a false positive during initialization. Revised restart budget: if container stop/start fixes degradation but pipeline collapses afterward, the next container stop/start counts as a pipeline restart attempt.
- `references/2026-07-09-cron-service-start-slow-after-clean-restart.md` — clean container restart → `miloco-cli service start` timed out at 20s but service started in background (uptime 43s). Shows `service start` CAN work after clean restart if given 40+ seconds; `service logs` shows initialization progress during the hang.
- `references/2026-07-09-cron-service-restart-fail-lxc-attach-recovery.md` — `supervisorctl restart failed` (empty error) when supervisord control interface broken; PID-targeted nuclear restart via lxc-attach; hidden CLI zombie revealed after kill.
- `references/2026-07-09-cron-high-load-false-alarm.md` — pre-run script timeout but service healthy; high container load (11.56) made miloco-cli slow; false-alarm vs real-failure decision matrix.
- `references/2026-07-09-cron-double-warm-then-die.md` — two consecutive warm-then-die failures across two container restarts; first recovery returned genuine fresh inferences (total_inferences:1) but collapsed; second recovery returned only stale cache (total_inferences:0); service logs not gathered before reporting (gap documented).
- `references/2026-07-09-cron-d-state-miloco-main-zombie-cli.md` — D-state miloco.main (Uninterruptible Sleep) + zombie `miloco-cli service start`; port unbound; PID-targeted kill via lxc-attach succeeded; kill -9 works despite D state (stale I/O, not blocking signals).
- `references/2026-07-10-cron-lxc-attach-partial-hang-recovery.md` — lxc-attach partial hang (echo OK, pgrep/ss hang) → container stop/start → supervisord → health at 30s. Clean recovery, no warm-then-die. Perception logs: person sleeping in study, two people near vehicles in north yard.
- `references/2026-07-10-cron-high-load-progressive-degradation.md` — high load (13.43) causing progressive command timeouts; HEVC drops coexisting with partial pipeline; stop-probing lesson; `service logs --lines` vs `--limit` flag.
- `references/2026-07-10-cron-device-control-partial-backend.md` — `perceive logs` succeeds but `device control` fails with "cannot connect to Miloco backend"; partial backend state where perception works but automation doesn't.
- `references/2026-07-10-cron-supervisord-auto-start-init.md` — supervisord auto-starts after clean container stop/start; "Another program is already listening" diagnostic; backend initialization timing (15-20s after supervisord confirmed running).
- `references/2026-07-10-cron-b-plus-hybrid-recovery.md` — B/B+ hybrid (port unbound + zombie CLI + D-state miloco.main) recovered via PID-targeted nuclear restart through pct exec; `--since 1h` returned stale cached data while `--since 10m` returned fresh data; pre-run failure string "⚠️ 无法解析感知日志:"
- `references/2026-07-10-cron-cli-pileup-container-restart.md` — pre-run retry pileup compounds Scenario D: nuclear restart alone insufficient, container stop/start required as second step; miloco.main at 123% CPU was not the cause (backend doing inference), stuck miloco-cli wrappers were
- `references/2026-07-10-cron-nsenter-fails-for-lxc-kills.md` — `nsenter -t <init_pid> -p` from PVE host cannot kill processes inside LXC container; PIDs visible via host ps don't map into container namespace; container stop/start is the only option when pct exec + lxc-attach both hang
- `references/2026-07-10-cron-pve-overload-pre-run-pileup.md` — PVE host load 16.39 from miloco.main (116% CPU) + 6+ stuck miloco-cli processes (pre-run retry pileup) + Minecraft server (6.5GB RAM). Host-level `ps aux --sort=-%cpu` as key diagnostic. Wrong subcommand `perception logs` (noun) contributed to pileup.
- `references/2026-07-10-cron-zombie-miloco-supervisord-auto-recovery.md` — Zombie (defunct) miloco.main + running supervisord + stuck miloco-cli processes from pre-run pileup. Killing only stuck CLI processes allowed supervisord to auto-restart miloco.main — no nuclear restart or container stop/start needed. Key pattern: when supervisord is alive and miloco.main is a zombie, the stuck CLI wrappers are the blocking factor.
- `references/2026-07-11-cron-rapid-warm-then-die.md` — Rapid warm-then-die (15s collapse window, faster than documented 30-60s); persistent miloco.main CPU >129% across restarts as upstream failure indicator; 2 restart attempts exhausted; perception data captured before collapse (man working in front yard).
- `references/2026-07-11-cron-bash-c-hang-fullpath-fix.md` — `bash -c` wrapper in pct exec intermittently hangs; direct full-path `/usr/local/bin/miloco-cli` execution is more reliable; transient "cannot connect" error resolved on retry after port verification.
- `references/2026-07-11-cron-host-pid-namespace-mismatch.md` — Host-level PIDs from `ps aux --sort=-%cpu` don't map to container PIDs in `pct exec kill`; container-internal PIDs from `pct exec 310 -- ps aux` required; pre-run retry pileup self-resolved.
- `references/2026-07-11-cron-host-wrapper-cleanup.md` — Host-level ssh/lxc-attach wrapper process pileup; killing ALL host wrappers before container restart; warm-then-die collapse after recovery.
- `references/2026-07-11-cron-hevc-host-zombie-cleanup.md` — Persistent HEVC decoder failure (8.5h stale logs); host-level `miloco-cli service start` zombies killed directly on host shell; miloco.main D state at 107% CPU; progressive degradation under load.
- `references/2026-07-11-cron-quick-zombie-auto-recovery.md` — Fastest recovery: zombie miloco.main + running supervisord = auto-restart in ~5min; host zombie cleanup + wait only, no nuclear restart needed.
- `references/2026-07-11-cron-host-zombie-scenario-a-recovery.md` — Host zombie cleanup (15 PIDs, load 9.59→4.95) followed by Scenario A container stop/start; supervisord did NOT auto-start after degraded restart; manual start required; health at 30s.
- `references/2026-07-12-cron-pre-run-false-alarm-recovery.md` — pre-run timeout was false alarm (service healthy, just slow); manual SSH with longer timeouts recovered cleanly; 24880 log entries retrieved
- `references/2026-07-12-cron-stuck-init-agent-pileup.md` — Scenario B− (stuck initialization, Dl state, 1s CPU after 8h); nuclear restart recovered backend; agent self-inflicted diagnostic pileup after recovery; host shell kill of container processes as fast cleanup.
- `references/2026-07-13-cron-b-minus-sl-state-recovery.md` — Scenario B− with Sl state (not Dl), 35s CPU over 8h; nuclear restart via pct exec succeeded; pre-run zombie cleanup before restart; confirms B− is not limited to Dl state.
- `references/2026-07-12-cron-supervisord-alive-zombie-cleanup.md` — Supervisord alive + CLI zombie cleanup → auto-recovery; supervisord handles miloco.main restart automatically; `supervisorctl` not on PATH (`FileNotFoundError`); `service status` fails while health OK
- `references/2026-07-12-cron-auto-recovery-no-intervention.md` — pre-run timeout caused by service mid-restart; service auto-recovered without manual intervention; `service status` showed `running: true, uptime_seconds: 11`; logs from 18 days ago with `total_inferences: 0` (expected warm-up, not failure).
- `references/2026-07-12-cron-duplicate-supervisord-cleanup.md` — Duplicate supervisord processes (2× from concurrent recovery) each spawned own miloco.main; host-level kill of duplicate pair + CLI pileup dropped load from 16.67 to 12.22; perception logs retrieved after cleanup.
- `references/2026-07-12-cron-pre-run-pileup-host-kill-recovery.md` — Pre-run pileup recovery via host-level kill only (no nuclear restart); supervisord dead but miloco.main auto-restarted independently; health OK + total_inferences: 1; lightest recovery path.
- `references/2026-07-12-cron-container-internal-zombie-cleanup.md` — Container-internal zombie cleanup via pct exec kill -9 (not host-level); fresh miloco.main couldn't bind port due to stuck CLI; 15s wait after cleanup sufficient; no nuclear restart needed; documents host vs container PID namespace mismatch.
- `references/2026-07-12-cron-high-cpu-probe-timeout.md` — Legitimate high CPU (miloco.main 128-132% doing inference) caused ALL probe methods to timeout (pct exec echo, lxc-attach echo, curl health). NOT a container hang. Service collapsed briefly then auto-recovered via supervisord. First query returned fresh data; second query timeout was load-induced, not collapse. Documents probe escalation anti-pattern.
- `references/2026-07-12-cron-b-minus-recovery-high-cpu.md` — B− recovery (stuck init, nuclear restart) succeeded, but subsequent probe queries timed out due to legitimate high CPU (128%, Sl state). Agent-inflicted pileup cleaned from host shell. Key lesson: stop probing after health OK + fresh inference confirmed.
- `references/2026-07-12-cron-cli-zombie-supervisord-auto-recovery.md` — CLI zombie cleanup → supervisord auto-recovery (lightest Scenario B variant); supervisord HTTP interface down (9001 refused) but process management still works; "already running (pid=XXXX)" as positive diagnostic signal.
- `references/2026-07-12-cron-host-zombie-cleanup-high-cpu.md` — Host zombie cleanup → health OK → miloco.main at 126% CPU (Sl state) during warm-up → stopped probing; D-state miloco-cli as diagnostic signal for backend busy; total_inferences: 0 expected during warm-up.
- `references/2026-07-12-cron-cli-success-curl-fail-high-cpu.md` — miloco-cli perceive logs succeeded at 145% CPU while curl health returned exit code 7; CLI uses different HTTP client with longer timeouts; service logs confirmed startup when all live probes failed.
- `references/2026-07-12-cron-false-alarm-high-cpu-shortcut.md` — False alarm: pre-run timeout but miloco.main at 134% Sl doing inference; full 7-step path wasted ~120s on timeouts when host ps at step 2 already confirmed health; documents False Alarm Shortcut to skip steps 3-7 when miloco.main >100% CPU Sl state with minutes CPU time.
- `references/2026-07-12-cron-health-unhealthy-pipeline-ok.md` — Health endpoint returned `{"status":"unhealthy"}` but pipeline fully functional (7 fresh inferences, all cameras online); HEVC frame drops present but not blocking; documents "unhealthy" as degraded-but-operational state, not restart trigger.
- `references/2026-07-12-cron-parse-failure-false-alarm.md` — "⚠️ 无法解析感知日志:" false alarm: service healthy (miloco.main 19% CPU Sl), pre-run zombies caused parse failure; host-level zombie cleanup sufficient, no nuclear restart needed.
- `references/2026-07-13-cron-b-minus-self-resolve.md` — B− self-resolve: pre-run timeout, service in B− state (process alive, port unbound), auto-recovered during diagnostics; startup log sequence (bind → shutdown → restart → rebind) is normal self-healing; short `--since` window revealed fresh data while long window returned stale cache.

## Known Device DIDs

| Device | DID |
|--------|-----|
| 客厅开关 | 2020879703 |
| 三楼楼梯灯 | 2042692296 |
| 书房筒灯开关 | 888910528 |
| 三楼灯 | 2042769877 |
| 一楼卫生间灯 | 20004181 |
| 厨房灯 | 888466709 |
| 小屋开关 | 2042776131 |

## Perception Log Structure

Response fields:
- `logs[]` — array of log entries, each with `id`, `t` (ISO timestamp), and `d` (dict keyed by area name)
- `total_inferences` — count of fresh inferences since last restart. If `0` alongside stale timestamps, the pipeline has NOT started inferring — the logs are cached, not live. See Scenario E. ⚠️ **Note**: `total_inferences` may differ between queries with different `--since` windows (e.g., `--since 10m` returns 0 while `--since 1h` returns 2 moments later). This likely reflects the counter being snapshot at query time, not scoped to the time window. Treat `total_inferences: 0` with fresh timestamps as a warm-up indicator, not necessarily a broken pipeline.

Common areas in `d`:
- **北院** — parking area (vehicles, ground conditions)
- **前院** — patio/terrace (furniture, people, pets)
- **三楼书房** — third-floor study (person at computer)

Each area value is a natural-language description from the vision model. Look for:
- People appearing/disappearing → potential home/away events
- Unusual objects or conditions → alerts

## Query Flags Reference

| Flag | Purpose | Example |
|------|---------|---------|
| `--since` | Relative time window (h/m/s/d, combinable) | `--since 1h`, `--since 2h30m`, `--since 30d` |
| `--limit` | Max entries returned | `--limit 20` |
| `--pretty` | Formatted JSON output | `--pretty` |
| `--jsonl` | One JSON object per line (agent mode, auto-cursor) | `--jsonl` |

**Note**: `--since` and `--jsonl` CAN be combined — `--since 10m --limit 10 --jsonl` works and returns JSONL-format output within the time window. `--jsonl` alone (without `--since`) uses the auto-cursor for incremental agent consumption.
