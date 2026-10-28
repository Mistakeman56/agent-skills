# 小米摄像头 / NAS 监控（the user's home）—— 结论：不折腾

## ★ 用户决策（2026-10-04，别再提）
**“我本来就用米家看，我也不用这个监控中心，这个不用管。”**
→ 家庭监控只用**米家 APP**。**不要提议买海康/监控中心/NVR**；海康那套已评估并因“贵 + 对 10~20m 院子过配”而被否。
→ 以后只在用户主动问时再谈。

## 现有设备（3 台，均为小米生态老款，无 ONVIF）
| 流 | IP | 型号 | 状态 |
|---|---|---|---|
| camera1 | 192.0.2.10 | xiaomi.camera.cw701 | 空闲，无报错 |
| camera2 | 192.0.2.10 | isa.camera.cw501 | ⚠️ 被拉流时 i/o timeout |
| camera3 | 192.0.2.10 | chuangmi.camera.81ac1（2016 老机）| ✅ 能推 H265，但报 pop buffer is full |

## go2rtc 桥（NAS 上，2026-10-02 搭）
- 容器 `alexxit_go2rtc-1`，配置 `/volume1/docker/alexxit_go2rtc-1/config/go2rtc.yaml`
- 用 `xiaomi://<uid>:cn@<ip>?did=<did>&model=<model>` 把私有协议翻成 RTSP
- 另配了 `cameraN_h264`（ffmpeg 转 H264/1280宽）给浏览器用，因为小米出的多是 H265
- **状态：用户不用，保留不维护**

## 踩过的判据坑
- **⚠️ 小米摄像头不回 ICMP** → ping 不通 ≠ 掉线。**看 go2rtc 的 `/api/streams` 才是真相**：有 `id`/`remote_addr` = 活着；只有 `url` = 配置了但没在跑（go2rtc 是按需拉流的，没人看就不拉）
- go2rtc 的 `stream=X` 报错只出现在**有消费者拉流时**；消费者断开报错就停 → 不能用“最近报错数=0”反推正常

## 绿联 NAS 监控中心（已调研，暂不用）
- DXP4800 官方支持，但**最大 AI 检测任务数 = 3**（人形/宠物/车辆各占1，人脸占3）；支持 8 路接入
- 只吃标准 ONVIF/RTSP → **小米私有协议不兼容**，必须靠 go2rtc 桥（社区反馉不稳）
- 海康选型与避坑详见 `consumer-tech-briefing/references/hikvision-nas-camera-2026.md`
