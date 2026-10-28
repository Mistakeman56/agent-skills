# Watchdog Self-Stall Kill Loop (SIGKILL every 3-5 min)

> 🔗 Related: omni-401 kill loop (`perception-degradation.md`) · CLI-empty wrapper quirk (`fallback-when-cli-hangs.md` → "Direct Python Invocation")

## Signature (observed 2026-08-01 ~03:15 UTC)

Distinct from the omni 401 degradation loop. The backend is **not** hung on HTTP calls — it is being SIGKILLed repeatedly by its own watchdog after the main loop stalls:

1. **`supervisord.log` shows a repeating SIGKILL cadence** — the fastest way to confirm:
   ```bash
   sshpass -p "<PASSWORD>" ssh -o ConnectTimeout=8 root@192.0.2.10 \
     "pct exec 310 -- tail -30 /root/.openclaw/miloco/log/supervisord.log"
   ```
   Pattern: `WARN exited: miloco-backend (terminated by SIGKILL; not expected)` → `spawned` → `entered RUNNING state` every ~3-5 minutes, on a regular clock (02:34, 02:43, 02:54, 02:58, 03:01, 03:04, 03:07, 03:13, 03:15, 03:23, 03:27).

**Cadence variance (observed 2026-08-01 12:00–12:20 local)**: the interval is NOT fixed at 3–5 min — a later episode cycled every ~6–10 min (03:54 → 04:02 → 04:12 → 04:18 UTC, respawn pids 221901/228695/236206/243951). Confirm the loop from the SIGKILL cadence itself, not from the interval length. Quick quantification: `tail -150 /root/.openclaw/miloco/log/supervisord.log | grep -cE "exited: miloco-backend"` — 50 cycles in 150 lines = serious ongoing loop.

2. **Backend log tail ends with the watchdog line**:
   ```
   [watchdog] self-stall detected: 185.9s since last tick
   ```
   Preceded by a flood of `miot.decoder - INFO - drop non-key frame, MIoTCameraCodec.VIDEO_HEVC, <id>` and `video frame is empty, 5, <id>` lines → the stall is in the **camera HEVC decode / frame ingestion path**.

3. **`perceive logs --since 3h` returns `No logs found`** (not an error) — backend restarts so often no inference ever completes; this is NOT a quiet period.

4. **Container memory is NOT the cause**: `free -m` shows ~2GB total / ~95MB used, plenty free — this loop is not OOM. Do not chase memory before checking the watchdog line.

**Host-side fast signature — PID churn (validated 2026-08-01 ~14:00 local)**: when `pct exec` hangs under load, poll from the PVE host — no container access needed:
   ```bash
   sshpass -p "<PASSWORD>" ssh -o ConnectTimeout=8 root@192.0.2.10 \
     "ps aux | grep 'miloco.ma[i]n' | grep -v grep"
   ```
   A kill loop shows a NEW miloco.main PID every ~3-5 min, each ramping to ~150% CPU then dying (observed 125696 @13:56 → 136714 @14:02 → 144879 @14:05). Contrast with a normal single long inference: the SAME PID sustains 120-150% for 10-30 min, then exits. **PID churn + load oscillation = loop; PID stable at high CPU = wait it out.** This lets you conclude "crash-looping backend, NOT PVE/CT <ID> unreachable" from the host alone, before touching supervisord.log — and tells you NOT to burn time on inference-wait polls (they never converge mid-loop).

## Diagnostic sequence (fast → slow)

1. `supervisorctl -c /root/.openclaw/miloco/supervisord.conf status` — note `uptime 0:00:xx` keeps resetting.
2. `tail /root/.openclaw/miloco/log/supervisord.log` — confirm SIGKILL cadence (step 1 above).
3. Find the live backend log: logs are **dated files**, not a single `miloco-backend.log` (that path may be empty/missing!):
   ```bash
   pct exec 310 -- bash -c 'ls -t /root/.openclaw/miloco/log/miloco-backend_*.log | head -3'
   ```
   Then `tail -30 <newest>` → look for `[watchdog] self-stall detected` + `miot.decoder` frame drops.
4. Check `dmesg` for OOM just in case (this loop had none).

## Handling

- **Do not** keep probing the CLI mid-loop — each `pct exec` attempt that hangs leaves lxc-attach zombies (see `fallback-when-cli-hangs.md` pitfall #0). The CLI often answers quickly here (backend restarts are fast), but the wrapper may return EMPTY → use the python3 direct invocation.
- **Bulk-killing the stuck cron processes does NOT stop the loop** (validated 2026-08-01): after the self-safe kill of stacked `perceive logs`/`service start` leftovers, miloco.main PIDs kept churning (125696→136714→144879) and the supervisord SIGKILL cadence continued. The loop predates the cleanup (already cycling at 05:21 UTC, before any cron kill). Clean up the stacked processes to relieve CPU (they compound load), but do NOT repeat kills or escalate to container restart thinking you caused/worsened the loop — the root cause is the camera HEVC decode stall, and restarting just resumes the cycle.
- The service self-recovers in the sense that supervisord keeps respawning it, but it never stabilizes — it will keep cycling until the camera stream issue is fixed.
- **"Wait for warmup then re-probe" does NOT converge during the loop** (observed 2026-08-01): after a 150s warmup wait the CLI still returned `cannot connect to Miloco backend` — the just-respawned backend had been SIGKILLed again mid-wait. Before spending time on warmup waits, read supervisord.log's exit cadence: a single restart → wait ~2 min is right; a repeating SIGKILL cadence → don't wait, the next kill arrives before the probe completes; report the loop instead.
- Report to the user honestly: "perception engine unstable, no reliable home/away events, no light control performed" (matches the monitor-cron reporting contract).
- Candidate fixes to suggest (not to silently apply): restart via `miloco-cli service restart`; if SIGKILL cadence continues, check the camera stream config / network for the HEVC source; consider raising CT <ID> memory (2GB) only if OOM evidence appears.

## Why it matters for the monitor cron

A crash-looping backend means the pre-run log fetch can timeout (the "⚠️ 获取感知日志超时" banner) even though PVE/CT <ID> are fully reachable. Before concluding "PVE/CT <ID> 不可达", verify with `pct status 310` + plain SSH — the host/container are usually fine; the backend is cycling. Distinguish — but NOTE the two can COEXIST (observed 2026-08-01 12:13 local): supervisord showed the SIGKILL cadence (watchdog loop) while the just-respawned backend's log already contained `miloco.perception.engine.pipeline - WARNING ... 感知API调用失败，错误码=HTTPStatusError:401(skipped) ... token-plan-cn.xiaomimimo.com` lines ~60s after startup. So a crash-looping backend can ALSO be omni-401-dead: even in its brief healthy windows it produces zero home/away events because the semantic stage fails every call. Always check BOTH signals and report both — renewing the omni key fixes the 401 but NOT the watchdog loop, and vice versa. Quantify 401s with `tail -4000 /root/.openclaw/miloco/log/miloco-backend.log | grep -cE "感知API调用失败|401 Unauthorized"` plus a `tail -2` sample line to confirm recency.
- omni 401 loop → degradation, inference skipped, backend stays up
- watchdog self-stall loop → backend keeps dying, no inference ever completes
- both together → backend keeps dying AND every brief run is semantically dead
