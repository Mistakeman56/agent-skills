# Cron Job Monitoring — Graceful Degradation

When running as a scheduled cron job and the perception pipeline is down:

## Step 1: Quick Diagnostic Shortcut

Try `person list` + `perceive devices` first. These work WITHOUT `MILOCO_TOKEN` and test whether the backend is alive:

```bash
pct exec 310 -- bash -c 'export PATH=/usr/local/bin:$PATH; miloco-cli person list 2>&1 | head -5'
pct exec 310 -- bash -c 'export PATH=/usr/local/bin:$PATH; miloco-cli perceive devices 2>&1 | head -5'
```

- **Both work** → Backend is alive. `perceive logs` failure is almost certainly the missing token. Set it and retry.
- **`person list` works, `pct exec` starts hanging** → Progressive degradation in progress. Report and stop.
- **`pct exec` times out** → Container fully hung. Don't attempt recovery in a cron job unless explicitly instructed.

## Step 2: Report Concisely

Don't run 10+ diagnostic commands in a cron job. The user wants a status, not a debugging session.

### Output Patterns

```
# ✅ Normal — no notification needed
感知引擎正常，最近1小时有N条事件。

# ⚠️ Degraded — brief notification
感知引擎部分不可用：perceive logs 失败（疑似token过期），person/devices 正常。建议检查。

# 🔴 Down — brief notification
感知引擎无法访问（CT <ID> 响应超时）。PVE 在线，建议检查容器状态。
```

## Progressive Degradation Pattern

The container can go from "some commands work" to "fully hung" within the same session. If you see partial functionality (e.g. `person list` works but `perceive logs` fails, then `pct exec` starts timing out), report the trend rather than treating each failure independently.

## What NOT to Do in a Cron Job

- **Don't** attempt `pct stop`/`pct start` — this is disruptive and should only happen when explicitly instructed.
- **Don't** run 5+ SSH commands trying to diagnose — each one may hang if the container is degrading.
- **Don't** kill processes (`killall`) — same reason.
- **Do** report the status and suggest the user check manually, or ask if they want you to attempt recovery.

## Recovery (Only When Instructed)

If the user asks you to fix it, follow the recovery procedures in `hung-container-recovery.md`.
