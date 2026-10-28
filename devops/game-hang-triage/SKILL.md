---
name: game-hang-triage
description: 'Use when 游戏卡住/冻结/黑屏/失去响应。先按 GPU-DXGI 层定性，再恢复对局。'
---

# 游戏卡死 / 冻结排查（定性 → 恢复 → 防复发）

场景：用户说「游戏卡住了 / 画面冻住 / 点不动」，往往正打着。顺序是**先拿证据定层，再动手恢复**；
用户的诉求是回到对局，不是重装驱动或重启电脑。

## 1. 确认真卡死，还是只是没在前台
- 窗口 hung 用 `IsHungAppWindow(hwnd)` 在 console session（Windows-MCP 的 PowerShell）里查。
  走 ssh 的会话看不到窗口（`MainWindowHandle` 全 0、`GetForegroundWindow()`=0、`.Responding` 恒 True），
  别拿它当「进程没卡」的证据。
- 同时看 GPU：`nvidia-smi --query-gpu=utilization.gpu,memory.used,temperature.gpu,power.draw --format=csv`。
  **显存已占住但 util 个位数、功耗贴近待机 = 进程活着但渲染循环死了**（不是没加载完、也不是网络）。

## 2. 读游戏自己的日志（最快拿到硬证据）
LoL（WeGame 国服）路径：`D:\WeGameApps\英雄联盟\Game\Logs\GameLogs\<session 时间戳>/`
- `*_r3dlog.txt` — 渲染/流程日志。**最后一行的时间戳 ≈ 卡死时刻**，之后不再写入即死循环。
- `*_netlog.txt` — 每秒一行；列序：`时间,地址,incoming,outgoing,app_ctos,app_stoc,loss,sent,ping,variance,reliable_delayed,unreliable_delayed,app_update_delayed,critical_section,latency_in_window,loss%_in_window,jitter_in_window,overall_min,overall_max,window_min,window_max,latency_samples,jitter_samples,reconnect`。
  即**第 7 列 = 丢包、第 9 列 = ping**（实测 `...,0,5515,20,0,...` = 0 丢包 / 20ms）；
  地址列是 `X.X.X.X` 脱敏，别指望从 netlog 拿游戏服 IP 去 ping。

判据：
- `DXGI_ERROR_INVALID_CALL` 洪水（每秒上百条），前一行常有 `X3D: Focus Lost` → **GPU/叠加层问题，窗口失焦触发**。
- netlog 的 `ping` 稳定、`loss` 0、`*_delayed` 0 → 明确告诉用户「不是网络」，并用数据背书，别只是附和。
- `Start Main Loop` 之后就没后续 → 卡在渲染，而不是卡在加载。

## 3. 「今天才坏」的对比法（定位变更物）
先统计每局错误数，再拿时间轴去找最近变更：
```bash
for d in "$GD"/Logs/GameLogs/*/; do f=$(ls "$d"*_r3dlog.txt | head -1); \
  echo "$(basename $d) dxgi=$(grep -c DXGI_ERROR_INVALID_CALL "$f") focus=$(grep -c 'X3D: Focus Lost' "$f")"; done
```
- 之前几十局 0 条、某天起每局几千条 = 那天有东西变了（叠加层/录制插件更新、显卡驱动、Windows 更新）。
  用文件 mtime 直接查可疑插件：`ls -la` 它的目录，比猜驱动版本快。
- **同时段还有 0 错误的局，去看它们的 focus 计数**：若「切过窗口的就炸、没切窗口的就好」，
  触发路径就定死了，报结论时也能一句话讲清。

## 4. 恢复：kill 游戏进程，客户端会自己重连
- 只 kill 游戏进程（`League of Legends.exe`），**不要 kill 客户端**（`LeagueClient*`）。
- 客户端通常 2 分钟内自动重新拉起游戏并进回对局（实测：kill 后客户端自己重启游戏，新进程 0 错误、
  ping 正常、GPU util 上来）。kill 完必须回读：新进程 `IsHungAppWindow=False` + 新 session 日志 dxgi 计数，
  再向用户宣布修好了。
- 对局中**不改游戏显示设置**：`game.cfg` 在游戏退出时才重写，改了会被覆盖，中途改窗口模式还可能二次掉线。
  设置类修复一律等这局打完。

## 5. 防复发（按证据优先级，一次改一类）
1. **关游戏内叠加层/录制钩子**：WeGame「精彩时刻」录制（`Cross\icreate\` 下 `icreate64.dll` + `recorder.exe`，
   OBS 内核，注入 D3D）与游戏内「AI 教练」overlay（`%APPDATA%\LolAICoach\logs\game-overlay.log` 里的
   `[Injector]` / `lol-coach` 页面）。这类钩子劫持 Present，焦点切换时最容易炸 DXGI。
2. **独占全屏改无边框窗口**（`game.cfg` 里 `WindowMode=0` 是独占全屏）——避开独占全屏的焦点/DXGI 切换路径。
3. 关 Windows Game Bar 后台录制（`GameDVR_Enabled`）。
4. 以上都无效才动显卡驱动（降版本 / 关「窗口化游戏优化」）。

改完让用户打一局，回来只看一件事：`r3dlog` 里 `DXGI_ERROR_INVALID_CALL` 是否为 0。

## 坑
- **别在用户对局中重启游戏或改显示设置** —— 会二次掉线，把可修复的卡死升级成真掉分。
- **WeGame 版 LoL 的 LCU API 走不通**：`LeagueClient\lockfile` 是 0 字节、进程 `CommandLine` 读不来（TenProtect 保护），
  Riot 那套 lockfile 认证别浪费时间试。要读客户端界面走截图 + OCR，要操作就让用户点或按 OCR 出的坐标 `Click`。
- **用户说「不是网络问题」多半是对的**，但结论仍要落在 netlog 的 ping/丢包上，否则两边都在凭感觉。
- 汇报分两段：**已经做了什么（附证据）+ 还要等什么（对局中不能改的）**，别让用户以为全修完了。

## 参考
- `references/remote-windows-screen-read.md` — 远程读屏/查窗口的工具链（session 0 vs console、IsHungAppWindow、
  截图不用 scp 用 `ssh 'cat'`、本机 tesseract 中文 OCR 出坐标、Git Bash 斜杠参数被 MSYS 转路径）。
- 「不跟手但 ping 正常」是另一类问题 → `game-latency-triage`。
