# go2rtc 流源头层（HA 的上游）

HA 只是消费端：拉不到流、某几路超时、只有快照，先在这一层定位，再动 HA。

## 本环境拓扑
- 容器 `alexxit_go2rtc-1` on NAS `192.0.2.10`；配置容器内 `/config/go2rtc.yaml`（宿主 `/volume1/docker/alexxit_go2rtc-1/config`）
- 端口：`1984` = WebUI + API；`8554` = RTSP（以 `api` 返回的 `rtsp.listen` 为准，**别拿 8888 当 RTSP**）
- 小米摄像头 `xiaomi://<uid>:cn@<ip>?did=<did>&model=<model>` = **本地 P2P，不过米家云**；账号密文在 `xiaomi:` 段，不落聊天

## 接口速查
- `GET :1984/api/streams` → 每路 producers/consumers/remote_addr/error：判活、判错、看谁在消费都在这
- `GET :1984/api/frame.jpeg?src=<name>` → 单帧（对比/哈希/验证出图）
- `GET :1984/api/stream.mjpeg?src=<name>` → MJPEG
- `ffprobe -rtsp_transport tcp rtsp://<nas>:8554/<name>` → codec / 分辨率（转码后验 `codec_name=h264`）

## 配置里的摄像头 IP 是 DHCP 派的，会漂
症状：几路报 `read udp ... i/o timeout`（IP 漂了但还没被占），或报 **`401 Unauthorized`（源 IP 已指到别的设备，对方拒认证——401 先查 IP 指向，别先怀疑密码）**，另几路好好的（别先怀疑协议）。**但设备整体不在网（ARP 全零、ping 不通、全网扫不到 MAC）不是 IP 漂移 —— 走 `lan-offline-triage` 物理层定性，别在这里改来改去。**
1. 取旧 IP：配置文件或 `api/streams` 里各路 url 的 `@<ip>`。
2. 找新 IP：路由器 `/tmp/dhcp.leases` 按 hostname 对齐（小米设备主机名带型号，如 `chuangmi_camera_81ac1`、`isa_camera_cw501`）；`ip neigh` 里该旧 IP 显示 `FAILED` = 确实已无设备。
3. 改 `go2rtc.yaml` → `docker restart alexxit_go2rtc-1` → 逐路 `frame.jpeg` 出字节才算修好。
根治：给摄像头钉静态 DHCP 租约，别每次靠救火。

## H265 源流必须转码，否则浏览器只见快照
```yaml
streams:
  camera1:
    - xiaomi://...
  camera1_h264:                        # 新增一路，名字自定
    - ffmpeg:camera1#video=h264#width=1280#audio=opus
```
- `ffmpeg:<同文件里的流名>` 可直接引用另一路，不必重写完整源
- **`#width=` 降分辨率是控 CPU 的主要手段**；`#hardware` 视平台而定，软件编码更通用
- **先看资源再铺开**：`uptime` + `top` + `ps aux | grep ffmpeg`。本机 4 核，3 路 720p 约占 1.3 核、load ~2/4、内存 81% —— 能跑但没余量，加路数或提分辨率前先评估
- 改配置先 `cp go2rtc.yaml go2rtc.yaml.bak.<tag>`；**追加用 base64 管道**（`echo <b64> | base64 -d >> /config/go2rtc.yaml`），嵌套 `docker exec … sh -c 'cat <<EOF'` 必被外层 shell 吃掉
- 改完 restart，逐路 ffprobe 确认 `codec_name=h264`，再让 HA 把 `stream_source` 切过来（见 SKILL.md §8）
