# 2026-07-08 Cron: Post-Restart Pipeline Failure + Progressive Degradation

## Timeline
- Pre-run script timed out (same session as the 07-08 zombie-bound port incident)
- Diagnosed Scenario B+ → PID-targeted nuclear restart (kill -9 6 PIDs → clear socket → supervisord)
- **Health passed** (`{"status":"ok"}`) after ~25s wait
- But: `perceive logs --since 30m`, `perceive devices`, `service logs` ALL timed out (20-30s)
- Then: even basic `ps aux | grep miloco` inside container started timing out
- Container entered **progressive degradation** — commands that worked initially became unreachable
- Restart budget exhausted (1 nuclear restart used; further restarts would worsen degradation)

## Key Observations
- This is a **distinct failure mode from E+**: health passes and stays OK, but the perception pipeline never produces fresh inferences. The backend server (uvicorn) is alive and responding to `/health`, but the inference pipeline (model loading, camera processing, vision API calls) is stuck or non-functional.
- Progressive degradation happened within ~60s of the pipeline being stuck — each failed CLI command consumed container resources, making subsequent commands also fail.
- The miloco.main process was in R state (25.7% CPU, 539MB RSS) suggesting it was actively trying but failing to process something.
- Multiple stuck `miloco-cli service start` zombies (4 processes) were present before the nuclear restart — these may have contributed to resource pressure.

## Diagnostic Signature
```
health: OK
perceive logs: timeout (>30s)
perceive devices: timeout (>20s)
service logs: timeout (>20s)
ps aux: timeout (>15s)  ← progressive degradation signal
```

## Lesson
After nuclear restart, if health passes but CLI commands hang, do NOT keep retrying. The progressive degradation pattern means each failed command makes the container worse. Stop immediately and report as upstream failure. The 2-restart budget exists precisely for this scenario.
