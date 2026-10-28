---
name: home-assistant-admin
description: "Use when the user 要接入或设计 Home Assistant（MCP 连通、仪表盘与实体筛选、摄像头/监控流接入）。"
version: 1.2.0
author: Hermes Agent
license: MIT
---

# Home Assistant 管理（走 MCP）

the user said 「玩 HA 一直玩不明白」，根因通常**不是设备少，而是实体噪声 + 一屏堆完**。设计目标：按功能分 view、只放真正会被操控的实体。他对「3D/炫酷」有兴趣，但先把「信息聚在一起」解决掉再谈锦上添花。

## 0. 拓扑（先确认再动手）

| 组件 | 位置 |
|---|---|
| HA 本体 | CT <ID> Docker，`192.0.2.10:8123`，`location_name=我的家`，约 1630 实体 |
| HA 配置 | CT <ID> 宿主 `/opt/ha-config/configuration.yaml`（容器内才是 `/config`）|
| HA MCP | Hermes `config.yaml → mcp_servers.homeassistant`，`mcp-compressor … ssh root@192.0.2.10 /opt/mcp-start-ha.sh` |
| MCP 启动脚本 | `.197` 上 `/opt/mcp-start-ha.sh`：`export HOMEASSISTANT_URL/TOKEN` 后起 `ha-mcp` |
| **另一台 HA** | NAS `.219:8123` 也跑着实例，**token 不通用** → 别连错 |
| **运行形态** | **Docker 形态**：宿主 `/opt/ha-config` = 容器 `/config`，伴随容器 `go2rtc`、`xiaoi-webhook` → **没有 Add-on/Supervisor**，第三方集成只能走 **custom component**（落 `custom_components/` 后重启容器）；**HACS 已装** |

从 PVE 侧探查比 CT 内 SSH 稳：`sshpass -p <PVE_ROOT> ssh root@192.0.2.10 'pct config 201; pct exec 201 -- docker ps'` —— root 密码在 `~/.hermes/.env` 的 `PVE_ROOT_PASSWORD`，不落聊天。**Docker 形态的升级是换镜像 tag，没有 HAOS 的一键回滚** → 大版本升级前先 `ha_backup_create`，并确认目标 tag 可回退。

**住户用电数据（国家电网电费曲线）的选型与装法** → `home-energy-audit`。

**CT <ID> 的 IP 走 DHCP 会漂**（已发生 `.172 → .175`）。凡是把 HA 地址**写死的消费者**（Caddy 反代、MCP 启动脚本）都会在漂移后变成静默故障 —— 修的时候 grep 旧 IP 把引用找全，别只改反代。

**有两台 HA，日志/配置必须对准 token 命中的那台**：token 打到 `192.0.2.10`（CT <ID> 的 `homeassistant` 容器）；NAS `.219` 上另有一个 `homeassistant-app-1`（`/config` 挂 `/volume1/docker/HAWork`），同一支 token 打它是 401。在 NAS 上 `docker exec homeassistant-app-1` 读到的日志/`/config` 是**另一台实例**，拿它当证据会把排查带偏 —— 正确实例的运行日志走 API `/api/error_log`（它才跟着 token 走）。

确认哪个实例认你的 token（token 从启动脚本读，**不落聊天**）：
```sh
TOKEN=$(grep -oP 'HOMEASSISTANT_TOKEN=\K\S+' /opt/mcp-start-ha.sh)
curl -s --noproxy '*' -H "Authorization: Bearer $TOKEN" http://<IP>:8123/api/config
```
返回 `location_name`/`version` = 就是它；401 = 不是这个实例。

## 1. MCP 调用规约

外层字段是 `arguments`，内层才是 `tool_name`/`tool_input`：
```json
{"name": "mcp__homeassistant__homeassistant_invoke_tool",
 "arguments": {"tool_name": "ha_get_overview", "tool_input": {…}}}
```
把 `tool_input` 放在外层会报 `calls must be a non-empty array of {name, arguments}` —— **见到这个错先查外层字段名**，别去怀疑 payload 内容或 MCP 服务本身。

后端 30 个工具，一律经 `homeassistant_invoke_tool` 分发。常用：`ha_get_overview`、`ha_search_entities`、`ha_config_set_dashboard`、`ha_config_get_dashboard`、`ha_get_dashboard_guide`、`ha_get_card_types`、`ha_config_set_automation|script|helper`、`ha_call_service`、`ha_backup_create`。

**schema 拿不准就发一个故意缺必填项的最小 payload** —— 报错会回吐完整签名（`ha_config_set_dashboard(url_path, config, title, icon, require_admin, show_in_sidebar)` 就是这么拿到的）。比翻文档快，也不会污染数据。

## 2. 已知 schema 陷阱

- `ha_config_set_dashboard`：**必填 `url_path`，没有 `dashboard_id` 参数**（那是返回值）。`url_path` **必须含连字符**，否则被拒。
- 写 `config` 是**整体替换**不是合并 → 一次把所有 view 放进同一个 payload，别分批指望叠加。
- `ha_get_overview` 的 `detail_level` 枚举是 `minimal | standard | full`（不接受其它值）。
- `ha_search_entities` 的过滤参数叫 **`domain_filter`** 不是 `domain`；`query` **必填且不能为空串**（空串返回 0 条）。要列某 domain 全部实体，就把 domain 名当 `query` 传，fuzzy 会匹配 entity_id。

## 3. 写完必读回

`ha_config_get_dashboard(url_path)` 读回，核对 view 数和实体 id。写接口返回 `config_updated: true` **只说明调用成功，不说明内容正确**。

访问地址：`http://192.0.2.10:8123/lovelace/<url_path>`。

## 4. 仪表盘设计流程

1. `ha_get_overview(detail_level="minimal")` 看规模与 domain 分布；**先看 `total_areas`**，为 0 就别用 `area` 卡片。
2. `ha_search_entities(query="<domain>", domain_filter="<domain>", limit=100)` 拿候选清单。
3. **过滤噪声** → 按 `references/entity-noise.md` 的判据挑真可控实体。
4. 按**功能**分 view（灯光 / 温控 / 窗帘 / 媒体…），用 `type: sections` + `grid` 分栏 + `tile` 卡片并挂 `features`（亮度、目标温度、播放/音量）。卡片结构与可用 features 以 `ha_get_dashboard_guide` / `ha_get_card_types` 为准，**别自己发明字段**。
5. 大 payload 先用 Python `json.dumps` 组装并 `json.loads` 自检（手写嵌套括号必错），再誊进调用。
6. 写入 → 读回验证 → 给出 `/lovelace/<path>` 地址。

改版请求按 the user's **字面范围**执行：他说「先做组织和信息、美观就行」就别自作主张塞自动化或传感器大盘 —— 他的自动化写在米家 App 里，HA 侧 `ha_deep_search(query="automation")` 常常是 0 条，看到 0 不代表要替他补。

## 5. 边界（MCP 没这些工具，别硬试）

- **没有 resources 安装工具** → Mushroom / Bubble / 3D 房间卡这类 custom card 装不了，得走 HACS 或直接改 HA 的 lovelace resources。
- **没有 area 管理工具** → 房间/分区只能在 HA UI 里建，建完 `area` 卡片才可用。
- 自动化/脚本/助手有 CRUD，但**改之前先 `ha_config_get_*` 读原配置**，别整段覆盖掉别人配好的东西。
- `ha_backup_create` 可以在大改前打个 HA 本地备份，作为回滚手段。
- **配置流只能走 REST**（`POST /api/config/config_entries/flow` → `POST .../flow/<id>`）：websocket 没有 `config_entries/start_flow`、没有 `config_entries/delete`、没有 `config/entities/get`，试一个浪费一轮。websocket 可用的是 `config_entries/get`、`manifest/get`（**必带 `integration`**）、`config/entity_registry/list`（**不接受 `domain` 参数**）、`camera/capabilities`、`camera/stream`。

## 6. MCP 报 502 时的判定顺序

1. 直接探 HA：`curl --noproxy '*' http://<IP>:8123/api/` → `API running.` = HA 活着。
2. HA 活着但 MCP 报 502 → 问题在 **MCP → HA 这一段**，读 `/opt/mcp-start-ha.sh` 的 `HOMEASSISTANT_URL` 比对当前真实 IP。
3. 改完 **kill 掉旧的 `ha-mcp` 进程**，下一次调用才会读新配置。
4. 再调一次工具，**返回真实实体数才算修好**。

`curl` 一律 `--noproxy '*'`，否则内网请求被本机代理劫持，会误判成服务不通。

## 7. 摄像头接入：MCP 加不了集成，走 HA REST

MCP 的 30 个工具**没有「加集成」能力**，CT <ID> 的 SSH 又经常不通 → 直接打 HA REST（token 就是 MCP 启动脚本里那支，不落聊天）。前置：**流源头先在 go2rtc/RTSP 层验证能拉通**，HA 只是消费端。

**选 `generic`，别选 `mjpeg`**：mjpeg 集成建出来的 camera `supported_features=0`，只有快照 —— 卡片写 `camera_view: "live"` 照样给你静态图；`generic` + `stream_source: rtsp://…` → `supported_features=2` 才是真流。

配置流（REST，通常两步）：
1. `POST /api/config/config_entries/flow {"handler":"generic"}` → `flow_id` + `data_schema`；
2. `POST /api/config/config_entries/flow/<flow_id>`，**顶层只放表单列出的键**（`stream_source`、`still_image_url`），高级项塞进 `advanced` **字典**（`{"framerate":2,"verify_ssl":false}`）—— 传 bool 或带未知键一律 400；
3. 常见第二步是 `step_id: user_confirm`（它正在试拉流）→ 再 POST `{"confirmed_ok": true}` 才 `create_entry`；
4. entity_id 由 title 自动拼（`192_168_100_219`、`_2`、`_3`）→ 按创建顺序对齐设备，卡片里用 `name` 覆盖显示名，entity_id 丑不影响用。

**流端点是 `/api/camera_proxy_stream/<eid>`（下划线）**；`/api/camera_proxy/stream/<eid>`（斜杠）本版恒 404 —— 这是源码里 `CameraMjpegStream.url` 的写法，快照才是 `/api/camera_proxy/<eid>`。该端点持续吐 `multipart/x-mixed-replace` 字节 = 端点活着，0 字节 = 只有快照；**但这只证明端点，不等于用户能看到视频** —— 前端 live 走的是另一条链，见 §8。

读回与映射：`config_entries/get` 返回的 `data`/`options` 是空壳，读不到配置 → 用 options flow 反查：`POST /api/config/config_entries/options/flow {"handler": entry_id}`，表单里的 `suggested_value`（`stream_source`）就是该 entry 接的哪路流。

止损：报 `single_instance_allowed` = 该集成已有实例，**改它别重建**；加错的集成别耗轮次删（websocket 无 `config_entries/delete`、REST `DELETE /api/config/config_entries/<id>` 404）→ 卡片不指向它即可，要清去 HA UI 删。

卡片：`{"type":"picture-entity","entity":"camera.xxx","camera_view":"live","name":"中文名"}`。MJPEG 走公网带宽粗（每路 Mbps 级），只放在监控 view 里，别铺到首页。

源头层（IP 漂移、转码配方、CPU 预算）见 `references/go2rtc-streams.md`。

设备整体离线（HA 报 unavailable、go2rtc 报错、App 显示离线）先走 `lan-offline-triage` 在路由侧定层：HA 侧只能确认症状，断在物理层/链路/应用层由路由的 ARP+DHCP+logread 回答；设备是有线还是 WiFi 先问清，有线设备别去查 AC 的 WiFi 客户端表。

云台（PTZ）/对讲这类「画面之外」的能力，先做协议层判定再答，别在集成层找按钮 —— 判据、四个已知缺口、实施顺序见 `references/camera-ptz-talkback.md`。

## 8. 「端点在流，用户仍只看到快照」= 编码不兼容，去源头转码

前端 live **不走 MJPEG 端点**，走 websocket：`camera/capabilities` → `frontend_stream_types`（本实例 `['hls','web_rtc']`），`camera/stream`（`format` 只收 `hls`）→ 返回 `/api/hls/<hash>/master_playlist.m3u8`。

判定链（从用户视角倒推，别停在端点测试）：
1. 拉 master（公网域名+端口，`curl --compressed`，否则拿到 gzip 乱码）看 `CODECS=`。
2. `hev1.*` = H265 → **Chrome 播不了 HLS，前端静默回退成快照**（「看的是快照」的标准根因）；`avc1.*` = H264 → 通用可播。
3. 修在源头不在 HA：go2rtc 每路加一条转码源 + options flow 把 entry 的 `stream_source` 切到 `*_h264` 流（同样会回 `user_confirm`，要再 POST `{"confirmed_ok": true}`）→ 配方见 `references/go2rtc-streams.md`。
4. 复验三件套：新 master 的 `CODECS="avc1..."`、子 playlist 有 `./segment/*.m4s`、公网域名+端口能拉到切片。**改完隔几秒再取 URL**，早了拿到的是旧 hash 的缓存。

两端都对才算修好：`camera_proxy_stream` 吐字节（HA 侧）+ `avc1` 的 HLS（前端侧）。只验前者会得出「明明在流」的错误结论。
