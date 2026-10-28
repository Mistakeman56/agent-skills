# Perception Log Query Patterns

## Basic Query

```bash
sshpass -p "<PASSWORD>" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 root@192.0.2.10 \
  "pct exec 310 -- bash -c 'export PATH=/usr/local/bin:$PATH; miloco-cli perceive logs --limit 5 2>&1'"
```

## Time-Based Query

```bash
# Last 24 hours
miloco-cli perceive logs --since 24h --limit 10

# Last hour
miloco-cli perceive logs --since 1h --limit 10

# Last 30 minutes
miloco-cli perceive logs --since 30m --limit 5
```

## JSON Output for Agent Processing

```bash
miloco-cli perceive logs --since 1h --jsonl
```

Returns one JSON object per line with format: `"timestamp": {"location": "description"}`

## Response Format

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "logs": [
      {
        "id": "uuid",
        "t": "2026-07-15T19:28:06+00:00",
        "d": {
          "三楼书房": "三楼书房内无人，画面为黑白夜视模式...",
          "北院": "夜间红外画面显示北院停放着一辆白色SUV...",
          "前院": "前院夜视画面，地面铺有地砖..."
        }
      }
    ],
    "count": 10,
    "total_inferences": 2
  }
}
```

## Common Locations in Logs

- 三楼书房 (3rd Floor Study)
- 北院 (North Yard)
- 前院 (Front Yard)
- 一楼卫生间 (1st Floor Bathroom)
- 厨房 (Kitchen)

## Log Content Patterns

- "无人" = no people detected
- "无宠物" = no pets detected
- "夜视模式" / "黑白夜视" = night vision mode (infrared)
- "画面静止" = still image, no motion

## SSH Command Template

```bash
sshpass -p "<PASSWORD>" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 \
  root@192.0.2.10 "pct exec 310 -- bash -c 'export PATH=/usr/local/bin:$PATH; miloco-cli <command> 2>&1'"
```

## Quick Health Check

```bash
# Check if service is running
ssh ... "pct exec 310 -- bash -c 'ps aux | grep miloco | grep -v grep; echo ---; ss -tlnp | grep 1810'"

# Check service logs
ssh ... "pct exec 310 -- bash -c 'miloco-cli service logs 2>&1 | tail -20'"
```

## Event Detection Patterns

For home automation triggers, look for these patterns in logs:

### Home Arrival (回家事件)
- "有人进入" / "有人进门"
- "人员出现" / "检测到人"
- "从门外进入"

### Home Departure (离家事件)
- "所有人离开" / "人员全部离开"
- "无人"持续出现
- "画面空无一人"

### Area Occupancy
- Check if specific area transitions from "无人" to having people
- Monitor for pet detection changes
