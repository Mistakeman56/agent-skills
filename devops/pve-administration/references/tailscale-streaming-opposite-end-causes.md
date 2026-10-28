# Tailscale 串流卡顿的对端原因：下载抢带宽 + 公网中转（2026-08-18 收尾实锤）

## 场景
本地链路全绿（0% 丢包、4.4Mbps+ 无压力、direct 20ms、MTU 已还原 1280）但 Moonlight
串流仍卡（只有 2.3Mbps，720p 勉强、1080p 不行）。继续在本地 MTU/Clash/Tailscale 配置上
反复调整是浪费时间 —— 本次绕了一大圈后的真相在对端。

## 真相 1：对端在跑 Steam 下载 = 串流被抢带宽
用户最终确认：**mydevice 电脑当时正在 Steam 下载游戏，上行带宽被占满**。
- "以前 1080p60 流畅、最近变卡" 的真正原因就是这个，与本地任何配置无关。
- 对端暂停/限速下载后，720p 恢复流畅；1080p 待对端不下载时再验证。

**排查教训（顺序很重要）：**
1. 串流卡顿排查，**第一步先问对端"你电脑现在在跑什么下载/上传吗？"**
   （Steam / 网盘同步 / 云备份 / BT），比任何 MTU、DERP、Clash 分析都快。
2. 本地网络全绿 ≠ 串流不卡 —— 瓶颈可以完全在对端（Moonlight 串流是对端上行 → 你下行，
   对端上行带宽被抢 = 你看到卡）。

## 真相 2：Moonlight 可能配了公网中转而非 Tailscale 直连
抓包（路由器 conntrack / tcpdump）发现串流设备在连 `203.0.113.1:80`
（阿里云香港）且 `SYN_SENT [UNREPLIED]` —— Moonlight 客户端配的可能是**公网中转/DDNS
地址**，而不是 Tailscale 虚拟 IP（`mydevice.tail879c26.ts.net` → 100.64.0.1）。
- 中转服务器失效/限速时串流就卡；此时 Tailscale 直连本身是好的（20ms 0% 丢包）。
- **对端无下载仍卡时，检查 Moonlight 主机地址是否为 Tailscale 域名/IP**，改回
  Tailscale 直连（20ms）避开中转。
- 识别方法：`tailscale status` 里 peer 显示 direct + 低延迟，但串流流量却在连
  非 Tailscale IP（阿里云/中转商 IP），且该连接 SYN_SENT 无响应或响应慢。

## 结论
- 本地链路全绿 → 优先怀疑对端应用层：下载占用、Sunshine 码率设置、机器性能。
- 先问"对端在跑什么"，再检查 Moonlight 连接目标是不是 Tailscale 地址。
- 相关方法论：`tailscale-streaming-lag-diagnosis.md`（本地路径诊断）、
  `tailscale-mtu-over-lowering-pitfall.md`（MTU 反面教训）。
