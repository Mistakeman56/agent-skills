# 2026-07-09 Cron — High Load False Alarm

## Scenario
- Pre-run script timed out: "获取感知日志超时，PVE/CT <ID> 可能不可达"
- Manual diagnosis showed system was **fully operational**
- Root cause: high container load making miloco-cli slow, not service failure

## Diagnosis Path
1. **PVE reachable?** → Yes (ping 0.06ms)
2. **pct exec works?** → Yes (uptime returned in <2s)
3. **Container load?** → `load average: 11.56, 10.17, 8.99` — very high
4. **Port 1810 listening?** → Yes (python3 PID 19612)
5. **Health OK?** → `{"status":"ok"}`
6. **Perception logs?** → `miloco-cli perceive logs --since 30m --limit 5 --jsonl` returned 5 fresh entries within 5s

## Key Insight
The pre-run script timed out because miloco-cli commands were slow under high load, NOT because the service was broken. The backend was healthy, port bound, and producing fresh inferences. The high load (11.56) made command execution sluggish enough to trigger the script's timeout.

## Pattern: False Alarm vs Real Failure

| Indicator | False Alarm (this session) | Real Failure |
|---|---|---|
| Pre-run script timeout | ✅ | ✅ |
| pct exec `uptime` | Works (<2s) | Hangs (>10s) |
| Port 1810 | Listening | Unbound or zombie-bound |
| Health endpoint | `{"status":"ok"}` | Timeout or connection refused |
| `perceive logs --since` | Returns fresh data | Timeout or stale data |
| Container load | High (11+) | Often normal (1-3) |

**Decision rule**: If `pct exec uptime` works AND port 1810 is listening AND health returns OK, the pre-run script timeout is a load issue, not a service failure. Do NOT restart — just report status.

## Load Source
High load in CT <ID> may be caused by:
- Multiple miloco-cli processes from concurrent cron runs
- Model inference (ORT sessions) consuming CPU
- Camera stream decoding (HEVC)
- Other container processes competing for resources

The load was 11.56 on what is likely a 4-8 core container — sustained high utilization but not a crash condition.
