# TTS Speaker Control — Detailed Reference

## The Parameter Prefix Bug

When calling `miloco-cli device action` for TTS, the CLI accepts parameters as positional args after the action IID. The spec shows parameters like `text-content:string`, but this is a **type annotation**, not a parameter name to pass.

### Correct format
```bash
miloco-cli device action <DID> <ACTION_IID> '纯净文本'
```

### Wrong format (prefix gets spoken!)
```bash
miloco-cli device action <DID> <ACTION_IID> text-content:string='纯净文本'
# Speaker will say: "text-content:string 纯净文本"
```

### Why this happens
The CLI's `device action` command takes `params` as `nargs=-1` (variadic positional args). Each param is processed by `infer_value()` which just type-converts the raw string. The `text-content:string=` prefix is NOT stripped — it's passed verbatim to the Xiaomi API as part of the text value.

The spec annotation `text-content:string` describes the parameter's name and type for documentation, but the CLI expects just the value.

## Checking a new speaker's action IID

Different Xiaomi speaker models use different service/ action IDs:

```bash
# Get full spec
miloco-cli device spec <DID>

# Look for play-text in the actions section
# Output format: action.{siid}.{aiid}  play-text|x|text-content:string
# The IID is the first field (e.g., action.5.3 or action.7.3)
```

### Known mappings
| Model | play-text IID | Notes |
|-------|--------------|-------|
| 蓝色智能音箱 (小米小爱音箱) | action.5.3 | siid=5 for TTS |
| Xiaomi 智能音箱 Pro | action.7.3 | siid=7 for TTS |
| 橙色智能音箱 | action.7.3 | Same series as Pro |

The siid differs because different hardware generations organize services differently.

## Full SSH chain

```bash
# From CT <ID> (Hermes host) → PVE → CT <ID>
sshpass -p '<PASSWORD>' ssh -o StrictHostKeyChecking=no root@192.0.2.10 \
  'pct exec 310 -- /usr/local/bin/miloco-cli device action 979939218 action.5.3 你好'
```

## Quoting gotchas
- The entire `pct exec` command should be in single quotes
- The text parameter should NOT have extra quotes around it
- Chinese punctuation (，。！) works fine in the text
