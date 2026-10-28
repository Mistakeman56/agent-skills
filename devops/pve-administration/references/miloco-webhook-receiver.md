# Miloco Webhook Receiver — Architecture Reference

## Overview
- **Location**: CT <ID> (192.0.2.10), port 18789
- **File**: `~/.hermes/scripts/miloco-webhook-receiver.py`
- **Version**: v5
- **Stack**: Flask + subprocess (SSH to CT <ID> for TTS)

## Event Flow
```
Camera → Miloco perception engine → webhook POST → receiver
  ├─ Parse event (priority, source, detection, suggestion)
  ├─ Filter (ignore list, cooldown, quiet hours)
  ├─ Route to correct speaker by floor
  ├─ TTS via sshpass → PVE → pct exec → miloco-cli
  └─ WeChat notification via hermes send
```

## Miloco Webhook Protocol
Miloco sends POST to configured `agent_webhook_url` with:
```json
{
  "action": "agent",
  "payload": {
    "message": "[感知引擎]事件提醒：\n时间：...\n来源：...\n检测到：...\n事件优先级：...\n建议：...",
    "sessionKey": "agent:main:miloco-suggest",
    "traceId": "uuid",
    "idempotencyKey": "uuid",
    "timeoutMs": 180000
  }
}
```

Required response format:
```json
{"code": 0, "message": "ok", "data": {"runId": "...", "status": "ok"}}
```

If response is wrong, Miloco retries with `get_trace` action.

## Quiet Hours
- **22:00 - 08:00**: Speaker TTS disabled, WeChat notifications still sent
- User's family sleeps — speaker is too loud/jarring at night
- Implemented via `QUIET_HOURS_START` / `QUIET_HOURS_END` constants

## Deduplication
- Fingerprint: `{source}:{detection[:30]}`
- Cooldown: 300 seconds (5 minutes)
- Prevents same event from triggering repeated notifications

## Event Parsing
Message format from Miloco:
```
[感知引擎]事件提醒：
时间：HH:MM:SS
来源：{room}的{camera_name}(did={did})
检测到：{detection_text}
事件优先级：{low|medium|high|urgent}
建议：{suggestion}
```

Extracted via regex: `extract_priority()`, `extract_source()`, `extract_detection()`, `extract_suggestion()`

## Notification Logic
- **Medium/High/Urgent priority** → speaker TTS + WeChat
- **Person-related keywords** (人, 人体, user, 移动, 进入, 出现) → speaker TTS + WeChat
- **Everything else** → save only, no notification
- **Ignore list** → skip entirely (e.g., "书房沙发上堆满衣物")

## TTS Text Construction
Build short, natural Chinese sentences based on detection content:
- Person recognized: "检测到你回来了"
- Abnormal sound: "检测到异常声音，请注意安全"
- Stranger: "检测到陌生人，请注意安全"
- General: "检测到{detection[:20]}"

## Deployment
1. Kill old: `fuser -k 18789/tcp`
2. Start new: `cd ~/.hermes/scripts && python3 miloco-webhook-receiver.py`
3. Background with `terminal(background=True)`

## Dependencies
- Flask (installed on CT <ID>)
- sshpass (for PVE SSH)
- hermes send (for WeChat notifications)
