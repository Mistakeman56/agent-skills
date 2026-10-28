---
name: pc-remote-ops
description: Use when running commands on the user's Windows PC over SSH — Git Bash is the DEFAULT shell (2026-10-09), PowerShell only as fallback.
---

# PC 远程运维（SSH → user@192.0.2.10）

目标机：Windows 11，主机名 MYPC，用户 `user`，**管理员权限已确认**（`elevated=True`），自带 `curl.exe`、`tar`（bsdtar）、`diskpart`。

## ⚡ 首选：Git Bash（2026-10-09 起，用户指令「以后用我电脑都要用这个，不要用 powershell」）

**SSH 默认 shell 已改成 Git Bash**：`reg add "HKLM\SOFTWARE\OpenSSH" /v DefaultShell /t REG_SZ /d "C:\Program Files\Git\bin\bash.exe" /f`（原值未设置，回滚 `reg delete "HKLM\SOFTWARE\OpenSSH" /v DefaultShell /f`）。因此 SSH 进去直接就是 bash，**不经 cmd、不经 PowerShell**：

```bash
# 行内命令 —— 直接 bash 语法，零转义
ssh user@192.0.2.10 'ls -la /c/Users/<PASSWORD>/Downloads | head'
ssh user@192.0.2.10 'grep -r error /c/project --include="*.log" | wc -l'

# 整段脚本 —— stdin 传入（bash -s 读 stdin），彻底避开引号/base64 地狱
ssh user@192.0.2.10 'bash -s' < /tmp/task.sh
```

**工具齐备**：grep sed awk sort uniq wc tr cut head tail find xargs（`/usr/bin/`，bash 自动挂载，**不依赖系统 PATH**）+ `rg`/`jq`（`WinGet\Links`，2026-10-09 装）+ git + python 3.14。**PowerShell 7 明确不装**（用户指令）。

**实测对比**（同机同任务）：行内 `bash -c` **0.38s**、stdin 脚本 **0.57s**、5 任务体检 **0.95s** —— 旧的 PowerShell 转发路径 **0.98s** / PS 自身执行 **1.68s**。同任务工具可用 **15/16 vs PS 4/16**（PS 里 grep/sed/awk/wc 等全 MISSING、`sort` 是别名返回空、`find` 是 Windows 自带的另一个程序），中文输出 **无乱码 vs PS 5.1 GBK 乱码**，PS 载体还要 5300 字符 EncodedCommand（超远程命令行长度直接 exit -1）或 scp 多传一个文件。

**需要 PowerShell 时**（兜底仍可用，已验证）：`ssh user@192.0.2.10 'powershell.exe -NoProfile -Command "..."'` —— 下面「铁律」里的 PS 坑只在这条路径上生效。

**坑**：cmd 下直接敲 `bash` 报「不是内部或外部命令」，但 `where bash` 能找到、PATH/PATHEXT 全正常、绝对路径执行也成功（cmd 怪癖，2026-10-09 未查明根因）→ **已用 DefaultShell 绕开，现在根本不经过 cmd**；若回滚到 cmd 作为 shell，必须用绝对路径 `"C:\Program Files\Git\bin\bash.exe" -c '...'`。改 PATH 后 sshd 要重启才生效（`Restart-Service sshd`，需 admin，<PASSWORD> 是 admin）。git 全局代理同 127.0.0.1:7899。

## Windows-MCP（2026-10-07 部署，GUI/截图/点击/进程用，命令类仍首选 bash）

要操控 Windows 桌面/GUI/进程/注册表时，**先用 Hermes MCP 的 `windows` 服务器**，别再手动拼 PowerShell。20 个工具：App / Click / Type / Scroll / Shortcut / Snapshot / Screenshot / Clipboard / FileSystem / Process / Registry / Notification / Scrape / WaitFor / PowerShell 等。

**架构（最关键教训）**：Windows-MCP **必须在 Windows 的交互登录会话里跑**。走 `ssh` + stdio 会落在 **session 0（服务会话）**，摸不到桌面 —— 实测：`Screenshot` 报 `screen grab failed`、UI Tree 空、`Opened Windows: No windows found`、光标 (0,0)、显示器识别成 1024×768 的 `WinDisc` 幽灵屏；而你的真机是 DISPLAY2 3840×2160 主屏 + DISPLAY1 副屏。

正确架构：PC 上 `windows-mcp install --transport streamable-http --host 0.0.0.0 --port 8026` 建**每用户计划任务 `windows-mcp-server`**（登录时自动拉起，跑在 **console 会话 3**），Hermes 走 HTTP 直连：

```yaml
mcp_servers:
  windows:
    url: http://192.0.2.10:8026/mcp    # 不能带尾斜杠：`/mcp/` 会 307 跳到 `/mcp`
    headers:
      Authorization: Bearer <config.toml 里的 auth_key>
    connect_timeout: 60
    timeout: 120
```

auth_key 由 `windows-mcp auth --transport streamable-http --host 0.0.0.0 --port 8026` 生成，写在 PC `C:\Users\<PASSWORD>\.windows-mcp\config.toml`，`serve` 自动读取；**`install` 不认 `--auth-key`**（只认 `--transport/--host/--port/--force`），也不读 config 里的 host/port（默认 127.0.0.1:8000，必须显式传）。日志：`~/.windows-mcp/server.log` / `server.error.log`；卸载 `windows-mcp uninstall`。验证：`hermes mcp test windows` → Connected + 20 个工具；不带 key 请求返回 401。

**调用方式**：去掉 mcp-compressor 包装后，直接注册 **20 个原始工具**（`mcp__windows__Screenshot` / `PowerShell` / `Process` …）。参数名必须先查 `tools/list` 或 `windows_get_tool_schema`，别猜（踩过：`Notification` 必填 `title/message/app_id`；`Process` 只有 `mode/name/pid/sort_by/limit/force`，没有 query；`PowerShell` 只有 `command` + `timeout`）。**server 一掉线，这 20 个工具会整体从会话注册表消失** —— 见下面「故障模式与加固」。

**实测性能**（HTTP 模式，局域网）：`Screenshot` ~450ms（含真实图像）、`Process` 26ms、`Clipboard` 29ms、`Move`/`Click` 同类**往返 ~0.8s**（779/832ms 实测，光标可验证移动）、完整 `Snapshot`（UI 树 + 窗口列表）**~12.4s（贵，别频繁用）**、stdio 冷启动握手 ~4.2s（HTTP 常驻无此开销）。要「看一眼」用 Screenshot，要「找元素」才用 Snapshot。

**`Screenshot` 的 `Opened Windows` / `Focused Window` 会报 `No windows found`，但图里明明有窗口** —— 快速路径（backend=pillow）只出图，窗口列表那半边枚举可能为空，**不是 session 0 故障**（判断依据：图能出真桌面就是好的）。要元素/窗口列表用 `Snapshot`。

**坑**：
1. **session 0 陷阱**（最重）：SSH/stdin 拉起的进程在服务会话，GUI/截图/窗口枚举全废；只有 API 类工具（Process/Registry/文件/通知）能用。GUI 一律走计划任务 + HTTP。
2. **锁屏 / 未登录** → 计划任务不启动，GUI 工具失效；解锁后自动恢复（任务是登录时启动的）。
3. PC 的 SSH 会话 PATH 里**没有** `C:\Users\<PASSWORD>\.local\bin`（`where uvx` 找得到，直接敲 `uvx` 报「不是内部或外部命令」）→ 一律用绝对路径。
4. PC 的 LAN IP：**静态租约已存在**（`<PASSWORD>` / `00:00:00:00:00:00` / `192.0.2.10`，dnsmasq 已加载），不用再绑。旧的 `/opt/mcp-start-windows.sh`（stdio 双 IP 回退）已降级为 API 级备用，**做不了 GUI**。
5. 参数名必须先查 schema（`windows_get_tool_schema` 或 tools/list），别猜：`Notification` 必填 `title/message/app_id`；`Process` 只有 `mode/name/pid/sort_by/limit/force`，`sort_by` 枚举是 memory/cpu/name，`Clipboard.mode` 是 get/set。
6. PVE 的 `mcp-server`（CT <ID>，Debian 12，2C/2G）是 **Linux 容器，装不了** Windows 专用的 UI Automation 服务 → Windows-MCP 必须跑在 Windows 上；其它纯 Python MCP 仍放 CT <ID>。
7. 配置备份：`~/.hermes/backups/config.yaml.bak-windows-*`（stdio 版与 http 版各一份）。

## 故障模式与加固（2026-10-07 实测）

**症状**：会话里 `mcp__windows__*` 全部消失，`tool_search` 的 available_sources 里也没有 `windows`。
**根因**：服务端进程收到 `^C` 退出 → 8026 不再监听 → Hermes 连接失败（`All connection attempts failed`，约 7s）→ 该 server 的工具被从会话摘掉。
**死因**：任务用 `cmd /c start-server.cmd` 启动，桌面留一个**可见控制台窗口**，被 Ctrl+C 或手滑关闭即挂。

修复（已应用并验证）：
1. `schtasks /run /tn windows-mcp-server` 立刻拉活；`C:\Users\<PASSWORD>\.windows-mcp\server.error.log` 尾部可见 `^C` 死因，`server.log` 有访问记录。
2. 防误关：写 `start-hidden.ps1`（内容 `& '…\start-server.cmd'`），`Set-ScheduledTask` 把 Action 改成 `powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File C:\Users\<PASSWORD>\.windows-mcp\start-hidden.ps1`。**隐藏控制台不影响** UIA/Screenshot/Click（同 session 3、同 window station）。
3. 看门狗任务 `windows-mcp-watchdog`：每 5 分钟（`PT5M`）查 8026，未监听则 `Start-ScheduledTask windows-mcp-server`。用 `Register-ScheduledTask` + `New-ScheduledTaskTrigger -Once -RepetitionInterval`（`-RepetitionDuration 3650天`），不需要密码。

**排查顺序**：`hermes mcp test windows` → `Get-NetTCPConnection -LocalPort 8026 -State Listen` → `schtasks /query /tn windows-mcp-server` → error.log 尾部。config 正常但 test 失败 = 服务端死了，**别去改 config**。

**工具不在会话列表时**：先 `tool_search`；搜不到 `windows` 服务 = server 掉线，不是配置错。恢复后要 `/reload-mcp` 才会重新注册到本会话 —— **在那之前可直接打 HTTP 端点干活**：`POST http://192.0.2.10:8026/mcp`，头 `Authorization: Bearer <config.toml 的 auth_key>` + `Accept: application/json, text/event-stream`，顺序 initialize → notifications/initialized → tools/list / tools/call；SSE 回包按行解析 `data:`。

## 铁律

1. **命令与脚本全英文 ASCII**。中文输出会吞掉后续内容 / 杀掉会话。
2. **PowerShell 脚本严禁含中文注释/中文字符串** —— 无 BOM 的 UTF-8 落盘后，PS 5.1 按 ANSI 读取，多字节序列错位会吞掉花括号，报 `UnexpectedToken / MissingEndParenthesis` 且行号错乱。**这是最常见的脚本失败原因**（英文脚本一次成功，带中文注释必挂）。
3. **长脚本必须 base64 落盘再执行**，不能走 stdin（`powershell -Command -` 只执行首行），也不能靠引号内嵌（引号会被 shell 吃掉，报 `OpenRead(C:UsersP...)` 缺引号）。
   ```bash
   b64=$(base64 -w0 /tmp/x.ps1)
   ssh user@192.0.2.10 'powershell -NoProfile -Command "[IO.File]::WriteAllText('"'"'C:\Users\Public\x.ps1'"'"',[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"'"'B64'"'"')))"'
   ssh user@192.0.2.10 'powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\Public\x.ps1'
   ```
4. **结果写文件再读**，中文列名用 `-join` / 手写 ASCII 标签，别用 `Format-Table`。
5. **PowerShell 里带空格的参数值传给 `Start-Process -ArgumentList` 不会自动加引号** → curl 会把 `dl_exit=%{http_code} size=...` 当成 URL，报 `curl: (3) URL rejected: Bad hostname`。**解决：`-w` 值里不能有空格**，用 `;` 分隔；或直接走 `Start-Process` 不带 `-w`（实测 `@('-sSL','--retry','3','-o',$out,$url) -Wait -PassThru` 稳定跑完 1.19GB）。
5b. **`.ps1` 脚本里写中文注释/中文字符串会炸**（`UnexpectedToken`、行号错乱、报在 `}` 上）：无 BOM 的 UTF-8 落盘后 PS 5.1 按 ANSI 读，中文字节错位吞掉语法。**全程写纯 ASCII 脚本**，中文只出现在 SSH 命令行输出里（那部分只是乱码，不影响执行）。
6. **后台下载别用 `Start-Process`**（SSH 会话一断进程被杀，无产出也无报错）。**前台跑完**反而稳：`curl.exe -L -C - -o out.zip -w 'http=...;size=...'`，30~60 秒即可完成 1GB+。
7. **注册表用 `reg add`**（`Set-ItemProperty` 参数不存在）；PowerShell 事件用 `Get-EventLog`/`wevtutil`；**EncodedCommand 会被 ssh 吃掉** → 改 base64 落盘。
8. 长 PowerShell 或多参数命令 → 包 `.bat` 或直接 `-File` 执行。
9. **做完必须回读验证**：`Test-Path` / 文件大小 / `Get-FileHash`。`EXTRACT_OK`、`exitcode=0` 这类自报不算数——曾出现 3.78s 解压 1.19GB 的可疑速度，必须列目录 + 校验 sha256 才能确认真落地。
10. **临时文件用完即删**，放 `C:\Users\Public\`（最后 `Get-ChildItem` 确认只剩 `desktop.ini`）。

## 擦盘/分区（不可逆操作）

- **先 `Get-CimInstance Win32_DiskDrive` 列盘 → 按 Model + 尺寸白名单校验 → 比对 C: 所在 DiskNumber，命中即 `ABORT`**，再执行 diskpart。
- 本机已知布局：disk0 = 致态 Ti600 1TB（C/D，**系统盘**）；disk1 = `MS YSUWD10-128GSY` 128G USB-SSD。
- **只有 `format.com` / `diskpart format` 有 32GB FAT32 上限；PowerShell `Format-Volume -DriveLetter X -FileSystem FAT32` 没有这个限制**（实测 119.2GB 一次成功，秒级完成）。因此合并成单个大 FAT32 盘的正确做法：diskpart `clean` + `create partition primary` + `assign` → `Format-Volume` → `diskpart ACTIVE`。
- **`assign` 之后立刻 `Test-Path 'U:'` 会返回 False**（分区已挂载但未格式化，文件系统 Unknown）→ 别据此判失败，用 `Get-Partition -DriveLetter U` 确认挂载，再格式化。
- **MBR 上 `Get-Partition .Type` 显示 `FAT32 XINT13` 才是主分区**；`IsActive` 须为 True 才能 BIOS 引导。diskpart 中文输出是 GBK 乱码，判断成功看 `IsActive=True` / 卷信息，别读乱码行。
- diskpart 脚本同样走 base64 落盘 → `diskpart /s file.txt`。

## unRAID 启动盘

- 官方直链在 `https://docs.unraid.net/unraid-os/download_list/` 的 JS 渲染里，**HTML 抓不到**（Vite SPA），用 browser 读 `<a>` 得到 `releases.unraid.net/dl/stable/<ver>/<sha256>/unRAIDServer-<ver>-x86_64.zip`。
- **公开可下的最新稳定版 ≠ 页面写的当前系列**：7.4.x 是 beta 要登录，公开直链停在 **7.3.2**（MD5 `5471d2b8d2242614c4392837ee1c31fa`）。
- zip 内 `*.sha256` 是**独立小文件**，`Get-FileHash` 逐个比对，6 个全 PASS 才算完好。
- 引导写入：`U:\syslinux\syslinux.exe -maf U:`（等价于交互式 `make_bootable.bat`，跳过问答），之后 `detail partition` 确认 `活动: 是`、类型 `0C`。
- 配置链 `EFI/boot/syslinux.cfg` → `include /syslinux/syslinux.cfg`；**根目录没有 `syslinux.cfg` 是官方原样，不是缺文件**。
- **坑：`YSUWD10-128GSY` 是 USB-SSD（`External hard disk media`），不是标准闪存盘**；unRAID 官方要求 unique GUID 的 USB flash。若启动报找不到 flash，需换真正的 U 盘。
- unRAID 7.3+ 支持 **internal boot**（装进内部 SATA/NVMe），U 盘不再是唯一方案；但首次引导仍建议 U 盘。
- **危险**：unRAID 会把 PC 的致态 C/D 列为候选阵列盘，**首启务必保持 Array Stopped**，否则数据被清。