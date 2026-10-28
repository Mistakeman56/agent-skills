# Home Assistant Administration (Consolidated from homeassistant-sysadmin)

## Access Pattern
HA runs inside a PVE LXC container. Direct SSH often fails — use PVE host as jump box:
```bash
sshpass -p 'PVE_PASS' ssh root@PVE_HOST "pct list | grep -i 'ha\\|home\\|homeassistant'"
sshpass -p 'PVE_PASS' ssh root@PVE_HOST 'lxc-attach -n <VMID> -- bash -c '\''COMMAND_HERE'\'' 2>&1'
```

## Key Containers
| Container | Purpose | Port |
|:---------|:--------|:----:|
| **homeassistant** | HA core (ghcr.io/home-assistant/home-assistant:stable) | 8123 |
| **go2rtc** | RTSP camera stream proxy | 1984 (web), 8554 (RTSP) |
| **xiaoi-webhook** | 小爱音箱 webhook bridge | 51666 |

## Inspection Checklist
1. Host info (`hostnamectl`, `df -h`, `uname -a`)
2. Docker containers (`docker ps --format`)
3. HA version (`docker exec homeassistant cat /config/.HA_VERSION`)
4. HA config (`docker exec homeassistant cat /config/configuration.yaml`)
5. Custom components (`docker exec homeassistant ls /config/custom_components/`)
6. Entity count (from `.storage/core.entity_registry`)
7. Error logs (`docker logs --tail 100`)
8. Port listening (`ss -tlnp`)

## Common Config Files (inside Docker)
| Path | Content |
|:----|:--------|
| `/config/configuration.yaml` | Main config |
| `/config/automations.yaml` | Automations |
| `/config/custom_components/` | HACS integrations |
| `/config/.storage/` | Persistent state |

## Common Error Patterns
- **xiaoi-webhook unhealthy**: Often benign, restart container
- **SSH timeout for system sensors**: Router SSH may hang under load
- **Xiaomi humidity range error**: Sensor returns "40-70" string instead of number — create template sensor
- **HA Login Attempt Warnings**: Normal when curling API without auth token

## API Access
- Create long-lived token: User profile → Security → Long-Lived Access Tokens
- Test: `curl -s -H "Authorization: Bearer TOKEN" http://HA_IP:8123/api/states`
- Key endpoints: `/api/`, `/api/config`, `/api/states`, `/api/services/<domain>/<service>`

## Xiaomi MIoT Integration Notes
- Uses `custom_components/xiaomi_home`
- Xiaomi lights often appear as `switch.` not `light.` — use `mushroom-entity-card` with `use_light_color: true`
- AC/climate may be split into `switch.*_power` + `sensor.*_temp`

## Dashboard Layout Optimization
See `ha-dashboard-layout-optimization.md` for complete workflow.

## Pitfalls
- Direct SSH to HA LXC may fail — use PVE host `lxc-attach` instead
- HA version file is at `/config/.HA_VERSION` inside Docker, not on host
- Large YAML (>30KB) deployment: Write to PVE host `/tmp/` → `pct push` to LXC → `docker cp` to container
- `docker cp` from PVE host requires file in LXC first; use `pct push` as intermediate
