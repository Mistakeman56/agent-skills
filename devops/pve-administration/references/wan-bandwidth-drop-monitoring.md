# 带宽波动监控 v2：延迟正常 ≠ 带宽正常（2026-08-19 实测教训）

## 核心教训

**只监控延迟/丢包/PPPoE uptime 会漏掉真正的病根。** 路由器 netmon.sh v1 跑 6 小时显示"零事件"（uptime 稳定增长、ping 0% 丢包、延迟稳定 20ms），但用户持续报"波动极大、打游戏一卡一卡"。加入**带宽采样**后立刻抓到真相：

```
[23:10:46] 0 MB/s    ← 完全没速度
[23:10:51] 8 MB/s
[23:10:59] 5 MB/s
[23:11:06] 0 MB/s    ← 又断
[23:11:13] 0 MB/s
[23:11:20] 1 MB/s
```

**下载带宽在 0–16MB/s 剧烈跳动，多次掉到 0，但链路层面（ping/延迟/PPPoE）完全正常。** 这就是"延迟正常但游戏卡顿"的典型真凶：带宽骤降 → 游戏 UDP 包被卡住 → 卡顿/掉线。

## 为什么 v1 漏掉了

- ping/延迟只反映**链路连通性**，不反映**带宽可用性**
- 运营商下行限速/拥塞、光猫吞吐不稳定 = 带宽层面问题，ping 完全看不出来
- 带宽采样必须用**大文件下载测速**（华为云 `ls-lR.gz` 38MB），小文件（Release 几 KB）测不准

## v2 监控脚本（部署中）

完整脚本：`scripts/netmon.sh`，部署到路由器 `/usr/bin/netmon.sh` + cron `*/2 * * * *`。

v2 相对 v1 的四个关键升级：
1. **带宽采样**：每轮下载华为云大文件 4s，记录 `bw=X MB/s`；<2MB/s 记 `BANDWIDTH_DROP` 事件
2. **光猫监测**：ping 192.0.2.10（桥接光猫管理 IP），`onu=yes/no`；失联记 `ONU_LOST`
3. **持久目录**：数据存 `/etc/netmon/`（v1 存 /tmp，路由器重启即清，掉线现场随重启消失）
4. **掉线现场留痕**：有事件时 logread（排除 dnsmasq 刷屏）+ 接口状态写入 `/etc/netmon/crash_YYYYMMDD.log`

## 掉线定位决策表

| 事件 | 含义 | 指向 |
|------|------|------|
| `PPPoE_RECONNECT` | 掉线重连 | 光猫/运营商线路断。**先问"谁手动重启过"**——用户手动重启路由器也会触发此事件 |
| `PACKET_LOSS >0%` | 线路抖动 | 光功率/OLT |
| `BANDWIDTH_DROP` | **带宽暴跌链路正常** | 运营商下行限速/光猫吞吐不稳 |
| `ONU_LOST` | 光猫失联 | 光猫死机/断电（"拔光猫重启才好"= 实锤光猫侧） |

## 排查顺序建议（用户偏好：action-first）

用户报"又卡了/又掉线"时：
1. 先看 `/etc/netmon/netmon.log` 最近几行——**如果恰好有 BANDWIDTH_DROP/PPPoE_RECONNECT/ONU_LOST 事件且时间吻合，直接定位**
2. 没有事件 → 现场跑带宽采样 `curl -s --noproxy '*' -m 4 -o /dev/null -w '%{speed_download}' http://mirrors.huaweicloud.com/ubuntu/ls-lR.gz` 连续 4-6 次
3. 带宽稳定 → 查游戏 UDP 连接/代理劫持（`references/openclash-game-direct-rules.md`）

## 坑

- **用户手动重启路由器 = uptime 归零 + IP 变化**，伪装成 PPPoE_RECONNECT——查监控前先问"你重启过吗"
- **小文件测速不准**：用 `ls-lR.gz`（38MB）级大文件，几 KB 的 Release 文件测出的是握手速度
- 路由器系统日志被 dnsmasq `log-queries=extra` 刷屏，抓现场时先 `grep -viE 'dnsmasq|ilinkai|weixin'`
- 光猫桥接模式下管理 IP 常见 192.0.2.10（VSOL V2901Q），HTTP 可能 000 但 ping 通
