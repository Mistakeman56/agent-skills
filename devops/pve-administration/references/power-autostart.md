# PVE 省电与自启

## 1. 功耗测量

- **RAPL 只能在宿主上读**：`ssh root@192.0.2.10`（密码在 `~/.hermes/.env` 的 `PVE_ROOT_PASSWORD`）→ 采样两次 `cat /sys/class/powercap/intel-rapl:*/energy_uj`，`ΔE/Δt` 求瓦数；**LXC 里 `Permission denied`**（unprivileged 设备映射），容器内测不出 CPU 功耗。
- 报告要区分**宿主整机**与 **CPU 部分**：RAPL 只算 package，主板/盘/风扇另加约 10~15W。
- 非 x86 设备（路由、AC/AP、NAS）没有计数器 → 用标称 + 第三方实测，标 ±15%。审计口径与对账见 `home-energy-audit`。

## 2. `intel_idle.max_cstate=1`（当前最大的一块浪费）

- 宿主 cmdline 带 `intel_idle.max_cstate=1` → C-state 被锁在浅层，**空载也恒定 ~53.7W CPU**（60s 采样两次 53.70/53.71W，复现性极高，与负载无关）。
- 去掉后预期回到 ~40W 档，按 24h 计算是每元省电里性价比最高的一档。
- 改法：`/etc/default/grub` 的 `GRUB_CMDLINE_LINUX_DEFAULT` 删掉该参数 → `update-grub` → **重启生效**。
- **重启 = 3~5 分钟全家服务中断**，属需用户点头的动作；**未重启前不要报「省电已生效」**，写成待办即可。

## 3. CT 开机自启（onboot）

- 查：`pct config <id>` 看 `onboot:`；改：`pct set <id> --onboot 0|1`（改完再 `pct config` 回读）。
- 当前白名单：**200 mcp-server / 201 homeassistant / 202 hermes-agent = 1**；**100 / 300 / 310 = 0**。
- **关掉自启的 CT 重启后不会自己起来** → 记住手动起的清单：**300 talent-app（公网 DNAT 5001）**、**310 miloco**。改白名单时顺手把清单带给用户，否则故障会被当成服务坏了。

## 4. 通电自启 / 定时开机：先分清哪一半能远程做

| 目标 | 能否远程 | 做法 |
|---|---|---|
| 定时**关机** | ✅ 能 | OS 层 cron/systemd timer 调 `shutdown -h now` |
| **通电自启**（AC Power Loss → Power On）| ❌ 不能 | **BIOS**，机器无 IPMI/BMC |
| **WOL 唤醒**（作定时开机）| ⚠️ 半能 | OS 层开能力 + 路由器发包；**BIOS 的 Power On By PCI-E 仍需人按 Del** |
| BIOS RTC 定时开机 | ❌ 不能 | 同上 |

本机主板 `TS 12-13th ITX D4L`（BIOS 5.27，**无 IPMI/BMC**）→ BIOS 项一律**人到机器前开机按 Del**，网络侧做不了，别在这上面空转。

**WOL 现状与持久化**：网卡 `nic0` 支持 `Wake-on: pumbg`；`ethtool -s nic0 wol g` 是**运行时设置，重启后回落**，持久化二选一：systemd unit（安全，不动网络栈）或 `/etc/network/interfaces` 的 `post-up`（**改前备份，要 reload 网络**）。路由器侧 `etherwake` 已装（iStoreOS `/usr/bin/etherwake`），MAC `00:00:00:00:00:00`。

## 5. 定时开关机的收益与风险（先算再挂）

`省下(元/月) = 整机W × 可关小时 × 30 ÷ 1000 × 单价` —— 68W × 8h × 30 ≈ 16 度/月，不到 10 元量级。

对照代价再决定：服务断线（HA 摄像头停录、MCP/Hermes 下线）、冷启动 3~5 分钟、每日开关对盘的损耗、排障变量增多。

**顺序铁律：先验证唤醒，再挂关机。** 未验证 `Wake on PCI-E`/RTC 就挂 `00:00 shutdown`，早上唤醒失败 = 全家断网直到人工干预。正确顺序：① BIOS 设 `AC Power Loss = Power On` + `Wake on PCI-E = Enabled` → ② 路由器 `etherwake` 实测唤醒成功 → ③ 才挂定时关机 cron，并把 WOL 持久化。

**收益 < 10 元/月且要断服务的改动，直接不做。**

## 6. 电源事件取证

- `last reboot` 看是否有异常 `crash`/`down` 记录；结合日志时间点区分**计划内重启**与**掉电**。
- 多台设备同时在某时刻中断 → 先查供电侧（空开/插排/市电），别先怀疑软件。
- 反复非正常关机 → 上 UPS（200VA 级即可覆盖 ITX 主机 + 外设）。
