# 2026-07-10 Cron — High Load Progressive Degradation

## Scenario
- Pre-run script failed: "无法解析感知日志"
- Manual diagnosis: service initially healthy, container load 13.43
- Commands that initially worked started timing out as session progressed
- HEVC frame drops coexisting with partial pipeline functionality

## Diagnosis Path
1. **PVE reachable?** → Yes
2. **CT <ID> running?** → Yes
3. **pct exec works?** → Yes (`uptime` returned: load 13.43)
4. **Port 1810 listening?** → Yes (python3 PID 119572)
5. **Health OK?** → `{"status":"ok"}`
6. **Perception logs?** → `--since 10m` returned 2 entries (01:23, 01:26 UTC); `--since 1h` returned 5 entries (00:31-00:44 UTC) with total_inferences: 2
7. **Service logs?** → Continuous HEVC frame drops + empty frames, but pipeline producing some inferences

## Progressive Degradation Pattern
Commands started timing out after ~5 rounds of queries:

| Round | Command | Result |
|-------|---------|--------|
| 1 | `pct exec uptime` | ✅ 2s |
| 2 | `pct exec ss -tlnp \| grep 1810` | ✅ 5s |
| 3 | `pct exec curl health` | ✅ 5s |
| 4 | `pct exec miloco-cli perceive logs --since 10m` | ✅ returned data |
| 5 | `pct exec miloco-cli service logs --lines 30` | ✅ returned data |
| 6 | `pct exec miloco-cli perceive logs --since 1h` | ✅ returned data |
| 7 | `pct exec miloco-cli perceive logs --since 30m --pretty` | ❌ timeout 30s |
| 8 | `pct exec miloco-cli service status` | ❌ timeout 15s (×3) |
| 9 | `pct exec ps aux \| grep miloco` | ❌ timeout 10s |
| 10 | `pct exec miloco-cli perceive logs --since 10m` | ❌ timeout 30s |
| 11 | `lxc-attach pgrep -la python3` | ❌ timeout 15s |
| 12 | `pct exec echo HELLO` | ❌ timeout 10s |

**Key insight**: Under extreme load (13+), the container doesn't "hang" in the traditional sense — it becomes progressively slower until even trivial commands time out. This is distinct from Scenario A (container-level hang where pct exec/lxc-attach hang from the start).

## HEVC Drops + Working Pipeline Coexistence
Service logs showed continuous `drop non-key frame, MIoTCameraCodec.VIDEO_HEVC` messages, yet the pipeline still produced 2 fresh inferences (total_inferences: 2). The HEVC drops were severe but not total — enough keyframes got through for partial pipeline operation.

This is a middle ground between:
- **Transient HEVC drops** (self-resolving in ~15s, normal startup)
- **Persistent HEVC failure** (pipeline completely stuck, total_inferences: 0)

In this session: HEVC drops ongoing but pipeline functional → partial observation capability.

## total_inferences Inconsistency
- `--since 10m` → total_inferences: 0
- `--since 1h` → total_inferences: 2 (queried moments later)

Possible explanations:
1. `total_inferences` is scoped to the query's time window (fresh inferences within the window only)
2. Counter resets between queries (unlikely)
3. The 10m window had no NEW inferences (only cached data within that window)

Most likely: `total_inferences` counts inferences since service restart, not within the query window. The 10m query returned 2 cached entries with total_inferences: 0 at query time, while the 1h query (run later) saw total_inferences: 2.

## Decision: Stop Probing
When commands start timing out under high load, STOP probing immediately. Each probe adds to the load. The essential data was already collected in rounds 1-6. Continuing to probe (rounds 7-12) provided no new information and worsened the degradation.

## Lessons
1. **High load (13+) causes progressive timeout**: Not a binary hang, but a gradual slowdown
2. **HEVC drops can coexist with partial pipeline**: Don't assume pipeline is dead just because service logs show HEVC errors
3. **Stop probing early**: If you have the essential data, don't keep querying a degraded container
4. **`service logs` uses `--lines` not `--limit`**: CLI flag difference from `perceive logs`
