# Home Assistant Lovelace Dashboard Layout Optimization

How to inspect, analyze, and reorganize HA Lovelace YAML dashboards for a cleaner UX.

## Trigger

User says: "排版有点乱", "帮我整好", "排版整一下", "优化一下布局", "改一下dashboard"

## Workflow

### 1. Locate Dashboard Files

HA dashboards configured in YAML live under `/config/lovelace_dashboards/` inside the HA container:

```bash
# From PVE host (jump box)
pct enter <VMID> -- bash -c 'docker exec homeassistant ls -la /config/lovelace_dashboards/'
```

Common dashboards:
| File | Description |
|:----|:-----------|
| `3d-smart-home.yaml` | Custom "智能家居" sidebar dashboard |
| `ui-lovelace.yaml` | Default HA dashboard (also at `/config/ui-lovelace.yaml`) |

The sidebar configuration (which dashboard appears in the sidebar) is in `/config/.storage/lovelace.views` or set via `ui-lovelace.yaml`.

### 2. Read & Analyze

Read the full dashboard YAML:

```bash
pct enter <VMID> -- bash -c 'docker exec homeassistant cat /config/lovelace_dashboards/<dashboard>.yaml'
```

**What to look for (layout issues):**
- **Duplicate cards** — Same entity appearing in multiple places on the same page (esp. switches)
- **Redundant views** — Same camera shown in both go2rtc (frame.jpeg) and HA native (picture-entity) formats
- **Inconsistent styling** — Some floors use `mushroom-light-card`, others use `mushroom-switch-card` for the same entity type
- **Repetitive navigation** — Navigation chip-bar repeated inside every section on the same page
- **Missing grouping** — No room-level organization in "设备" (devices) view; all entities dumped in one list
- **Card type mismatch** — Using `switch` entities with `light-card` or vice versa
- **Over-nested vertical-stacks** — Deeply nested vertical-stacks that could be flat horizontal-stacks

### 3. Understand Entity Landscape

Before redesigning, know what the user actually has:

```bash
# Get entity list grouped by domain
curl -s -H "Authorization: Bearer $HA_TOKEN" "http://<HA_IP>:8123/api/states" | \
  python3 -c "
import json, sys
from collections import Counter
data = json.load(sys.stdin)
domains = Counter()
for e in data:
    domains[e['entity_id'].split('.')[0]] += 1
for d, c in domains.most_common():
    print(f'  {d}: {c}')
"
```

Then list the specific entities you need:
- `light.*` — actual dimmable lights (BT mesh筒灯, Yeelight吸顶灯)
- `switch.*_on_p_*_1` — physical switch controls (the real on/off switches)
- `cover.*_s_2_curtain` — curtains
- `climate.*` — AC units
- `camera.*` — camera entities

### 4. Design Principles for This User's Dashboard

- **One card type per entity class** — `mushroom-light-card` for light switches (even if entity is `switch.`), `mushroom-entity-card` for non-light devices
- **Room grouping** — Group controls by room/floor, not by device type
- **Single nav bar** — Navigation chips at the very top only, never repeated per section
- **No camera duplication** — Choose one streaming approach (go2rtc frame.jpeg is faster) and stick with it
- **Compact first page** — Home page should be an overview with quick access to rooms, not a bloated control panel
- **Consistent card_mod styling** — Use same border-radius, background color pattern everywhere (`rgba(color,0.08)` + `border-radius: 20px`)
- **Hover effects on interactive cards** — `transform: translateY(-2px)` for tactile feedback
- **Separate "全部设备" page** — Flat list grouped by floor/room for when you need to find any device
- **Color by room not by type** — Each floor gets its own accent color rather than all lights being yellow

### 5. Rewrite the YAML

Recommended view structure:

```
首页 (home)
  ├── Navigation chips (all floors + cameras + devices + servers)
  ├── Welcome title card (gradient background, dynamic temp)
  ├── Quick status row (weather + indoor temp + humidity)
  ├── Floor quick-entries (一楼/二楼/三楼: 3 cards each — main light + secondary + curtain)
  └── Common devices row (desktop PC + light master switch + AC)

一楼 (floor1) / 二楼 (floor2) / 三楼 (floor3)
  ├── Navigation chips (home + other floors)
  ├── Section title
  ├── Lighting section (horizontal-stack of mushroom-light-cards)
  ├── Devices section (空调 + 窗帘)
  └── Gauge section (温度 + 湿度)

院子 (yard) — 4 mushroom-entity-cards for outdoor lights

监控 (cameras)
  ├── go2rtc live feeds (picture cards with click-to-webrtc)
  └── Power switches + storage space

设备 (devices) — entities grouped by floor/room, flat list

服务器 (servers) — gauge cards + apexcharts for PVE/NAS/Router
```

### 6. Deploy the Update

```bash
# Step 1: Write new YAML to /tmp on PVE host
# Step 2: Push to LXC
sshpass -p 'PVE_PASS' ssh root@PVE_HOST "pct push <VMID> /tmp/<new_dashboard>.yaml /tmp/<new_dashboard>.yaml"

# Step 3: Copy into HA container
sshpass -p 'PVE_PASS' ssh root@PVE_HOST 'pct enter <VMID> -- bash -c \
  "docker cp /tmp/<new_dashboard>.yaml homeassistant:/config/lovelace_dashboards/<dashboard>.yaml"'

# Step 4: Restart HA to pick up changes
pct enter <VMID> -- bash -c 'docker restart homeassistant'

# Step 5: Verify HA comes back
sleep 10
curl -s -H "Authorization: Bearer $HA_TOKEN" "http://<HA_IP>:8123/api/states" | \
  python3 -c "import json,sys;d=json.load(sys.stdin);print(f'HA OK, {len(d)} entities')"
```

Also create a backup before overwriting:
```bash
pct enter <VMID> -- bash -c \
  'docker exec homeassistant cp /config/lovelace_dashboards/<dashboard>.yaml /config/lovelace_dashboards/<dashboard>.yaml.bak'
```

### 7. HA REST API Token Management

- Long-lived tokens are generated from HA Web UI → user profile → Security → Long-Lived Access Tokens
- Old tokens may expire — test first: `curl -s -H "Authorization: Bearer $TOKEN" "http://<HA_IP>:8123/api/config"`
- If 401, user needs to create a new one
- Store in memory for future sessions

### Common Pitfalls

- **YAML indentation strictness** — HA Lovelace YAML is sensitive. Test locally with `python3 -c "import yaml; yaml.safe_load(open('file.yaml'))"` if you have PyYAML
- **Entity IDs may change** — After HA restart or MIoT re-auth, entity IDs with `_p_2_1` suffixes can shift. Verify entities still exist before deploying
- **`docker cp` from PVE host requires file in LXC first** — Use `pct push` to get the file into the LXC, then `docker cp` from LXC to container
- **HA long wait on restart** — ~5-10 seconds for HA to restart, ~30s for go2rtc. Check API before assuming it's down
- **Camera entities have both `camera.*` and `switch.*_on_p_2_1`** — The switch controls the camera power, the camera entity shows the stream
