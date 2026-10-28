# Device DID Reference

## Perception Cameras (via `miloco-cli perceive devices`)

| DID | Name | Room |
|-----|------|------|
| 1179415436 | 小米智能室外摄像机 4 Pro 三摄变焦版 | 前院 |
| 1180976594 | 三楼监控 | 三楼书房 |
| 1176694677 | 北院摄像头 | 北院 |

These DIDs are used with `miloco-cli perceive query --source <DID> --query "..."`.

## Smart Home Devices (via `miloco-cli device control`)

| DID | Name | Usage |
|-----|------|-------|
| 2020879703 | 客厅开关 | `device control 2020879703 switch 0/1` |
| 2042692296 | 三楼楼梯灯 | `device control 2042692296 switch 0/1` |
| 888910528 | 书房筒灯开关 | `device control 888910528 switch 0/1` |
| 2042769877 | 三楼灯 | `device control 2042769877 switch 0/1` |
| 20004181 | 一楼卫生间灯 | `device control 20004181 switch 0/1` |
| 888466709 | 厨房灯 | `device control 888466709 switch 0/1` |
| 2042776131 | 小屋开关 | `device control 2042776131 switch 0/1` |

## Notes

- Perception camera DIDs are for live inference queries (require backend HTTP API on port 1810)
- Smart home device DIDs are for controlling lights/switches (also require backend)
- Camera DIDs can be refreshed via `miloco-cli perceive devices`
- Smart home device DIDs may change if devices are re-paired; verify with `miloco-cli device list` if control fails
