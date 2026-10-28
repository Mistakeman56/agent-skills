# 摄像头进阶能力：云台（PTZ）与对讲（two-way audio）

用户问「能不能把移动摄像头画面 / 语音麦克风弄进 HA」时，先按下面的判定顺序给出结论，再谈方案。核心原则：**能力先在协议层查清楚，别在 HA 集成层硬找按钮。**

## 现状对照（三台小米摄像头）

| HA 显示名 | 型号 | go2rtc 流名 |
|---|---|---|
| 室外摄像机4Pro | xiaomi.camera.cw701（三摄） | camera1 / camera1_h264 |
| 北院摄像头 | isa.camera.cw501 | camera2 / camera2_h264 |
| 星核监控 | chuangmi.camera.81ac1 | camera3 / camera3_h264 |

HA 里已有、可直接用的实体：`number.*_active_fav_area_*`（常看位置 0-64，跳预设）、`button.*_ptz_calibrate_*`（云台校准）、若干摄像机控制开关（人形追踪、夜视、声光报警等）。

## 判定顺序

1. **控制能力查 miot-spec 的「读写」位**：`web_extract https://home.miot-spec.com/spec/<model>`。三台的 `ptz-camera` 属性全部是 `R/N`（只读状态）→ **xiaomi_miot / 官方 Xiaomi Home 集成做不出云台方向键，方向控制不存在于 MIoT 属性层，别去集成里找**。同理，凡是「集成里怎么没有 XX 按钮」，先查 spec 读写位再下结论。
   - miot-spec 页面极长，web_extract 会截断存盘 → 用 search_files 在缓存文件里 grep `ptz|云台|读写`，别整页重拉。
2. **对讲能力看 go2rtc probe**：`GET :1984/api/streams`，producer 的 `medias` 含 `audio, sendonly, OPUS/…` = 摄像头反向收音通道在（本环境三台均为 cs2+tcp，都有）。协议层通了才谈前端。
3. **HA 原生卡片没有麦克风按钮**（官方两路音频还在 roadmap，前端 talk UI 未落地）→ 对讲必须走 HACS 自定义卡。

## 已知缺口（开工前必须知道的四个坑）

1. **go2rtc CS2 上行音频有写包 bug，上游未合入**：`pkg/xiaomi/miss/cs2/conn.go` 的 `WritePacket` 里第二个 `copy` 拷了 `hdr` 而不是 `payload` → 对讲发过去是巨大噪音。修法是一行代码，需自己 build 镜像替换 NAS 上的 `alexxit/go2rtc:latest`。
2. **go2rtc 没有 PTZ 架构**（上游 enhancement 挂着未合）。协议本身已知：MISS 通道命令 `0x112` + `{"operation":1左 2右 3上 4下}`（社区在部分型号实测通过；**本环境三台是否认此命令未验证**）。老 dafang/tutk 型号另有 `dafangRaw(0xff2404,…)` 系列命令（在 `pkg/xiaomi/miss/client.go` 注释里）：源码注释的左右方向是反的、电机收到命令会一直转必须显式发 stop、speed 取 1-9。
3. **浏览器麦克风强制 HTTPS**：http 页面拿不到 mic；且 https 页面里连 `ws://` 会被当混合内容拦截 → go2rtc 也必须挂一条 Caddy HTTPS 反代（泛域名证书现成，照 home-public-services 的反代段写）。WebRTC 的 UDP 8555 只在局域网直连可用，外网要另开端口映射，第一期不做。
4. **advanced-camera-card 的两路音频只支持 Frigate 实体** → 本环境选 intercom-camera-card 或 AlexxIT webrtc-camera（可请求 `media: video,audio,microphone`）。

## 兜底方案（今天就能落地，零风险）

常看位置跳转：三台的 `active_fav_area` number 实体已在 HA，米家 App 里存好机位 → HA 做按钮跳转。哪台摄像头不认 PTZ 命令，就退回这个方案。

## 验证方法（不用人盯）

- **云台命令是否生效**：发命令前后各抓一次 `GET :1984/api/frame.jpeg?src=<name>`，做像素差对比 → 自动判定方向与幅度。命令→画面可见动作有约 1-2 秒延迟，抓帧要留间隔。
- **对讲**：端到端必须真人按住说话试听（agent 替代不了），之前的链路验证只到「反向通道存在 + 噪音 bug 已修」。

## 实施顺序（若开工，一次做完）

1. NAS 上 build 补丁版 go2rtc（对讲写包修复 + PTZ API）→ 替换容器（看家流断几秒）→ 补丁文件留在 NAS，上游升级后要重打。
2. Caddy 加 go2rtc HTTPS 反代并 reload。
3. HA 侧纯前端：HACS 装卡 + 仪表盘方向键/麦克风卡片（卡片直接 fetch go2rtc API，**不改 HA 后端 configuration.yaml、不重启 HA**）。
4. 验证：云台抓帧自动验 → 对讲真人试听收尾。
