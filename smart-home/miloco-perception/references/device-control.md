# Device Control & Perception Logs Reference

## Perception Logs Parameters

```bash
miloco-cli perceive logs --limit 5              # last 5 events (all time)
miloco-cli perceive logs --limit 5 --since 24h  # last 5 events from past 24 hours
miloco-cli perceive logs --limit 5 --since 48h  # last 5 events from past 48 hours
```

The `--since` parameter accepts relative time strings (e.g., `1h`, `24h`, `48h`, `7d`). Useful for filtering recent events without retrieving the entire history.

## Device Control Command Reference

### Syntax

```bash
miloco-cli device control [OPTIONS] DID [IID] [VALUE]
```

### Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| DID | Device ID (6-10 digit number) | 888910528 |
| IID | Interface ID (device capability) | switch, brightness, color_temperature |
| VALUE | Value to set | true/false, 0-100, color values |

### Common Device Interfaces

| Device | DID | IID (use `on@开关` or `prop.s.p`) | Values |
|--------|-----|-----|--------|
| 书房筒灯开关 | 888910528 | `on@开关` or `prop.2.1` | true (on) / false (off) |
| 客厅开关 | 2020879703 | `on@开关` or `prop.2.1` | true / false |
| 三楼楼梯灯 | 2042692296 | `on@开关` or `prop.2.1` | true / false |
| 三楼灯 | 2042769877 | `on@开关` or `prop.2.1` | true / false |
| 一楼卫生间灯 | 20004181 | `on@开关` or `prop.2.1` | true / false |
| 厨房灯 | 888466709 | `on@开关` or `prop.2.1` | true / false |
| 小屋开关 | 2042776131 | `on@开关` or `prop.2.1` | true / false |

### ⚠️ PITFALL: IID Disambiguation Required

Using bare `on` or `switch` as the IID **fails** with:
```
spec_name 'on' matches 3 iids on '888910528', use spec_name@<子设备描述> or prop.s.p to disambiguate
```

This is because switches expose multiple `on` properties (开关, 全部开关指示灯状态, 指示灯状态). You MUST disambiguate with one of:
- **`on@开关`** — human-readable, preferred for clarity
- **`prop.2.1`** — numeric IID, works but less readable

Use `miloco-cli device props <DID>` to discover the correct IID for any device.

## Examples

```bash
# Turn off study room light (use on@开关 to disambiguate)
miloco-cli device control 888910528 on@开关 false

# Turn on living room light
miloco-cli device control 2020879703 on@开关 true

# Alternative: use numeric IID prop.2.1
miloco-cli device control 888910528 prop.2.1 false

# List available devices
miloco-cli device list

# Get device spec (capabilities) — shows all IIDs
miloco-cli device spec <DID>

# Get current device properties — shows IID values and spec_names
miloco-cli device props <DID>
```

## Troubleshooting

- **Timeout**: `device control` may timeout when backend is partially degraded (see `fallback-when-cli-hangs.md`)
- **"spec_name 'on' matches 3 iids"**: Bare `on` or `switch` is ambiguous — use `on@开关` or `prop.2.1` instead (see PITFALL above)
- **"Got unexpected extra argument"**: Check parameter order — DID, IID, VALUE (not DID, IID, VALUE, extra)
- **"No such command"**: Ensure using `miloco-cli device control` not `miloco-cli devicecontrol`
- **Backend unreachable (`cannot connect to Miloco backend at http://127.0.0.1:1810`)**: Backend process is down, not just hung. `miloco-cli service start` may also hang in this state. See `ct310-recovery.md` for full restart procedure.
