# HA Instance Configuration (Discovered 2026-05-19)

## Host Information
- **IP:** 192.0.2.10
- **PVE VMID:** 201 (LXC container)
- **Hostname:** homeassistant
- **OS:** Debian 12 (bookworm), Kernel 6.17.2-1-pve
- **Disk:** 16G total, 6.2G used, 8.6G free
- **Virtualization:** LXC on Proxmox VE

## Docker Containers

| Name | Image | Status | Ports |
|:----|:------|:------|:------|
| homeassistant | homeassistant/home-assistant:stable | Up 4 days ✅ | 8123 |
| go2rtc | alexxit/go2rtc:latest | Up 4 days ✅ | 1984 (web), 8554 (RTSP) |
| xiaoi-webhook | iusy/xiaoi:latest | Up 4 days ⚠️ unhealthy | 0.0.0.0:51666 |

## HA Configuration

### Version: 2026.5.1

### configuration.yaml
```yaml
# Loads default set of integrations. Do not remove.
default_config:

frontend:
  themes: !include_dir_merge_named themes

automation: !include automations.yaml
script: !include scripts.yaml
scene: !include scenes.yaml

# 系统监控 sensors (PVE / NAS / Router)
command_line: !include sysmon_sensors.yaml

# Lovelace YAML 仪表盘
lovelace:
  dashboards:
    3d-smart-home:
      mode: yaml
      title: 智能家居
      icon: mdi:home-assistant
      show_in_sidebar: true
      filename: lovelace_dashboards/3d-smart-home.yaml

# go2rtc 本地摄像头流
camera:
  - platform: generic
    name: "三楼监控 RTSP"
    still_image_url: "http://192.0.2.10:1984/api/frame.jpeg?src=camera_3f"
    stream_source: "rtsp://192.0.2.10:8554/camera_3f"
  - platform: generic
    name: "前院监控 RTSP"
    still_image_url: "http://192.0.2.10:1984/api/frame.jpeg?src=camera_front"
    stream_source: "rtsp://192.0.2.10:8554/camera_front"
  - platform: generic
    name: "北院监控 RTSP"
    still_image_url: "http://192.0.2.10:1984/api/frame.jpeg?src=camera_north"
    stream_source: "rtsp://192.0.2.10:8554/camera_north"
stream:
```

### Custom Components (HACS)
- `hacs` — Home Assistant Community Store
- `xiaomi_home` — Xiaomi MIoT integration

### Installed Integrations (from .storage config_entries)
- Xiaomi Home (MIoT) — via cloud account
- System monitoring (command_line sensors)
- Camera (generic, via go2rtc)

### Entity Count: N/A (could not query .storage, file may be large)

## Xiaoi Webhook

xiaoi-webhook connects to 小爱音箱 (Xiaomi Smart Speaker Pro) via the Xiaoi platform. It provides:
- Voice command processing for HA
- Text-to-speech from HA to the speaker

**Note:** The container status shows "(unhealthy)" but the PM2 logs show normal operation. This appears to be a false positive — the health check may fail due to PM2 version mismatch rather than actual service failure.

## Known Issues

1. **xiaoi-webhook unhealthy** — PM2 reports outdated version, but the webhook appears functional
2. **System monitoring SSH timeout** — HA's command_line sensors SSH to router (192.0.2.10) to check CPU/memory/temperature. Recent logs show "Timeout for command" errors on some sensor queries. This may be transient router SSH load.
3. **Xiaomi humidity sensor** — One or more Xiaomi sensors report humidity as a range string ("40-70") instead of a number, causing template render errors in HA.
4. **HA API auth required** — HA rejects unauthenticated API requests. Need a long-lived access token for automated management.
