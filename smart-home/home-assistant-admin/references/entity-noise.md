# the user 家的实体噪声判据（建仪表盘前先读）

规模参考：约 1630 实体 / 22 domain / **0 area**。domain 分布：sensor 325、switch 281、event 244、button 212、select 152、number 141、text 93、light 86、notify 59、binary_sensor 17、media_player 4、cover 3、climate 2、device_tracker 2、person/zone/sun/weather/todo/tts/conversation 各 1。

## 噪声从哪来

`xiaomi_home` 集成会把每台设备的**全部属性**都暴露成实体，绝大多数既不可操控也不该上仪表盘：

- **指示灯**：`* 指示灯`、`* 全部开关指示灯状态`、`* 左/中/右键指示灯状态` —— light 域 86 条里约 70 条是这类，还带一批 friendly_name 为空的 unavailable 重复体。
- **设备内部参数**：`* 特色功能 内部电压`、`* 自定义补充 设备的按键埋点（插件不用）`、`* 系统参数 内机参数`。
- **服务型实体**：`button.*`（自检/格式化/静音切换）、`notify.*`（亮度±、色温±）不该当卡片。
- **协议字段**：`event` 244 条、`select`/`number`/`text` 里的裸参数（围栏坐标、JPEG 配置串、固件列表）。

## 挑实体时逐条过的判据

1. friendly_name 含「指示灯 / 埋点 / 内部 / 参数 / 插件不用」 → 剔除。
2. domain 是 `event` / `notify` / `text` → 默认不上仪表盘。
3. `button` 只有明确的常用动作才留。
4. 同一个物理开关在 `light` 和 `switch` 下会有多个伴生实体 → 只留真正控制照明/设备的那个。
5. 状态 `unavailable` 的实体可以留但别当主卡片（先确认设备是不是离线）。
6. **数量反差是信号**：86 个 light 只有 15 个是真灯 → 遇到某 domain 实体异常多，先抽样看名字再上卡片。

## 筛出来的真可控实体（可直接复用）

**灯（15）**
- 主灯：`light.yeelink_cn_827125644_ceil38_s_2_light`（吸顶主灯）、`light.yeelink_cn_1136134697_wy0a01_s_2_light`、`light.yeelink_cn_1136134703_wy0a01_s_2_light`（磁吸灯 ×2）
- 群组：`light.mijia_cn_group_1979220889048604672_group3_s_2_light`（射灯）、`light.mijia_cn_group_2018687421600759808_group3_s_2_light`（筒灯）
- 米家筒灯2 蓝牙Mesh ×9：`light.xiaomi_cn_{2021840043,2021840053,2021847227,2021859859,2021859864,2021860536,2022375256,2022449924,2022515757}_btlm2_s_2_light`
- `light.xiaomi_cn_2081462019_btlm2_s_2_light`（筒灯2）

**房间灯控开关（switch 域，约 26 个）—— 真正控灯的是这组**
命名规律 `switch.<设备id>_on_p_<通道>_1`，`<设备id>` 后缀 `_w1/_w2/_w3` 是几路键；light 域里的同名开关全是伴生指示灯（见上）。按楼层分好区直接可用：
- ⚡ 总控：`xiaomi_cn_2021067696_w1_p2` 灯光总闸、`xiaomi_cn_888910528_w1_p2` 筒灯总（红卡置顶）
- 🏠 客厅 `2020879703_w3`：p2 大灯 / p3 客厅筒灯 / p4 饭桌筒灯
- 🍳 一楼：厨房 `888466709_w1_p2`；卫生间 `2000304181_w3` p2 排气扇 / p3 灯 / p4 门口吊灯；客房 `2021723733_w1_p2`
- 🛁 二楼：三开 `946243288_w3` p2 小吊灯 / p3 筒灯 / p4 灯带；卫生间 `2000438087_w3` p2 排气扇 / p3 灯带 / p4 灯
- 🪜 三楼：楼梯 `2042692296_w2` p2 吊灯 / p3 灯带；三楼 `2042769877_w2` p2 筒灯 / p3 吊灯
- 🛏 主卧·小屋：主卧大灯 `2042811252_w2_p3`；小屋 `2042776131_w2` p2 吊灯 / p3 右键
- 🌳 院子：`2000452006_w3` p2 氛围灯 / p3 院子灯 / p4 七星灯，加 `giot_cn_2079099780_v9icm_on_p_2_1`（院子灯·吉屋）
- 智能灯的物理火线开关：`2021421100_w2` p2 吸顶灯 / p3 射灯（橙卡，跟对应智能灯放一起）
- 一次拿全：`ha_eval_template` 遍历 `states.switch` 过滤 `'_on_' in entity_id`，输出 `entity_id :: name :: state`。

**空调（2）**：`climate.xiaomi_cn_898889695_h21h00`（上出风Pro 1.5匹）、`climate.xiaomi_cn_898663441_h21h00`

**窗帘（3）**：`cover.linp_cn_2077425766_ec1db_s_2_curtain`（一楼）、`cover.linp_cn_2079455069_ec1db_s_2_curtain`（二楼）、`cover.linp_cn_2077414306_ec1db_s_2_curtain`

**媒体（4）**：`media_player.xiaomi_cn_981192128_oh2p`（智能音箱 Pro）、`media_player.xiaomi_cn_979931026_oh2`（橙）、`media_player.xiaomi_cn_979939218_oh2`（蓝）、`media_player.xiaomi_cn_903481888_rmonh`（显示器/电视）

**适合做徽章**：`person.cui_yi_ming`、`weather.forecast_wo_de_jia`、`sun.sun`

## 待补的两块

- **摄像头已接入**：3 路小米头走 NAS 上 go2rtc（`xiaomi://` 本地 P2P，不走米家云）→ HA `generic` 集成 → `camera.192_168_100_219`（室外4Pro）/ `_2`（北院）/ `_3`（星核）；接入步骤与流端点见 SKILL.md §7。列表里另有 3 个早前 `mjpeg` 集成的遗留实体（`camera.shi_wai_she_xiang_ji_4pro` 等，无流只有快照、脚本删不掉）—— **卡片别指向它们**。
- **没有 area**（`total_areas: 0`）：房间归属目前只能靠开关名反推 —— 客厅、厨房、一楼卫生间、二楼卫生间、三楼楼梯、客房、小屋、院子、北院、灯光总闸（别墅 1~3 楼）。在 HA UI 建好 area 后，`area` 卡片和按房间分组才可用。
