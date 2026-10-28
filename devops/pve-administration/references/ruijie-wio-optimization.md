# 锐捷 Reyee WIO 深优化：正确入口与实测结果

## 入口链路（eWeb）
`WLAN Optimization` → `Network Optimization` 页签 → **`Advanced Settings`** → 卡片底部 **w160 的 `OK` 按钮** = 真正的启动入口（不是页面上那个 `Cancel Optimization`）。

点 OK 会弹确认框 **Tips**："During optimization, the APs may switch channels and collect data, which may result in temporary disconnection..." → 框内 **`OK`** 才真正开跑。

## 参数位置
- 模式单选：`radio value=0` = Deep optimization（默认选中）；`value=1` = Quick
- `Scan time` / `Roaming Sensitivity` / `Transmit Power` 三个开关默认全开、值 Default，**不要动**
- 2.4G/5G 的 `Selected channels` 是 **chip 样式**（不是原生 checkbox），`CH.x` 文本节点向上找 3 层父元素的 `el-tag` 判断选中态

## 实测（2026-10-04 00:21:22，Deep，耗时 6分34秒）
| AP | 5G 信道 前→后 | 干扰 前→后 | 漫游灵敏度 |
|---|---|---|---|
| 三楼AP `G1RUC0T233359` | 36 → **149** | 9% → **1%** | 20 → 90 |
| 一楼AP `G1RUC0T251590` | 36 → **52** | 5% → **1%** | 20 → 84 |
| 二楼AP `G1RUC0T250109` | 36（不变）| 1% → 1% | 20 → 90 |

总计：优化 3 台 AP、干扰降 60.17%、体验 +84.81%。**结果：三台从全挤 ch36 变成 36/52/149 三个不同 80MHz 信道。**

## ✅ 用户验证（2026-10-04）—— 根因确认
跑完 WIO 后用户原话：**"现在我感觉不卡了，你的操作应该是有效果的。抖音B站都不卡了"**
→ **根因确认 = 5G 三台 AP 全挤 `ch36` 导致的空口争用**，拆成 `36/52/149` 后立即恢复正常。

### ★★ 重要教训（本次差点判错）
**空口争用导致的视频卡顿，在 ping 的 min/avg/max 上看不出来。**
本次现象：`min=2.7ms`（链路优秀）但 `avg 39ms / max 112ms`，我一度判为"Apple 省电机制、非故障"并**怀疑是手机端问题** —— 但实际就是无线信道规划问题，拆信道后立刻好了。
**正确判据**：厂商 WIO 的「干扰百分比」+ **用户实际刷视频体感**；**不要**用 ping 统计值否定信道规划结论。
**正确顺序**：先拆信道（治本且可验证），ping 只当参考。

## 坑
1. **WIO 会把 AP 放到 DFS 雷达信道（本例一楼AP → ch52）。** 虽然 5G 白名单里 52/56/60/64 显示为未选，WIO 仍分配了 ch52 → **不要相信 chip 的选中态就等于生效白名单**；要么在跑之前用 Advanced Settings 明确重设，要么跑完检查并手工拉回非 DFS（36-48 / 149-161）。DFS 信道的风险：AP 检测到雷达必须让道 → 突发断流。
2. **【重要】ping 抖动 ≠ 无线故障，但 ping 漂亮也 ≠ 体验好。** iPhone/iPad 的 WiFi 省电（DTIM 唤醒）天然产生「min 2-3ms 但周期性 ~100ms 尖峰」，**别拿 avg/max 判故障**（会误报「无线劣化」）。
   反过来更坑：**`min` 只有 2.5ms（”链路优秀“）时用户照样喊卡。** ping 只能证明「链路通」，**不能证明「体验好」** —— 别用它收束结论。
   **判视频卡顿的权威判据 = AC 里该终端的 `Signal Quality`(dBm) + `Negotiation Rate`**（AP 详情页客户端表 / 拓扑页节点面板都能读到）：
   | 同 AP 的终端 | Signal | 协商速率 | 体感 |
   |---|---|---|---|
   | iPad | -68 dBm | 1201M | 正常 |
   | 小米电视 | -58 dBm | 1080M | 正常 |
   | 投诉卡顿的 iPhone | **-82 dBm** | **648M** | 卡 |
   **5G 低于约 -75dBm、且协商速率明显低于同 AP 其他终端 → 是终端位置/漫游粘滞，不是网络配置。**
   处理顺序：先让用户关一次 WiFi 重连（强制重选 AP）；仍弱再问在哪个楼层/房间，查那层覆盖或补点。
   **别为此改无线参数或重跑 WIO —— 配置没问题。**
3. **优化期间浏览器 CDP 会话会被打断**（页签回 `about:blank`、登录态丢失）。监控优先走路由器侧 ping，别死磕浏览器轮询。
4. **登录态恢复流程**（每次断线都要重来）：`browser_vault_fill` 前必须先给 `#password` 设 `autocomplete=current-password`，并勾 `.read-agreement`，否则 fill 不进。
5. 跑完 WIO 后 `Client Association` / `Clients` 页可直接查「设备 → 频段 → 挂在哪台 AP」；`Clients` 表是虚拟滚动只渲染 ~10 行，**必须用 `placeholder="Search by IP/MAC/Username"` 的输入框过滤**，且要用原生 value setter 派发 `input` 事件才生效。

## 排查视频/App 卡顿的正确顺序
1. **规则**：抖音系域名是否被送去代理 —— `douyin.com` 之外必须查 `snssdk`/`pstatp`/`byteimg`/`bytedance`（`rule-provider` 里的域名 grep `/rules` 抓不到，要翻 `/etc/openclash/rule_provider/`）。
   共用规则集（`RuleSet TikTok`、`Bahamut` 这类）会抓走国内 App 与证书域名 → `references/openclash-douyin-tiktok-ruleset.md`、`references/openclash-ocsp-ruleset-fix.md`。
2. **出口**：WAN 实时吞吐（`/sys/class/net/pppoe-wan/statistics/` 采两段算差值）+ SQM 队列（`tc -s qdisc show`，看 `pk_delay`/`drops`/`overlimits`）。
   **别凭「NAS 在跑 BT」就断言上传被占满 —— 实测才 4Mbps / 90Mbps，队列 `pk_delay` 1.74ms 无排队。**
3. **无线（最常被跳过、也最常是真凶）**：进 AC 读该终端的 `Signal Quality`(dBm) + `Negotiation Rate`，与同 AP 其他终端横向对比 —— 判据表见上面「坑 2」。
4. 前三步全绿才动无线参数，动完用同一组测试对比。

### ⚠️ 动 WIO 之前必须先确认「真的需要动」
怀疑「信道被改回去了」时，**先取证再动手**：
- `WLAN Optimization` 页的 **`Completion time`** = 最后一次优化的时间（没变 = 没人重跑过）
- AP 详情页的实时 **`Channel`**（`Devices` → 该 AP → 看各频段 Channel）

**两个都正常就别跑 WIO** —— 深优化 680s、全屋无线断 6~11 分钟，为一个不存在的信道问题折腾是纯损失。
