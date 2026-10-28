# Cron Monitoring Workflow for Miloco Perception

## How to Read Perception Logs for Home/Away Events

### Timestamp Conversion
All perception log timestamps are **UTC** (`+00:00`). Add **8 hours** for Beijing time:
```
UTC 02:25 → Beijing 10:25
UTC 22:30 → Beijing 06:30 (next day)
```

### Log Structure
Each log entry has:
- `t`: ISO 8601 UTC timestamp
- `d`: Dict of `{area_name: scene_description}` — natural language

**Empty `d: {}`** means no camera activity was detected (normal, skip it).

### Key Areas to Monitor
| Area | Camera | What to Look For |
|------|--------|------------------|
| 三楼书房 | Indoor | Person present → home; empty bed + desk = person left |
| 前院 | Outdoor | Person arriving/leaving |
| 北院 | Outdoor | Cars moving, person walking → arrivals/departures |

### Home/Away Detection Heuristics
- **Person visible in 三楼书房** = someone is home (usually assistant)
- **三楼书房 empty + bed messy + no person** = person likely sleeping or left
- **Person walking in 北院/前院** = potential arrival/departure event
- **Car movement in 北院** = potential arrival/departure

### Typical Cron Query
```bash
# Get last 2 hours of logs for monitoring
miloco-cli perceive logs --since 2h --limit 50 2>&1
```

Parse the JSON response:
```python
import json, datetime
data = json.loads(raw_output)
for log in data['data']['logs']:
    utc_time = datetime.datetime.fromisoformat(log['t'])
    bj_time = utc_time + datetime.timedelta(hours=8)
    areas = log['d']
    if areas:
        for area, desc in areas.items():
            print(f"[{bj_time.strftime('%H:%M')}] {area}: {desc}")
    else:
        pass  # empty detection, skip
```

### Common Pitfalls
1. **UTC vs Beijing time**: Always convert when presenting to user. A log at "02:30" is actually 10:30 AM.
2. **Empty `d: {}`**: These are frequent — they mean no camera detected anything meaningful. Don't report them.
3. **"陌生人" vs "user"**: The ReID model sometimes can't identify assistant and labels him as "陌生人". Don't alarm on this — it's a recognition gap, not an intrusion.
4. **Backend connectivity after restart**: If `perceive logs` returns "cannot connect to Miloco backend", check `ss -tlnp | grep 1810` and `ps aux | grep miloco`. The backend takes ~5s to start after supervisord restarts it.
5. **MILOCO_TOKEN required**: Even with the backend healthy on port 1810, `miloco-cli perceive logs` needs `export MILOCO_TOKEN=...` in the environment. The token is in the web UI's `index.html` (`window.__MILOCO_TOKEN__`). Without it, the CLI reports "cannot connect" despite the backend being up.

### Fallback: Active Perception Query When Logs Are Stale

When `perceive logs` returns old/stale data (pipeline stopped), you can still check current camera state via `perceive query`:

```bash
# Check if anyone is home right now (real-time inference)
pct exec 310 -- bash -c 'export PATH=/usr/local/bin:$PATH; miloco-cli perceive query --source 1180976594 --query "三楼书房有人吗？" 2>&1'
```

This triggers fresh multi-modal inference (5-30s) rather than reading cached logs. Useful when logs are days old but cameras are still online. Requires the same MILOCO_TOKEN as perceive logs.
